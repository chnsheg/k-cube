# k-cube-daemon/app.py
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QThread

from ui.main_window import MainWindow
from tray_icon import TrayIcon
from core.worker import Worker
from config_manager import config


class KCubeApplication(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.setQuitOnLastWindowClosed(False)

        # Worker 池，用 vault_path 作为键
        self.worker_pool = {}

        self.tray_icon = TrayIcon()
        self.main_window = MainWindow()

        # --- 连接信号与槽 ---
        self.tray_icon.action_open.triggered.connect(self.main_window.show)
        self.tray_icon.action_quit.triggered.connect(self.quit_app)
        self.main_window.vaults_changed.connect(self.restart_all_workers)

        self.tray_icon.show()
        self.restart_all_workers()  # 初始启动

    def restart_all_workers(self):
        # 停止所有当前正在运行的 worker
        for path, worker_data in list(self.worker_pool.items()):
            worker_data['worker'].stop()
            worker_data['thread'].quit()
            worker_data['thread'].wait()
        self.worker_pool.clear()

        # 为配置文件中的每个 vault 启动一个新的 worker
        vault_paths = config.get("vault_paths", [])
        if not vault_paths:
            self.tray_icon.set_status("idle", "无保险库被监控。")
            return

        for path in vault_paths:
            self.start_worker(path)

        self.tray_icon.set_status("idle", f"正在监控 {len(vault_paths)} 个保险库。")

    def start_worker(self, vault_path: str):
        thread = QThread()
        worker = Worker(vault_path)
        worker.moveToThread(thread)

        # 连接 worker 的信号到 UI 的槽
        # 注意：多个 worker 会共享同一个托盘图标，需要更精细的状态管理
        # 此处简化为只显示最后一个 worker 的状态
        worker.status_changed.connect(self.tray_icon.set_status)
        worker.vault_path_invalid.connect(
            lambda: self.handle_invalid_path(vault_path))

        thread.started.connect(worker.run)
        thread.start()

        self.worker_pool[vault_path] = {'worker': worker, 'thread': thread}

    def handle_invalid_path(self, path):
        self.tray_icon.set_status("error", f"路径无效: {Path(path).name}")

    def quit_app(self):
        for path, worker_data in self.worker_pool.items():
            worker_data['worker'].stop()
            worker_data['thread'].quit()
            worker_data['thread'].wait()
        self.quit()


if __name__ == "__main__":
    app = KCubeApplication(sys.argv)
    sys.exit(app.exec())
