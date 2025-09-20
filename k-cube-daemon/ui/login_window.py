# k-cube-daemon/ui/login_window.py
from PyQt6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QLabel, QMessageBox,
                             QHBoxLayout, QStackedWidget, QPushButton, QSpacerItem,
                             QSizePolicy, QFormLayout, QFrame)
from PyQt6.QtCore import pyqtSignal, Qt, QThread, QObject
from PyQt6.QtGui import QPainter, QBrush, QPen, QFontDatabase

from config_manager import config
from k_cube.client import APIClient, APIError
from ui.theme import Color, Font, Size
from .components.styled_button import StyledButton
from .components.styled_line_edit import StyledLineEdit
from .components.title_bar import TitleBar
import qtawesome as qta

# --- 后台认证任务 Worker ---


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
                # 注册成功后自动为用户登录
                token = client.login(self.email, self.password)
                self.finished.emit(True, token)
        except Exception as e:
            self.finished.emit(False, str(e))

# --- 登录/注册主窗口 ---


class LoginWindow(QDialog):
    login_successful = pyqtSignal()
    logout_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.title_bar = TitleBar(self)
        self.title_bar.setTitle("K-Cube 全局设置")

        self.stacked_widget = QStackedWidget(self)
        self.login_widget = self._create_login_widget()
        self.register_widget = self._create_register_widget()
        self.stacked_widget.addWidget(self.login_widget)
        self.stacked_widget.addWidget(self.register_widget)

        self.background_frame = QFrame(self)
        self.background_frame.setObjectName("backgroundFrame")
        self.background_frame.setStyleSheet(f"""
            #backgroundFrame {{
                background-color: {Color.BACKGROUND.name()};
                border: 1px solid {Color.WINDOW_BORDER.name()};
                border-radius: 12px;
            }}
        """)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(1, 1, 1, 1)
        self.main_layout.setSpacing(0)

        frame_layout = QVBoxLayout(self.background_frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)
        frame_layout.addWidget(self.title_bar)
        frame_layout.addWidget(self.stacked_widget)

        self.main_layout.addWidget(self.background_frame)

        self.setFixedSize(420, 480)
        self.logout_button = None  # 初始化登出按钮引用

    def _create_login_widget(self):
        widget = QWidget()
        widget.setStyleSheet("background-color: transparent;")

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(35, 10, 35, 30)

        title = QLabel("欢迎回来")
        title.setStyleSheet(Font.TITLE)

        form_layout = QFormLayout()
        form_layout.setVerticalSpacing(20)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.login_remote_input = StyledLineEdit(
            placeholder_text="http://127.0.0.1:5000")
        self.login_remote_input.setText(config.get("remote_url", ""))
        self.login_remote_input.setMinimumHeight(Size.INPUT_HEIGHT)

        self.login_email_input = StyledLineEdit(placeholder_text="请输入邮箱")
        self.login_email_input.setMinimumHeight(Size.INPUT_HEIGHT)

        self.login_password_input = StyledLineEdit(is_password=True)
        self.login_password_input.setMinimumHeight(Size.INPUT_HEIGHT)

        remote_label = QLabel("远程仓库 URL:")
        remote_label.setStyleSheet(Font.FORM_LABEL)
        email_label = QLabel("邮箱:")
        email_label.setStyleSheet(Font.FORM_LABEL)
        password_label = QLabel("密码:")
        password_label.setStyleSheet(Font.FORM_LABEL)

        form_layout.addRow(remote_label, self.login_remote_input)
        form_layout.addRow(email_label, self.login_email_input)
        form_layout.addRow(password_label, self.login_password_input)

        self.login_error_label = QLabel("")
        self.login_error_label.setStyleSheet(
            f"color: {Color.RED.name()}; {Font.CAPTION}")
        self.login_error_label.setVisible(False)
        self.login_error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.login_error_label.setFixedHeight(20)

        self.login_button = StyledButton("登录", is_primary=True)
        self.login_button.setMinimumHeight(Size.BUTTON_HEIGHT)
        self.login_button.clicked.connect(self.attempt_login)

        switch_button = QPushButton("还没有账户？ 立即注册")
        switch_button.setStyleSheet(
            f"background: transparent; border: none; color: {Color.PRIMARY.name()}; {Font.BODY}")
        switch_button.setCursor(Qt.CursorShape.PointingHandCursor)
        switch_button.clicked.connect(lambda: self.switch_page(1))

        layout.addSpacerItem(QSpacerItem(
            20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacerItem(QSpacerItem(
            20, 30, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))
        layout.addLayout(form_layout)
        layout.addWidget(self.login_error_label)
        layout.addStretch()
        layout.addWidget(self.login_button)
        layout.addSpacerItem(QSpacerItem(
            20, 15, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))
        layout.addWidget(switch_button, alignment=Qt.AlignmentFlag.AlignCenter)

        return widget

    def _create_register_widget(self):
        widget = QWidget()
        widget.setStyleSheet("background-color: transparent;")

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(35, 10, 35, 30)

        title = QLabel("创建新账户")
        title.setStyleSheet(Font.TITLE)

        form_layout = QFormLayout()
        form_layout.setVerticalSpacing(20)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.reg_email_input = StyledLineEdit(placeholder_text="请输入邮箱")
        self.reg_email_input.setMinimumHeight(Size.INPUT_HEIGHT)

        self.reg_password_input = StyledLineEdit(is_password=True)
        self.reg_password_input.setMinimumHeight(Size.INPUT_HEIGHT)

        self.reg_password2_input = StyledLineEdit(
            placeholder_text="请再次输入密码", is_password=True)
        self.reg_password2_input.setMinimumHeight(Size.INPUT_HEIGHT)

        email_label = QLabel("邮箱:")
        email_label.setStyleSheet(Font.FORM_LABEL)
        password_label = QLabel("密码:")
        password_label.setStyleSheet(Font.FORM_LABEL)
        password2_label = QLabel("确认密码:")
        password2_label.setStyleSheet(Font.FORM_LABEL)

        form_layout.addRow(email_label, self.reg_email_input)
        form_layout.addRow(password_label, self.reg_password_input)
        form_layout.addRow(password2_label, self.reg_password2_input)

        self.reg_error_label = QLabel("")
        self.reg_error_label.setStyleSheet(
            f"color: {Color.RED.name()}; {Font.CAPTION}")
        self.reg_error_label.setVisible(False)
        self.reg_error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.reg_error_label.setFixedHeight(20)

        self.register_button = StyledButton("注册并登录", is_primary=True)
        self.register_button.setMinimumHeight(Size.BUTTON_HEIGHT)
        self.register_button.clicked.connect(self.attempt_register)

        switch_button = QPushButton("已有账户？ 返回登录")
        switch_button.setStyleSheet(
            f"background: transparent; border: none; color: {Color.PRIMARY.name()}; {Font.BODY}")
        switch_button.setCursor(Qt.CursorShape.PointingHandCursor)
        switch_button.clicked.connect(lambda: self.switch_page(0))

        layout.addSpacerItem(QSpacerItem(
            20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacerItem(QSpacerItem(
            20, 30, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))
        layout.addLayout(form_layout)
        layout.addWidget(self.reg_error_label)
        layout.addStretch()
        layout.addWidget(self.register_button)
        layout.addSpacerItem(QSpacerItem(
            20, 15, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))
        layout.addWidget(switch_button, alignment=Qt.AlignmentFlag.AlignCenter)

        return widget

    def add_logout_button(self):
        """如果用户已登录，动态地在登录页面添加一个登出按钮。"""
        if config.get("api_token") and not self.logout_button:
            self.logout_button = StyledButton("登出当前账户", is_primary=False)
            self.logout_button.setMinimumHeight(Size.BUTTON_HEIGHT)
            self.logout_button.clicked.connect(self.logout_requested)

            # 插入到主登录按钮之前，并增加一个间隔
            login_layout = self.login_widget.layout()
            spacer = QSpacerItem(
                20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            login_layout.insertItem(
                login_layout.indexOf(self.login_button), spacer)
            login_layout.insertWidget(login_layout.indexOf(
                self.login_button), self.logout_button)

            self.setFixedSize(420, 540)  # 增加高度以容纳新按钮

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
            self.original_button_text = button.text()
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
