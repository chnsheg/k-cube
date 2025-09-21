# k-cube-daemon/core/worker.py
# (替换完整内容)
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, pyqtSlot

from k_cube.repository import Repository
from k_cube.client import APIClient
from k_cube.sync import Synchronizer, SyncResult
from .watcher import WatcherThread


class Worker(QObject):
    # --- 升级后的信号 ---
    # vault_path, direction ('upload'/'download'/'bidirectional')
    sync_started = pyqtSignal(str, str)
    sync_finished = pyqtSignal(str, SyncResult)  # vault_path, result_object
    sync_error = pyqtSignal(str, str)       # vault_path, error_message
    # vault_path, success, message
    validation_finished = pyqtSignal(str, bool, str)
    finished = pyqtSignal(str)

    # --- 新增信号，用于线程安全的任务触发 ---
    _manual_sync_request = pyqtSignal()

    def __init__(self, vault_path: str, client: APIClient):
        super().__init__()
        self.vault_path_str = vault_path
        self.vault_path = Path(vault_path)
        self.client = client
        self.watcher_thread = None
        self.debounce_timer = QTimer()
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.setInterval(2000)
        self._is_running = False

        # --- 核心修复：连接内部信号到槽 ---
        self._manual_sync_request.connect(self.perform_sync)

    def run(self):
        self._is_running = True
        try:
            repo = Repository.find(self.vault_path)
            if not repo or not repo.vault_id:
                raise ValueError("本地保险库无效或未关联。")
            self.client.get_vault_details(repo.vault_id)
            self.validation_finished.emit(
                self.vault_path_str, True, "验证成功，正在监控")
        except Exception as e:
            self.validation_finished.emit(
                self.vault_path_str, False, f"验证失败: {e}")
            self.stop()
            return

        self.debounce_timer.timeout.connect(self.perform_sync)
        self.watcher_thread = WatcherThread(self.vault_path_str)
        self.watcher_thread.file_changed.connect(self.on_file_changed)
        self.watcher_thread.start()

    def stop(self):
        if self.watcher_thread and self.watcher_thread.isRunning():
            self.watcher_thread.stop()
            self.watcher_thread.wait()
        self._is_running = False
        self.finished.emit(self.vault_path_str)

    def on_file_changed(self):
        if not self._is_running:
            return
        self.debounce_timer.start()

    @pyqtSlot()
    def perform_sync(self):
        if not self._is_running:
            return
        try:
            repo = Repository.find(self.vault_path)
            status = repo.get_status()
            if status.has_unstaged_changes() or status.has_tracked_unstaged_changes() or status.untracked_files:
                repo.add([self.vault_path])
                repo.commit({"type": "Auto", "summary": "Auto-sync changes"})

            synchronizer = Synchronizer(repo, self.client)
            local_versions = repo.db.get_all_version_hashes()
            sync_state = self.client.check_sync_state(
                repo.vault_id, local_versions)
            versions_to_upload = sync_state.get('versions_to_upload', [])
            versions_to_download = sync_state.get('versions_to_download', [])

            direction = "none"
            if versions_to_upload and versions_to_download:
                direction = "bidirectional"
            elif versions_to_upload:
                direction = "upload"
            elif versions_to_download:
                direction = "download"

            # 只有在有事可做时才发射信号和同步
            if direction != "none":
                self.sync_started.emit(self.vault_path_str, direction)

            result = synchronizer.sync()  # sync 内部不再检查，直接执行

            self.sync_started.emit(self.vault_path_str, result.direction)

            if result.direction in ["download", "bidirectional"]:
                latest_hash = repo.db.get_latest_version_hash()
                if latest_hash:
                    # 暂停监控以避免循环
                    self.watcher_thread.stop()
                    repo.restore(latest_hash, hard_mode=True)
                    self.watcher_thread.start()

            self.sync_finished.emit(self.vault_path_str, result)
        except Exception as e:
            self.sync_error.emit(self.vault_path_str, str(e))
