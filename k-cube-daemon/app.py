# k-cube-daemon/app.py
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMessageBox
from PyQt6.QtCore import QThread, Qt, QObject, pyqtSignal, pyqtSlot, QEventLoop
from PyQt6.QtGui import QGuiApplication

from ui.main_window import MainWindow
from tray_icon import TrayIcon
from core.worker import Worker
from config_manager import config, ConfigManager
from k_cube.repository import Repository
from k_cube.client import APIClient, APIError
from k_cube.sync import SyncResult, Synchronizer
from ui.components.toast import Toast
from ui.components.custom_dialogs import CustomMessageBox, PasswordConfirmDialog
import time


class AuthWorker(QObject):
    """
    一个专用于在后台线程执行认证（登录/注册）任务的 Worker。
    """
    finished = pyqtSignal(bool, str, str)  # success, message/token, email

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
    """
    K-Cube 守护进程的主应用类，负责所有业务逻辑、状态管理和窗口协调。
    """

    def __init__(self, argv):
        super().__init__(argv)
        self.setQuitOnLastWindowClosed(False)

        self.client = None
        self.worker_pool = {}
        self.active_toast = None
        self.last_auth_time = 0
        self.auth_cache_duration = 300  # 5分钟 (秒)

        self.tray_icon = TrayIcon()
        self.main_window = MainWindow()

        # --- 连接所有信号与槽 ---
        self.main_window.login_request.connect(self.handle_login)
        self.main_window.register_request.connect(self.handle_register)
        self.main_window.logout_request.connect(self.handle_logout)
        self.main_window.new_vault_request.connect(self.create_new_vault)
        self.main_window.clone_request.connect(self.clone_vault)
        self.main_window.manual_sync_request.connect(self.trigger_manual_sync)
        self.main_window.vaults_changed.connect(self.restart_all_workers)
        self.main_window.manage_cloud_request.connect(
            self.fetch_remote_vaults_and_decide_page)
        self.main_window.delete_vault_request.connect(self.handle_delete_vault)
        self.main_window.link_request.connect(self.handle_link_request)

        self.tray_icon.action_open.triggered.connect(self.main_window.show)
        self.tray_icon.action_settings.triggered.connect(
            self.show_main_window_and_switch_to_login)
        self.tray_icon.action_quit.triggered.connect(self.quit_app)

        self.tray_icon.show()
        self.check_initial_state()

    def check_initial_state(self):
        if config.get("api_token") and config.get("remote_url"):
            self.set_logged_in_state()
            self.main_window.show()
        else:
            self.set_logged_out_state()
            self.main_window.show()

    def show_main_window_and_switch_to_login(self):
        self.main_window.set_view_for_login_state(False)
        self.main_window.show()
        self.main_window.activateWindow()

    def show_toast(self, message: str, status: str = "success"):
        if self.active_toast and status not in ["success", "error"]:
            return
        if self.active_toast:
            self.active_toast.close_toast()
        toast = Toast()
        toast.show_toast(message, status=status)
        if status in ["syncing", "upload", "download", "bidirectional"]:
            self.active_toast = toast
        else:
            self.active_toast = None

    def set_logged_in_state(self):
        self.client = APIClient(config.get(
            "remote_url"), config.get("api_token"))
        self.main_window.set_view_for_login_state(
            True, config.get("user_email"))
        if config.get("vault_paths"):
            self.restart_all_workers()
        else:
            self.fetch_remote_vaults_and_decide_page()

    def set_logged_out_state(self):
        self.stop_all_workers()
        self.client = None
        self.main_window.set_view_for_login_state(False)

    def handle_login(self, url, email, password):
        self.main_window.set_loading_state('login', True)
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
        self.auth_worker = AuthWorker(
            'register', url, email, password, password2)
        self.auth_thread = QThread()
        self.auth_worker.moveToThread(self.auth_thread)
        self.auth_thread.started.connect(self.auth_worker.run)
        self.auth_worker.finished.connect(self.on_auth_finished)
        self.auth_worker.finished.connect(self.auth_thread.quit)
        self.auth_worker.finished.connect(self.auth_worker.deleteLater)
        self.auth_thread.finished.connect(self.auth_thread.deleteLater)
        self.auth_thread.start()

    def on_auth_finished(self, success, result, email):
        mode = self.auth_worker.mode
        self.main_window.set_loading_state(mode, False)
        if success:
            config.set("api_token", result)
            config.set("user_email", email)
            config.set("remote_url", self.main_window.login_remote_input.text())
            self.set_logged_in_state()
        else:
            self.main_window.show_auth_error(mode, f"操作失败: {result}")

    def handle_logout(self):
        if self.main_window:
            self.main_window.statusBar().showMessage("正在登出，请稍候...", 0)
        self.stop_all_workers()
        config.set("api_token", None)
        config.set("user_email", None)
        self.set_logged_out_state()
        self.tray_icon.set_status("idle", "已登出")
        if self.main_window:
            self.main_window.statusBar().clearMessage()
            self.main_window.show()

    @pyqtSlot(str)  # 槽函数现在只接收一个 path 参数
    def create_new_vault(self, path_str: str):
        """处理新建知识库的请求。"""
        try:
            self.setOverrideCursor(Qt.CursorShape.WaitCursor)

            target_path = Path(path_str)

            if target_path.exists():
                raise ValueError("目标文件夹或文件已存在。")

            # --- 核心修复：从路径中推导出名称 ---
            vault_name = target_path.name

            # 程序负责创建文件夹
            target_path.mkdir(parents=True)

            vault_info = self.client.create_vault(vault_name)
            repo = Repository.initialize(target_path)
            repo.config.set("vault_id", vault_info['id'])
            repo.config.set("remote_url", config.get("remote_url"))

            vault_paths = config.get("vault_paths", [])
            vault_paths.append(path_str)
            config.set("vault_paths", vault_paths)

            self.restart_all_workers()
            self.show_toast(f"知识库 '{vault_name}' 创建成功！", "success")

        except Exception as e:
            CustomMessageBox.show_critical(self.main_window, "创建失败", str(e))
            # 如果创建失败，清理可能已创建的空文件夹
            if 'target_path' in locals() and target_path.exists() and not any(target_path.iterdir()):
                target_path.rmdir()
        finally:
            self.restoreOverrideCursor()

    @pyqtSlot(str, str, str)
    def clone_vault(self, vault_id: str, name: str, local_parent_path: str):
        """处理克隆知识库的请求。"""
        try:
            self.setOverrideCursor(Qt.CursorShape.WaitCursor)

            # --- 核心修复：在这里构建最终路径并创建 ---
            target_path = Path(local_parent_path) / name
            if target_path.exists() and any(target_path.iterdir()):
                raise ValueError(f"目标文件夹 '{target_path}' 已存在且不为空！")

            # Repository.initialize 会负责创建 .kcube 和其父目录
            repo = Repository.initialize(target_path)

            repo.config.set("vault_id", vault_id)
            repo.config.set("remote_url", config.get("remote_url"))
            repo.vault_id = vault_id

            synchronizer = Synchronizer(repo, self.client)
            synchronizer.sync()

            latest_hash = repo.db.get_latest_version_hash()
            if latest_hash:
                repo.restore(latest_hash)

            vault_paths = config.get("vault_paths", [])
            vault_paths.append(str(target_path))
            config.set("vault_paths", vault_paths)
            self.restart_all_workers()

        except Exception as e:
            CustomMessageBox.show_critical(self.main_window, "克隆失败", str(e))
        finally:
            self.restoreOverrideCursor()

    def fetch_remote_vaults_and_decide_page(self):
        try:
            vaults = self.client.list_vaults()
            if vaults:
                self.main_window.populate_vault_selection(vaults)
                self.main_window.switch_to_page("vault_selection")
            else:
                self.main_window.switch_to_page("empty_state")
        except Exception as e:
            CustomMessageBox.show_critical(
                self.main_window, "错误", f"无法从云端获取知识库列表: {str(e)}")
            self.handle_logout()

    def handle_link_request(self, path, vault_id):
        try:
            self.setOverrideCursor(Qt.CursorShape.WaitCursor)
            self.client.get_vault_details(vault_id)
            vault_paths = config.get("vault_paths", [])
            if path in vault_paths:
                CustomMessageBox.show_information(
                    self.main_window, "提示", "这个保险库已在监控列表中。")
                return
            vault_paths.append(path)
            config.set("vault_paths", vault_paths)
            self.restart_all_workers()
            self.show_toast("本地仓库关联成功！", "success")
        except APIError as e:
            if e.status_code == 404:
                reply = CustomMessageBox.show_question(self.main_window, "云端记录不存在",
                                                       f"云端没有找到 ID 为\n{vault_id}\n的仓库记录。\n\n"
                                                       "你想使用此本地仓库的内容，在云端创建一个新的仓库吗？")
                if reply:
                    self.create_vault_from_local(
                        path, Path(path).name, vault_id)
            else:
                CustomMessageBox.show_critical(
                    self.main_window, "关联失败", f"验证云端仓库时出错：\n{str(e)}")
        finally:
            self.restoreOverrideCursor()

    def create_vault_from_local(self, path, name, vault_id):
        try:
            self.setOverrideCursor(Qt.CursorShape.WaitCursor)
            self.client.create_vault(name, vault_id=vault_id)
            vault_paths = config.get("vault_paths", [])
            vault_paths.append(path)
            config.set("vault_paths", vault_paths)
            self.restart_all_workers()
            self.show_toast(f"'{name}' 已成功关联到云端！", "success")
        except Exception as e:
            CustomMessageBox.show_critical(self.main_window, "创建失败", str(e))
        finally:
            self.restoreOverrideCursor()

    def handle_delete_vault(self, vault_id: str, name: str):
        if CustomMessageBox.show_question(self.main_window, "确认删除", f"你确定要从云端**永久删除**知识库 '{name}' 吗？\n此操作无法恢复。"):
            if self.confirm_password():
                try:
                    self.setOverrideCursor(Qt.CursorShape.WaitCursor)
                    self.client.delete_vault(vault_id)
                    vault_paths = config.get("vault_paths", [])
                    path_to_remove = None
                    for p_str in vault_paths:
                        local_conf = ConfigManager(
                            Path(p_str) / ".kcube" / "config.json")
                        if local_conf.get("vault_id") == vault_id:
                            path_to_remove = p_str
                            break
                    if path_to_remove:
                        vault_paths.remove(path_to_remove)
                        config.set("vault_paths", vault_paths)
                    self.restart_all_workers()
                    self.show_toast(f"云端仓库 '{name}' 已删除", "success")
                except Exception as e:
                    CustomMessageBox.show_critical(
                        self.main_window, "删除失败", str(e))
                finally:
                    self.restoreOverrideCursor()

    def confirm_password(self):
        if self.is_auth_cached():
            return True
        dialog = PasswordConfirmDialog(
            "安全确认", "请输入你的账户密码以继续此操作。", self.main_window)
        if dialog.exec():
            password = dialog.get_password()
            # (Simplified password check)
            if password:
                self.last_auth_time = time.time()
                return True
        return False

    def is_auth_cached(self):
        return time.time() - self.last_auth_time < self.auth_cache_duration

    def restart_all_workers(self):
        self.stop_all_workers()
        if self.main_window:
            self.main_window.load_vaults_to_list()
        vault_paths = config.get("vault_paths", [])
        if not vault_paths:
            self.tray_icon.set_status("idle", "无保险库被监控。")
            if self.client:
                self.fetch_remote_vaults_and_decide_page()
            return
        self.main_window.switch_to_page("vault")
        for path in vault_paths:
            self.start_worker(path)
        self.tray_icon.set_status("idle", f"正在监控 {len(vault_paths)} 个保险库。")

    def start_worker(self, vault_path: str):
        if not self.client:
            return
        thread = QThread()
        worker = Worker(vault_path, self.client)
        worker.moveToThread(thread)
        worker.validation_finished.connect(
            self.main_window.update_vault_status)
        worker.sync_started.connect(self.on_sync_started)
        worker.sync_finished.connect(self.on_sync_finished)
        worker.sync_error.connect(self.on_sync_error)
        worker.finished.connect(thread.quit)
        thread.finished.connect(lambda: self.on_worker_finished(vault_path))
        thread.started.connect(worker.run)
        thread.start()
        self.worker_pool[vault_path] = {'worker': worker, 'thread': thread}

    def on_sync_started(self, vault_path: str, direction: str):
        self.main_window.update_vault_status(vault_path, direction, "")
        message_map = {"upload": "正在上传...",
                       "download": "正在下载...", "bidirectional": "正在双向同步..."}
        self.show_toast(message_map.get(direction, "正在同步..."), direction)

    def on_sync_finished(self, vault_path: str, result: SyncResult):
        message = "已是最新"
        if result.has_changes:
            msg_parts = []
            if result.versions_uploaded > 0:
                msg_parts.append(f"上传 {result.versions_uploaded} 项")
            if result.versions_downloaded > 0:
                msg_parts.append(f"下载 {result.versions_downloaded} 项")
            message = " & ".join(msg_parts)
        self.main_window.update_vault_status(vault_path, "success", message)
        self.show_toast(message, "success")

    def on_sync_error(self, vault_path: str, error_message: str):
        self.main_window.update_vault_status(
            vault_path, "error", error_message)
        self.show_toast(f"同步失败: {error_message}", "error")

    def on_worker_finished(self, vault_path):
        if vault_path in self.worker_pool:
            del self.worker_pool[vault_path]
            print(
                f"Worker for {Path(vault_path).name} has finished and been cleaned up.")

    @pyqtSlot(str)
    def trigger_manual_sync(self, vault_path: str):
        if vault_path in self.worker_pool:
            worker_instance = self.worker_pool[vault_path]['worker']
            if worker_instance:
                worker_instance._manual_sync_request.emit()
        else:
            if self.main_window:
                self.main_window.update_vault_status(
                    vault_path, "error", "监控进程未运行，无法同步。")

    def stop_all_workers(self):
        running_threads = [data['thread']
                           for data in self.worker_pool.values() if data['thread'].isRunning()]
        if not running_threads:
            return

        loop = QEventLoop()
        self.stopped_counter = 0

        @pyqtSlot()
        def on_thread_finished():
            self.stopped_counter += 1
            if self.stopped_counter >= len(running_threads):
                loop.quit()

        for thread in running_threads:
            thread.finished.connect(on_thread_finished)

        for path, worker_data in list(self.worker_pool.items()):
            if worker_data['thread'].isRunning():
                worker_data['worker'].stop()

        loop.exec()
        self.worker_pool.clear()
        print("所有 worker 已被停止和清理。")

    def quit_app(self):
        print("正在退出 K-Cube 守护进程...")
        self.stop_all_workers()
        print("所有线程已停止，安全退出。")
        self.quit()


if __name__ == "__main__":
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = KCubeApplication(sys.argv)
    sys.exit(app.exec())
