# k-cube-daemon/app.py
# (替换完整内容)
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMessageBox
from PyQt6.QtCore import QThread, Qt, QObject, pyqtSignal

from ui.main_window import MainWindow
from ui.login_window import LoginWindow
from tray_icon import TrayIcon
from core.worker import Worker
from config_manager import config
from k_cube.repository import Repository
from k_cube.client import APIClient, APIError
from PyQt6.QtCore import pyqtSlot  # 导入 pyqtSlot
# --- 将 AuthWorker 移到 app.py，作为应用的核心逻辑部分 ---


class AuthWorker(QObject):
    finished = pyqtSignal(bool, str, str)

    def __init__(self, mode, remote_url, email, password, password2=None):
        super().__init__()
        self.mode = mode
        self.remote_url = remote_url
        self.email = email
        self.password = password
        self.password2 = password2

    def run(self):
        try:
            client = APIClient(self.remote_url)
            if self.mode == 'login':
                token = client.login(self.email, self.password)
                self.finished.emit(True, token, self.email)
            elif self.mode == 'register':
                if self.password != self.password2:
                    raise ValueError("两次输入的密码不一致。")
                client.register(self.email, self.password)
                token = client.login(self.email, self.password)
                self.finished.emit(True, token, self.email)
        except Exception as e:
            self.finished.emit(False, str(e), self.email)


class KCubeApplication(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.setQuitOnLastWindowClosed(False)

        self.client = None
        self.worker_pool = {}

        self.tray_icon = TrayIcon()
        self.main_window = None
        self.login_window = LoginWindow()

        # --- 连接与 MainWindow 无关的信号 ---
        self.tray_icon.action_quit.triggered.connect(self.quit_app)
        self.tray_icon.action_open.triggered.connect(self.show_main_window)
        self.login_window.login_successful.connect(self.on_login_success)

        self.tray_icon.show()
        self.tray_icon.action_settings.triggered.connect(
            self.show_main_window_and_switch_to_login)
        self.check_initial_state()

    def check_initial_state(self):
        api_token = config.get("api_token")
        remote_url = config.get("remote_url")

        if not api_token or not remote_url:
            self.set_logged_out_state()
            self.login_window.show()
        else:
            self.set_logged_in_state()
            self.show_main_window()

    def show_main_window(self):
        """一个统一的显示主窗口的入口，处理 None 的情况。"""
        if self.main_window:
            if self.main_window.isVisible():
                self.main_window.activateWindow()
            else:
                self.main_window.show()
        else:
            # 如果 main_window 还不存在 (例如，用户已登录但重启了应用)，
            # 调用 set_logged_in_state 会创建它
            if config.get("api_token"):
                self.set_logged_in_state()
                self.main_window.show()
            else:  # 如果未登录，则显示登录窗口
                self.login_window.show()

    def on_login_success(self):
        self.login_window.close()  # 关闭登录对话框
        self.set_logged_in_state()
        self.show_main_window()

    def set_logged_in_state(self):
        self.client = APIClient(config.get(
            "remote_url"), config.get("api_token"))

        if self.main_window is None:
            self.main_window = MainWindow()
            # 仅在首次创建时连接信号
            self.main_window.login_request.connect(self.handle_login)
            self.main_window.register_request.connect(self.handle_register)
            self.main_window.logout_request.connect(self.handle_logout)
            self.main_window.new_vault_request.connect(self.create_new_vault)
            self.main_window.manual_sync_request.connect(
                self.trigger_manual_sync)
            self.main_window.vaults_changed.connect(self.restart_all_workers)

        self.main_window.set_user_status(config.get("user_email", "未知用户"))
        self.main_window.switch_to_page("vault")
        self.restart_all_workers()

    def show_main_window_and_switch_to_login(self):
        """显示主窗口并强制切换到登录/设置页面。"""
        if self.main_window:
            self.main_window.switch_to_page("login")  # 先切换
            self.show_main_window()  # 再显示
        else:
            # 如果应用刚启动就点设置，直接显示登录窗口
            self.login_window.show()

    def set_logged_out_state(self):
        self.stop_all_workers()
        self.client = None
        if self.main_window:
            self.main_window.set_user_status(None)
            self.main_window.switch_to_page("login")
            # --- 核心修复：登出后主动显示登录页 ---
            self.main_window.show()
        else:
            # 这种情况基本不会发生，但作为保险
            self.login_window.show()

    def handle_login(self, url, email, password):
        self.main_window.set_loading_state('login', True)
        # --- 核心实现 ---
        self.auth_worker = AuthWorker('login', url, email, password)
        self.auth_thread = QThread()
        self.auth_worker.moveToThread(self.auth_thread)
        self.auth_thread.started.connect(self.auth_worker.run)
        self.auth_worker.finished.connect(self.on_auth_finished)
        self.auth_worker.finished.connect(self.auth_thread.quit)
        self.auth_worker.finished.connect(self.auth_worker.deleteLater)
        self.auth_thread.finished.connect(self.auth_thread.deleteLater)
        self.auth_thread.start()

    def handle_register(self, url, email, password, password2):
        self.main_window.set_loading_state('register', True)
        # --- 核心实现 ---
        self.auth_worker = AuthWorker(
            'register', url, email, password, password2)
        # ... (线程创建和启动逻辑同 handle_login) ...
        self.auth_thread = QThread()
        self.auth_worker.moveToThread(self.auth_thread)
        self.auth_thread.started.connect(self.auth_worker.run)
        self.auth_worker.finished.connect(self.on_auth_finished)
        self.auth_worker.finished.connect(self.auth_thread.quit)
        self.auth_worker.finished.connect(self.auth_worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.auth_thread.start()

    def on_auth_finished(self, success, result, email):
        mode = self.auth_worker.mode
        self.main_window.set_loading_state(mode, False)
        if success:
            config.set("api_token", result)
            config.set("user_email", email)

            # --- 核心修复：直接从 MainWindow 实例访问控件 ---
            # 无论当前是哪个页面，remote_input 都是 MainWindow 的属性
            # 我们假设注册时也需要远程URL，所以从登录页获取
            config.set("remote_url", self.main_window.login_remote_input.text())

            self.set_logged_in_state()
        else:
            self.main_window.show_auth_error(mode, f"操作失败: {result}")

    def handle_logout(self):
        config.set("api_token", None)
        config.set("user_email", None)
        self.set_logged_out_state()
        self.tray_icon.set_status("idle", "已登出")

    # ... (create_new_vault, restart_all_workers, etc. 保持不变) ...
    def create_new_vault(self, path, name):
        try:
            self.setOverrideCursor(Qt.CursorShape.WaitCursor)
            vault_info = self.client.create_vault(name)
            repo = Repository.initialize(Path(path))
            repo.config.set("vault_id", vault_info['id'])
            repo.config.set("remote_url", config.get("remote_url"))
            vault_paths = config.get("vault_paths", [])
            vault_paths.append(path)
            config.set("vault_paths", vault_paths)
            self.main_window.load_vaults_to_list()
            self.restart_all_workers()
        except Exception as e:
            QMessageBox.critical(self.main_window, "创建失败", str(e))
        finally:
            self.restoreOverrideCursor()

    def restart_all_workers(self):
        self.stop_all_workers()

        vault_paths = config.get("vault_paths", [])

        # --- 核心修复：命令 MainWindow 刷新其列表 ---
        if self.main_window:
            self.main_window.load_vaults_to_list()

        if not vault_paths:
            self.tray_icon.set_status("idle", "无保险库被监控。")
            return

        for path in vault_paths:
            self.start_worker(path)

        self.tray_icon.set_status("idle", f"正在监控 {len(vault_paths)} 个保险库。")

    def start_worker(self, vault_path: str):
        if not self.client:
            return

        thread = QThread()
        worker = Worker(vault_path, self.client)
        worker.moveToThread(thread)

        worker.status_changed.connect(self.main_window.update_vault_status)
        # --- 核心修复：worker 结束后，让线程也退出 ---
        worker.finished.connect(thread.quit)
        # --- 核心修复：线程结束后，再进行对象清理 ---
        thread.finished.connect(lambda: self.on_worker_finished(vault_path))

        thread.started.connect(worker.run)
        thread.start()

        self.worker_pool[vault_path] = {'worker': worker, 'thread': thread}

    def on_worker_finished(self, vault_path):
        if vault_path in self.worker_pool:
            # 清理 worker 和 thread 对象
            worker_data = self.worker_pool[vault_path]
            worker_data['worker'].deleteLater()
            worker_data['thread'].deleteLater()
            del self.worker_pool[vault_path]
            print(
                f"Worker for {Path(vault_path).name} has finished and been cleaned up.")

    @pyqtSlot(str)  # 明确这是一个槽函数
    def trigger_manual_sync(self, vault_path: str):
        if vault_path in self.worker_pool:
            worker_data = self.worker_pool[vault_path]
            worker_instance = worker_data['worker']
            if worker_instance:
                # 使用 invokeMethod 确保线程安全调用
                worker_instance.perform_sync()
        else:
            if self.main_window:
                self.main_window.update_vault_status(
                    vault_path, "error", "监控进程未运行，无法同步。")

    def stop_all_workers(self):
        for path, worker_data in list(self.worker_pool.items()):
            if worker_data['thread'].isRunning():
                # --- 核心修复：通过 worker 的 stop 方法来请求停止 ---
                worker_data['worker'].stop()
                # 等待线程自然结束
                worker_data['thread'].wait(2000)  # 等待最多2秒

    def quit_app(self):
        print("正在退出 K-Cube 守护进程...")
        self.stop_all_workers()
        self.quit()


if __name__ == "__main__":
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = KCubeApplication(sys.argv)
    sys.exit(app.exec())
