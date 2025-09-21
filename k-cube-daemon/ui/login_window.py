# k-cube-daemon/ui/login_window.py
# (替换完整内容)
from PyQt6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QLabel, QMessageBox,
                             QHBoxLayout, QStackedWidget, QPushButton)
from PyQt6.QtCore import pyqtSignal, Qt, QThread, QObject, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPainter, QBrush, QPen, QFontDatabase

from config_manager import config
from k_cube.client import APIClient, APIError
from ui.theme import Color, Font, Size
from .components.styled_button import StyledButton
from .components.styled_line_edit import StyledLineEdit
from .components.title_bar import TitleBar
import qtawesome as qta

# --- 后台任务 (可以移到独立文件) ---


class AuthWorker(QObject):
    finished = pyqtSignal(bool, str)  # success, message/token

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
                self.finished.emit(True, token)
            elif self.mode == 'register':
                if self.password != self.password2:
                    raise ValueError("两次输入的密码不一致。")
                client.register(self.email, self.password)
                # 注册成功后自动登录
                token = client.login(self.email, self.password)
                self.finished.emit(True, token)
        except Exception as e:
            self.finished.emit(False, str(e))

# --- 主窗口 ---


class LoginWindow(QDialog):
    login_successful = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.Attribute.WA_TranslucentBackground)

        self.title_bar = TitleBar(self)
        self.title_bar.setTitle("K-Cube 全局设置")

        self.stacked_widget = QStackedWidget(self)
        self.login_widget = self._create_login_widget()
        self.register_widget = self._create_register_widget()
        self.stacked_widget.addWidget(self.login_widget)
        self.stacked_widget.addWidget(self.register_widget)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.main_layout.addWidget(self.title_bar)
        self.main_layout.addWidget(self.stacked_widget)

        self.setFixedSize(400, 380)  # 增加高度以容纳更多内容

    def _create_login_widget(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(30, 20, 30, 30)  # 增加边距
        layout.setSpacing(12)  # 增加间距

        title = QLabel("欢迎回来")
        title.setStyleSheet(Font.TITLE)

        self.login_remote_input = StyledLineEdit(
            placeholder_text="http://127.0.0.1:5000")
        self.login_remote_input.setText(config.get("remote_url", ""))
        self.login_remote_input.setMinimumHeight(Size.INPUT_HEIGHT)

        self.login_email_input = StyledLineEdit(placeholder_text="请输入邮箱")
        self.login_email_input.setMinimumHeight(Size.INPUT_HEIGHT)

        self.login_password_input = StyledLineEdit(is_password=True)
        self.login_password_input.setMinimumHeight(Size.INPUT_HEIGHT)

        self.login_error_label = QLabel("")
        self.login_error_label.setStyleSheet(
            f"color: {Color.RED.name()}; {Font.CAPTION}")
        self.login_error_label.setVisible(False)

        self.login_button = StyledButton("登录", is_primary=True)
        self.login_button.setMinimumHeight(Size.BUTTON_HEIGHT)
        self.login_button.clicked.connect(self.attempt_login)

        switch_button = QPushButton("还没有账户？ 立即注册")
        switch_button.setStyleSheet(
            f"background: transparent; border: none; color: {Color.PRIMARY.name()}; {Font.BODY}")
        switch_button.setCursor(Qt.CursorShape.PointingHandCursor)
        switch_button.clicked.connect(lambda: self.switch_page(1))

        layout.addWidget(title)
        layout.addSpacing(20)  # 增加额外间距
        layout.addWidget(QLabel("远程仓库 URL:"))
        layout.addWidget(self.login_remote_input)
        layout.addWidget(QLabel("邮箱:"))
        layout.addWidget(self.login_email_input)
        layout.addWidget(QLabel("密码:"))
        layout.addWidget(self.login_password_input)
        layout.addWidget(self.login_error_label,
                         alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()
        layout.addWidget(self.login_button)
        layout.addWidget(switch_button, alignment=Qt.AlignmentFlag.AlignCenter)

        return widget

    def _create_register_widget(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(30, 20, 30, 30)
        layout.setSpacing(12)

        title = QLabel("创建新账户")
        title.setStyleSheet(Font.TITLE)

        self.reg_email_input = StyledLineEdit(placeholder_text="请输入邮箱")
        self.reg_email_input.setMinimumHeight(Size.INPUT_HEIGHT)

        self.reg_password_input = StyledLineEdit(is_password=True)
        self.reg_password_input.setMinimumHeight(Size.INPUT_HEIGHT)

        self.reg_password2_input = StyledLineEdit(
            placeholder_text="请再次输入密码", is_password=True)
        self.reg_password2_input.setMinimumHeight(Size.INPUT_HEIGHT)

        self.reg_error_label = QLabel("")
        self.reg_error_label.setStyleSheet(
            f"color: {Color.RED.name()}; {Font.CAPTION}")
        self.reg_error_label.setVisible(False)

        self.register_button = StyledButton("注册并登录", is_primary=True)
        self.register_button.setMinimumHeight(Size.BUTTON_HEIGHT)
        self.register_button.clicked.connect(self.attempt_register)

        switch_button = QPushButton("已有账户？ 返回登录")
        switch_button.setStyleSheet(
            f"background: transparent; border: none; color: {Color.PRIMARY.name()}; {Font.BODY}")
        switch_button.setCursor(Qt.CursorShape.PointingHandCursor)
        switch_button.clicked.connect(lambda: self.switch_page(0))

        layout.addWidget(title)
        layout.addSpacing(20)
        layout.addWidget(QLabel("邮箱:"))
        layout.addWidget(self.reg_email_input)
        layout.addWidget(QLabel("密码:"))
        layout.addWidget(self.reg_password_input)
        layout.addWidget(QLabel("确认密码:"))
        layout.addWidget(self.reg_password2_input)
        layout.addWidget(self.reg_error_label,
                         alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()
        layout.addWidget(self.register_button)
        layout.addWidget(switch_button, alignment=Qt.AlignmentFlag.AlignCenter)

        return widget

    def switch_page(self, index):
        self.stacked_widget.setCurrentIndex(index)

    def attempt_login(self):
        remote_url = self.login_remote_input.text().strip()
        email = self.login_email_input.text().strip()
        password = self.login_password_input.text()
        if not all([remote_url, email, password]):
            self.show_error("login", "请填写所有字段。")
            return
        self.start_auth_worker('login', remote_url, email, password)

    def attempt_register(self):
        remote_url = self.login_remote_input.text().strip()  # URL is on the login page
        email = self.reg_email_input.text().strip()
        password = self.reg_password_input.text()
        password2 = self.reg_password2_input.text()
        if not all([remote_url, email, password, password2]):
            self.show_error("register", "请填写所有字段。")
            return
        self.start_auth_worker('register', remote_url,
                               email, password, password2)

    def start_auth_worker(self, mode, remote_url, email, password, password2=None):
        self.set_loading_state(mode, True)
        self.worker = AuthWorker(mode, remote_url, email, password, password2)
        self.thread = QThread()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_auth_finished)
        # ... (thread cleanup) ...
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def on_auth_finished(self, success, result):
        mode = self.worker.mode
        self.set_loading_state(mode, False)
        if success:
            remote_url = self.login_remote_input.text().strip()
            config.set("remote_url", remote_url)
            config.set("api_token", result)
            self.login_successful.emit()
            self.accept()
        else:
            self.show_error(mode, f"操作失败: {result}")

    def set_loading_state(self, mode, is_loading):
        button = self.login_button if mode == 'login' else self.register_button
        if is_loading:
            button.setText("请稍候...")
            button.setEnabled(False)
        else:
            button.setText("登录" if mode == 'login' else "注册并登录")
            button.setEnabled(True)

    def show_error(self, mode, message):
        label = self.login_error_label if mode == 'login' else self.reg_error_label
        label.setText(message)
        label.setVisible(True)

    def paintEvent(self, event):
        # ... (paintEvent 保持不变，用于绘制窗口背景和边框) ...
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        brush = QBrush(Color.BACKGROUND)
        pen = QPen(Color.WINDOW_BORDER, 1)
        painter.setPen(pen)
        painter.setBrush(brush)
        rect = self.rect()
        painter.drawRoundedRect(
            rect.x(), rect.y(), rect.width()-1, rect.height()-1, 12, 12)
