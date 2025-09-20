from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, pyqtSlot

from k_cube.repository import Repository
from k_cube.config import ConfigManager as VaultConfigManager
from k_cube.client import APIClient, APIError
from k_cube.sync import Synchronizer
from .watcher import WatcherThread


class Worker(QObject):
    status_changed = pyqtSignal(str, str, str)
    finished = pyqtSignal(str)

    def __init__(self, vault_path: str, client: APIClient):
        super().__init__()
        self.vault_path_str = vault_path
        self.vault_path = Path(vault_path)
        self.client = client
        self.watcher_thread = None  # 延迟创建
        self.debounce_timer = QTimer()
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.setInterval(2000)
        self.debounce_timer.timeout.connect(self.perform_sync)

        # --- 核心修复：增加运行状态标志 ---
        self._is_running = False

    def run(self):
        """主逻辑，包含启动前的健康检查。"""
        self._is_running = True
        try:
            self.status_changed.emit(self.vault_path_str, "syncing", "正在验证...")
            repo = Repository.find(self.vault_path)
            if not repo or not repo.vault_id:
                raise ValueError("本地保险库无效或未关联。")
            self.client.get_vault_details(repo.vault_id)
        except Exception as e:
            self.status_changed.emit(
                self.vault_path_str, "error", f"验证失败: {e}")
            self.finished.emit(self.vault_path_str)
            return

        self.status_changed.emit(self.vault_path_str, "idle", f"正在监控")

        # 在 Worker 自己的线程中创建和启动 Watcher
        self.watcher_thread = WatcherThread(self.vault_path_str)
        self.watcher_thread.file_changed.connect(self.on_file_changed)
        self.watcher_thread.start()

        # --- 核心修复：保持 Worker 存活 ---
        while self._is_running:
            self.thread().msleep(100)  # 用 msleep 避免 CPU 占用

    def stop(self):
        """请求停止 worker 和 watcher。"""
        self.status_changed.emit(self.vault_path_str, "idle", "正在停止...")
        if self.watcher_thread:
            self.watcher_thread.stop()
        self._is_running = False  # 设置标志位以退出 run() 循环

    def on_file_changed(self):
        if not self._is_running:
            return
        self.status_changed.emit(self.vault_path_str, "idle", "检测到变更...")
        self.debounce_timer.start()

    @pyqtSlot()  # 明确这是一个槽函数
    def perform_sync(self):
        self.status_changed.emit(self.vault_path_str, "syncing", "正在同步...")
        try:
            repo = Repository.find(self.vault_path)
            # ... (同步逻辑不变) ...
            self.status_changed.emit(self.vault_path_str, "success", "同步成功！")
        except Exception as e:
            self.status_changed.emit(
                self.vault_path_str, "error", f"同步失败: {e}")
