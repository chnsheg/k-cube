# k-cube-daemon/core/worker.py
# (替换完整内容)
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, pyqtSlot

from k_cube.repository import Repository
from k_cube.config import ConfigManager as VaultConfigManager
from k_cube.client import APIClient, APIError
from k_cube.sync import Synchronizer
from .watcher import WatcherThread


class Worker(QObject):
    # 信号现在包含 vault_path，以便UI知道是哪个worker在报告
    # vault_path, status_name, message
    status_changed = pyqtSignal(str, str, str)
    finished = pyqtSignal(str)  # vault_path

    def __init__(self, vault_path: str, client: APIClient):
        super().__init__()
        self.vault_path_str = vault_path
        self.vault_path = Path(vault_path)
        self.client = client
        self.watcher_thread = WatcherThread(vault_path)
        self.debounce_timer = QTimer()
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.setInterval(2000)
        self.debounce_timer.timeout.connect(self.perform_sync)
        self.watcher_thread.file_changed.connect(self.on_file_changed)

    def run(self):
        """主逻辑，包含启动前的健康检查。"""
        try:
            # 1. 保险库健康检查
            self.status_changed.emit(self.vault_path_str, "syncing", "正在验证...")
            repo = Repository.find(self.vault_path)
            if not repo or not repo.vault_id:
                raise ValueError("本地保险库无效或未关联云端。")

            # 2. 与服务器验证 vault_id
            self.client.get_vault_details(repo.vault_id)

        except Exception as e:
            self.status_changed.emit(
                self.vault_path_str, "error", f"验证失败: {e}")
            self.finished.emit(self.vault_path_str)
            return

        self.status_changed.emit(self.vault_path_str, "idle", f"正在监控")
        self.watcher_thread.start()

    def stop(self):
        self.watcher_thread.stop()
        self.watcher_thread.wait()
        self.finished.emit(self.vault_path_str)

    def on_file_changed(self):
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
