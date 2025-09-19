# k-cube-daemon/core/worker.py

import time
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from k_cube.repository import Repository
from k_cube.config import ConfigManager as VaultConfigManager
from k_cube.client import APIClient, APIError, AuthenticationError
from k_cube.sync import Synchronizer

from .watcher import WatcherThread


class Worker(QObject):
    status_changed = pyqtSignal(str, str)
    vault_path_invalid = pyqtSignal()

    def __init__(self, vault_path_str: str):
        super().__init__()
        self.vault_path = Path(vault_path_str)
        self.watcher_thread = WatcherThread(vault_path_str)

        # 使用一个简单的定时器来实现去抖 (debounce)
        self.debounce_timer = QTimer()
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.setInterval(2000)  # 2秒延迟
        self.debounce_timer.timeout.connect(self.perform_sync)

        self.watcher_thread.file_changed.connect(self.on_file_changed)

    def run(self):
        """主逻辑，在自己的线程中运行。"""
        if not self.vault_path.exists() or not self.vault_path.is_dir():
            self.vault_path_invalid.emit()
            return

        self.status_changed.emit("idle", f"正在监控: {self.vault_path.name}")
        self.watcher_thread.start()

    def stop(self):
        self.watcher_thread.stop()
        self.watcher_thread.wait()

    def on_file_changed(self):
        """
        文件变更时触发，但使用定时器去抖，避免短时内重复同步。
        """
        # 每次有文件变化，就重置（或启动）定时器
        self.debounce_timer.start()
        self.status_changed.emit("idle", "检测到变更，等待同步...")

    def perform_sync(self):
        self.status_changed.emit("syncing", "正在同步...")
        try:
            repo = Repository.find(self.vault_path)
            if not repo:
                self.status_changed.emit("error", "找不到保险库。")
                return

            vault_config = VaultConfigManager(repo.kcube_path)
            remote_url = vault_config.get("remote_url")
            api_token = vault_config.get("api_token")

            if not remote_url or not api_token:
                self.status_changed.emit("error", "未配置远程或未登录。")
                return

            # --- 关键逻辑修改 ---

            # 1. 先检查是否有本地变更需要提交
            status = repo.get_status()
            if status.has_unstaged_changes() or status.has_tracked_unstaged_changes() or status.untracked_files:
                repo.add([self.vault_path])
                commit_message = {"type": "Auto",
                                  "summary": "Auto-sync changes"}
                repo.commit(commit_message)

            # 2. 执行同步，并获取是否下载了新内容
            client = APIClient(remote_url, api_token)
            # 注意：Synchronizer 依赖的 rich.console 在 GUI 应用中会打印到终端
            # 生产环境中应提供一个 silent 模式
            synchronizer = Synchronizer(repo, client)
            did_download_changes = synchronizer.sync()

            # 3. **只在下载了新内容时**才执行 restore
            if did_download_changes:
                self.status_changed.emit("syncing", "正在应用远程变更...")
                latest_hash = repo.db.get_latest_version_hash()
                if latest_hash:
                    # 我们暂时禁用 watcher 来避免 restore 触发新的事件
                    self.watcher_thread.stop()

                    repo.restore(latest_hash, hard_mode=True)

                    # 完成后重启 watcher
                    self.watcher_thread.start()

            self.status_changed.emit("success", "同步成功！")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.status_changed.emit("error", f"同步失败: {e}")
