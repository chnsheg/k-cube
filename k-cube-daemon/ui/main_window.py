# k-cube-daemon/ui/main_window.py
# (替换完整内容)
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QLabel,
                             QListWidget, QListWidgetItem, QFileDialog, QHBoxLayout,
                             QMessageBox, QInputDialog, QFrame, QStackedWidget,
                             QPushButton, QSpacerItem, QSizePolicy, QFormLayout)
from PyQt6.QtCore import pyqtSignal, Qt, QSize
from pathlib import Path

from config_manager import config
from .components.styled_button import StyledButton
from .components.styled_line_edit import StyledLineEdit
from .components.title_bar import TitleBar
from .components.vault_list_item import VaultListItem
from .theme import Color, Font, Size, QSS, STYLESHEET
import qtawesome as qta


class MainWindow(QMainWindow):
    # --- 定义所有信号 ---
    login_request = pyqtSignal(str, str, str)  # url, email, password
    # url, email, password, password2
    register_request = pyqtSignal(str, str, str, str)
    logout_request = pyqtSignal()
    vaults_changed = pyqtSignal()
    new_vault_request = pyqtSignal(str, str)  # path, name
    manual_sync_request = pyqtSignal(str)    # path

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.title_bar = TitleBar(self)
        self.title_bar.setTitle("K-Cube")

        # --- 核心：页面堆栈 ---
        self.stacked_widget = QStackedWidget(self)
        self.vault_page = self._create_vault_page()
        self.login_page = self._create_login_page()
        self.register_page = self._create_register_page()

        self.stacked_widget.addWidget(self.vault_page)
        self.stacked_widget.addWidget(self.login_page)
        self.stacked_widget.addWidget(self.register_page)

        # --- 背景框架 ---
        self.background_frame = QFrame(self)
        self.background_frame.setObjectName("backgroundFrame")
        self.background_frame.setStyleSheet(f"""
            #backgroundFrame {{
                background-color: {Color.BACKGROUND.name()};
                border: 1px solid {Color.WINDOW_BORDER.name()};
                border-radius: 12px;
            }}
        """)

        frame_layout = QVBoxLayout(self.background_frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)
        frame_layout.addWidget(self.title_bar)
        frame_layout.addWidget(self.stacked_widget)

        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(1, 1, 1, 1)
        self.main_layout.addWidget(self.background_frame)

        central_widget = QWidget()
        central_widget.setLayout(self.main_layout)
        self.setCentralWidget(central_widget)

        self.setMinimumSize(500, 550)

    def switch_to_page(self, page_name: str):
        page_map = {"vault": self.vault_page,
                    "login": self.login_page, "register": self.register_page}
        widget_to_show = page_map.get(page_name)
        if widget_to_show:
            self.stacked_widget.setCurrentWidget(widget_to_show)

    def _create_vault_page(self):
        page = QWidget()
        page.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 10, 20, 20)
        layout.setSpacing(15)

        # --- 用户状态栏 ---
        status_bar_layout = QHBoxLayout()
        self.user_email_label = QLabel()
        self.user_email_label.setStyleSheet(QSS.USER_STATUS)
        self.logout_button_vault_page = QPushButton("登出")  # 使用独立实例
        self.logout_button_vault_page.setStyleSheet(
            f"background: transparent; border: none; color: {Color.PRIMARY.name()}; {Font.BODY}")
        self.logout_button_vault_page.setCursor(
            Qt.CursorShape.PointingHandCursor)
        self.logout_button_vault_page.clicked.connect(self.logout_request)
        status_bar_layout.addWidget(QLabel("已登录为:"))
        status_bar_layout.addWidget(self.user_email_label)
        status_bar_layout.addStretch()
        status_bar_layout.addWidget(self.logout_button_vault_page)
        layout.addLayout(status_bar_layout)

        # --- 列表 ---
        list_label = QLabel("正在监控的知识库:")
        list_label.setStyleSheet(
            f"{Font.SUBTITLE} color: {Color.TEXT_SECONDARY.name()};")
        self.vault_list = QListWidget()
        self.vault_list.setStyleSheet(STYLESHEET)  # 应用全局样式
        # --- 核心修改：设置列表项之间的间距 ---
        self.vault_list.setSpacing(8)
        layout.addWidget(list_label)
        layout.addWidget(self.vault_list)

        # --- 按钮栏 ---
        button_layout = QHBoxLayout()
        new_button = StyledButton("新建知识库", is_primary=False)
        add_button = StyledButton("添加已有", is_primary=True)
        remove_button = StyledButton("移除选中", is_primary=False)
        button_layout.addWidget(new_button)
        button_layout.addWidget(add_button)
        button_layout.addWidget(remove_button)
        new_button.clicked.connect(self.new_vault)
        add_button.clicked.connect(self.add_vault)
        remove_button.clicked.connect(self.remove_vault)
        self.vault_list.currentItemChanged.connect(
            self.on_list_selection_changed)
        layout.addLayout(button_layout)

        return page

    def on_list_selection_changed(self, current: QListWidgetItem, previous: QListWidgetItem):
        """处理列表选中项的变化，更新卡片样式。"""
        if previous:
            widget = self.vault_list.itemWidget(previous)
            if isinstance(widget, VaultListItem):
                widget.set_selected(False)

        if current:
            widget = self.vault_list.itemWidget(current)
            if isinstance(widget, VaultListItem):
                widget.set_selected(True)

    def _create_login_page(self):
        page = QWidget()
        page.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(page)
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
        form_layout.addRow(
            QLabel("远程仓库 URL:", styleSheet=Font.FORM_LABEL), self.login_remote_input)
        form_layout.addRow(
            QLabel("邮箱:", styleSheet=Font.FORM_LABEL), self.login_email_input)
        form_layout.addRow(
            QLabel("密码:", styleSheet=Font.FORM_LABEL), self.login_password_input)
        self.login_error_label = QLabel("")
        self.login_error_label.setStyleSheet(
            f"color: {Color.RED.name()}; {Font.CAPTION}")
        self.login_error_label.setVisible(False)
        self.login_error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.login_error_label.setFixedHeight(20)
        self.login_button = StyledButton("登录", is_primary=True)
        self.login_button.setMinimumHeight(Size.BUTTON_HEIGHT)
        self.login_button.clicked.connect(lambda: self.login_request.emit(
            self.login_remote_input.text(), self.login_email_input.text(), self.login_password_input.text()))
        switch_button = QPushButton("还没有账户？ 立即注册")
        switch_button.setStyleSheet(
            f"background: transparent; border: none; color: {Color.PRIMARY.name()}; {Font.BODY}")
        switch_button.setCursor(Qt.CursorShape.PointingHandCursor)
        switch_button.clicked.connect(lambda: self.switch_to_page("register"))
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
        return page

    def _create_register_page(self):
        page = QWidget()
        page.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(page)
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
        form_layout.addRow(
            QLabel("邮箱:", styleSheet=Font.FORM_LABEL), self.reg_email_input)
        form_layout.addRow(
            QLabel("密码:", styleSheet=Font.FORM_LABEL), self.reg_password_input)
        form_layout.addRow(
            QLabel("确认密码:", styleSheet=Font.FORM_LABEL), self.reg_password2_input)
        self.reg_error_label = QLabel("")
        self.reg_error_label.setStyleSheet(
            f"color: {Color.RED.name()}; {Font.CAPTION}")
        self.reg_error_label.setVisible(False)
        self.reg_error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.reg_error_label.setFixedHeight(20)
        self.register_button = StyledButton("注册并登录", is_primary=True)
        self.register_button.setMinimumHeight(Size.BUTTON_HEIGHT)
        self.register_button.clicked.connect(lambda: self.register_request.emit(self.login_remote_input.text(
        ), self.reg_email_input.text(), self.reg_password_input.text(), self.reg_password2_input.text()))
        switch_button = QPushButton("已有账户？ 返回登录")
        switch_button.setStyleSheet(
            f"background: transparent; border: none; color: {Color.PRIMARY.name()}; {Font.BODY}")
        switch_button.setCursor(Qt.CursorShape.PointingHandCursor)
        switch_button.clicked.connect(lambda: self.switch_to_page("login"))
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
        return page

    # --- UI 状态切换方法 ---
    def set_loading_state(self, mode, is_loading):
        page = self.login_page if mode == 'login' else self.register_page
        button = page.findChild(StyledButton)
        if button:
            if is_loading:
                button.setText("请稍候...")
                button.setEnabled(False)
            else:
                button.setText("登录" if mode == 'login' else "注册并登录")
                button.setEnabled(True)

    def show_auth_error(self, mode, message):
        label = self.login_error_label if mode == 'login' else self.reg_error_label
        label.setText(message)
        label.setVisible(True)

    def set_user_status(self, email: str or None):
        if email:
            self.user_email_label.setText(email)
        else:
            self.user_email_label.setText("未登录")

    # --- 业务逻辑方法 ---
    def load_vaults_to_list(self):
        # 暂时断开信号，防止在填充列表时触发不必要的回调
        self.vault_list.currentItemChanged.disconnect(
            self.on_list_selection_changed)

        self.vault_list.clear()
        vault_paths = config.get("vault_paths", [])
        item_height = 65

        for path in vault_paths:
            list_item_widget = VaultListItem(path, self)
            list_item_widget.sync_requested.connect(
                lambda p=path: self.manual_sync_request.emit(p))
            list_widget_item = QListWidgetItem(self.vault_list)
            list_widget_item.setSizeHint(
                QSize(list_item_widget.width(), item_height))
            self.vault_list.addItem(list_widget_item)
            self.vault_list.setItemWidget(list_widget_item, list_item_widget)

        # 重新连接信号
        self.vault_list.currentItemChanged.connect(
            self.on_list_selection_changed)
        # 手动触发一次，以高亮显示第一项（如果存在）
        if self.vault_list.count() > 0:
            self.vault_list.setCurrentRow(0)
            self.on_list_selection_changed(self.vault_list.currentItem(), None)

    def new_vault(self):
        path = QFileDialog.getExistingDirectory(self, "选择一个空文件夹来创建新知识库")
        if not path:
            return
        if any(Path(path).iterdir()):
            QMessageBox.critical(self, "错误", "所选文件夹不为空！")
            return
        name, ok = QInputDialog.getText(self, "新建知识库", "请输入新知识库的名称:")
        if ok and name:
            self.new_vault_request.emit(path, name)

    def add_vault(self):
        path = QFileDialog.getExistingDirectory(self, "选择一个已初始化的 K-Cube 保险库")
        if path:
            vault_paths = config.get("vault_paths", [])
            if path in vault_paths:
                QMessageBox.warning(self, "重复", "这个保险库已在监控列表中。")
                return
            if not (Path(path) / ".kcube").exists():
                QMessageBox.critical(self, "错误", "所选文件夹不是有效的 K-Cube 保险库。")
                return
            vault_paths.append(path)
            config.set("vault_paths", vault_paths)
            self.load_vaults_to_list()
            self.vaults_changed.emit()

    def remove_vault(self):
        """从监控列表中移除选中的保险库。"""
        current_item = self.vault_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "提示", "请先选择一个要移除的保险库。")
            return

        widget = self.vault_list.itemWidget(current_item)
        if not widget:
            return
        path_to_remove = widget.path

        reply = QMessageBox.question(
            self, "确认", f"确定要停止监控\n{path_to_remove}\n吗？")
        if reply == QMessageBox.StandardButton.Yes:
            vault_paths = config.get("vault_paths", [])
            if path_to_remove in vault_paths:
                vault_paths.remove(path_to_remove)
                config.set("vault_paths", vault_paths)
                # --- 核心修复：直接调用 load_vaults_to_list 刷新 ---
                self.load_vaults_to_list()
                self.vaults_changed.emit()

    def update_vault_status(self, vault_path, status, message):
        """根据路径查找列表项并更新其状态和消息。"""
        for i in range(self.vault_list.count()):
            item = self.vault_list.item(i)
            widget = self.vault_list.itemWidget(item)
            if widget and widget.path == vault_path:
                # --- 核心修复：传递 message ---
                widget.set_status(status, message)
                break

    def closeEvent(self, event):
        self.hide()
        event.ignore()
