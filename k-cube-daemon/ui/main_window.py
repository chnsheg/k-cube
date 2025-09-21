# k-cube-daemon/ui/main_window.py
# (替换完整内容)
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QLabel,
                             QListWidget, QListWidgetItem, QFileDialog, QHBoxLayout,
                             QMessageBox, QInputDialog, QFrame, QStackedWidget,
                             QPushButton, QSpacerItem, QSizePolicy, QFormLayout, QGridLayout, QScrollArea)
from PyQt6.QtCore import pyqtSignal, Qt, QSize, QSignalBlocker
from pathlib import Path

from config_manager import config
from .components.styled_button import StyledButton
from .components.styled_line_edit import StyledLineEdit
from .components.title_bar import TitleBar
from .components.vault_list_item import VaultListItem
from .theme import Color, Font, Size, QSS, STYLESHEET
import qtawesome as qta
from .components.toast import Toast  # 确保导入

from .components.vault_card import VaultCard
from typing import Optional
from .components.flow_layout import FlowLayout  # 导入 FlowLayout
import config_manager


class MainWindow(QMainWindow):
    # --- 定义所有信号 ---
    login_request = pyqtSignal(str, str, str)  # url, email, password
    # url, email, password, password2
    register_request = pyqtSignal(str, str, str, str)
    logout_request = pyqtSignal()
    vaults_changed = pyqtSignal()
    new_vault_request = pyqtSignal(str)  # path
    manual_sync_request = pyqtSignal(str)    # path
    clone_request = pyqtSignal(str, str, str)  # vault_id, name, local_path
    manage_cloud_request = pyqtSignal()
    link_request = pyqtSignal(str, str)  # 新增关联信号
    delete_vault_request = pyqtSignal(str)
    delete_vault_request = pyqtSignal(str, str)  # vault_id, vault_name

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.vault_selection_page = self._create_vault_selection_page()
        self.empty_state_page = self._create_empty_state_page()

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
        self.stacked_widget.addWidget(self.vault_selection_page)
        self.stacked_widget.addWidget(self.empty_state_page)

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
        self.manage_cloud_button.clicked.connect(self.manage_cloud_request)

        central_widget = QWidget()
        central_widget.setLayout(self.main_layout)
        self.setCentralWidget(central_widget)

        self.setMinimumSize(720, 640)

    def switch_to_page(self, page_name: str):
        """
        一个强力的、能确保页面切换成功的方法。
        """
        page_map = {
            "vault": self.vault_page, "login": self.login_page,
            "register": self.register_page, "vault_selection": self.vault_selection_page,
            "empty_state": self.empty_state_page
        }

        target_widget = page_map.get(page_name)
        if not target_widget:
            print(f"警告：尝试切换到一个不存在的页面: {page_name}")
            return

        # --- 核心修复：强制切换 ---
        # 1. 遍历并隐藏所有页面
        for i in range(self.stacked_widget.count()):
            self.stacked_widget.widget(i).setVisible(False)

        # 2. 将目标页面设置为当前页面
        self.stacked_widget.setCurrentWidget(target_widget)

        # 3. 显式地显示目标页面
        target_widget.setVisible(True)

    def set_view_for_login_state(self, is_logged_in: bool, email: Optional[str] = None):
        """
        根据登录状态，原子性地更新整个窗口的UI。
        """
        if is_logged_in:
            # --- 已登录状态 ---
            self.user_email_label.setText(email or "未知用户")
            # 检查是否有本地仓库，决定显示 vault_page 还是 vault_selection_page
            if config.get("vault_paths"):
                self.switch_to_page("vault")
            else:
                # 这个逻辑现在由 app.py 控制，这里只负责显示 vault_page 的容器
                # app.py 会在之后填充它或切换到 selection 页
                self.switch_to_page("vault")
        else:
            # --- 未登录状态 ---
            self.user_email_label.setText("未登录")
            self.switch_to_page("login")

        # 控制 vault_page 中特定按钮的可见性
        self.logout_button_vault_page.setVisible(is_logged_in)
        self.manage_cloud_button.setVisible(is_logged_in)

    def showEvent(self, event):
        """在窗口显示前，再次确认UI状态。"""
        # 这个事件可以确保即使在后台状态已改变，显示时UI也是正确的
        is_logged_in = bool(config.get("api_token"))
        self.set_view_for_login_state(is_logged_in, config.get("user_email"))
        super().showEvent(event)

    def _create_vault_selection_page(self):
        """
        创建一个页面，用于让用户从云端仓库中选择一个进行同步，
        或创建/关联本地仓库。
        """
        page = QWidget()
        page.setStyleSheet("background-color: transparent;")
        main_layout = QVBoxLayout(page)
        main_layout.setContentsMargins(40, 30, 40, 40)

        title = QLabel("设置你的知识库")
        title.setStyleSheet(Font.TITLE)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        cloud_label = QLabel("从云端同步一个知识库")
        cloud_label.setStyleSheet(Font.SUBTITLE)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        # --- 核心修改：确保滚动条应用我们的全局样式 ---
        scroll_area.setStyleSheet(
            f"QScrollArea {{ border: none; background: transparent; }} {STYLESHEET}")

        self.cloud_vaults_widget = QWidget()
        self.flow_layout = FlowLayout(self.cloud_vaults_widget, 10, 25, 25)
        scroll_area.setWidget(self.cloud_vaults_widget)

        # --- 本地操作区域 ---
        local_label = QLabel("或者...")
        local_label.setStyleSheet(
            f"{Font.SUBTITLE} color: {Color.TEXT_SECONDARY.name()};")
        local_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        local_buttons_layout = QHBoxLayout()
        new_button = StyledButton("新建一个全新的知识库", is_primary=False)
        link_button = StyledButton("关联本地已有知识库", is_primary=False)
        new_button.clicked.connect(self.new_vault)
        link_button.clicked.connect(self.link_vault)
        local_buttons_layout.addStretch()
        local_buttons_layout.addWidget(new_button)
        local_buttons_layout.addWidget(link_button)
        local_buttons_layout.addStretch()

        # --- 返回按钮 ---
        self.back_to_vault_page_button = StyledButton(
            "返回本地仓库列表", is_primary=False)
        self.back_to_vault_page_button.clicked.connect(
            lambda: self.switch_to_page("vault"))
        self.back_to_vault_page_button.setVisible(False)  # 默认隐藏

        # --- 最终布局 ---
        main_layout.addWidget(title, 0)  # stretch = 0
        main_layout.addSpacing(25)
        main_layout.addWidget(cloud_label, 0)
        main_layout.addSpacing(10)
        # --- 核心修改：为滚动区域设置拉伸因子 ---
        main_layout.addWidget(scroll_area, 1)  # stretch = 1

        main_layout.addSpacing(20)
        main_layout.addWidget(local_label, 0)
        main_layout.addSpacing(15)
        main_layout.addLayout(local_buttons_layout, 0)
        main_layout.addSpacing(20)
        main_layout.addWidget(self.back_to_vault_page_button,
                              0, Qt.AlignmentFlag.AlignCenter)

        return page

    def populate_vault_selection(self, vaults: list):
        # 清空旧的
        while self.flow_layout.count():
            child = self.flow_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for vault in vaults:
            card = VaultCard(vault['id'], vault['name'])
            card.selected.connect(self.on_vault_card_selected)
            # --- 核心修复：连接删除信号 ---
            card.delete_requested.connect(self.handle_delete_request)
            self.flow_layout.addWidget(card)
        self.flow_layout.update()

        if config.get("vault_paths"):
            self.back_to_vault_page_button.show()
        else:
            self.back_to_vault_page_button.hide()

    def link_vault(self):
        """处理关联本地已有知识库的逻辑。"""
        path = QFileDialog.getExistingDirectory(self, "选择一个已初始化的本地 K-Cube 文件夹")
        if path:
            if not (Path(path) / ".kcube").exists():
                QMessageBox.critical(self, "错误", "所选文件夹不是有效的 K-Cube 保险库。")
                return

            local_repo_config = config_manager.ConfigManager(
                Path(path) / ".kcube" / "config.json")
        vault_id = local_repo_config.get("vault_id")

        # 如果本地就没有 vault_id，说明这是一个纯本地仓库
        if not vault_id:
            reply = QMessageBox.question(self, "关联到云端",
                                         "这是一个纯本地知识库。\n你想在云端为它创建一个新的仓库记录吗？")
            if reply == QMessageBox.StandardButton.Yes:
                self.new_vault_request.emit(path, Path(path).name)  # 复用新建逻辑
            return

        # 如果有 vault_id，发射信号给 app.py 去验证
        self.link_request.emit(path, vault_id)

    def on_vault_card_selected(self, vault_id, name):
        path = QFileDialog.getExistingDirectory(self, f"为 '{name}' 选择一个本地文件夹")
        if path:
            self.clone_request.emit(vault_id, name, path)

    def _create_empty_state_page(self):
        page = QWidget()
        page.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)

        icon_label = QLabel()
        icon_label.setPixmap(
            qta.icon('fa5s.seedling', color=Color.TEXT_SECONDARY.name()).pixmap(60, 60))

        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("开启你的知识之旅")
        title.setStyleSheet(Font.TITLE)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        caption = QLabel("你在云端还没有任何知识库。创建一个，开始记录你的想法吧。")
        caption.setStyleSheet(Font.CAPTION)
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        caption.setWordWrap(True)

        create_button = StyledButton("创建第一个知识库", is_primary=True)
        create_button.clicked.connect(self.new_vault)

        layout.addStretch()
        layout.addWidget(icon_label)
        layout.addWidget(title)
        layout.addWidget(caption)
        layout.addSpacing(20)
        layout.addWidget(create_button)
        layout.addStretch()

        return page

    def _create_vault_page(self):
        page = QWidget()
        page.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 10, 20, 20)
        layout.setSpacing(15)

        # --- 用户状态栏 (升级) ---
        status_bar_layout = QHBoxLayout()
        self.user_email_label = QLabel()
        self.user_email_label.setStyleSheet(QSS.USER_STATUS)

        # --- 新增：管理云端仓库的入口 ---
        self.manage_cloud_button = QPushButton("管理云端仓库")
        self.manage_cloud_button.setStyleSheet(
            f"background: transparent; border: none; color: {Color.PRIMARY.name()}; {Font.BODY}")
        self.manage_cloud_button.setCursor(Qt.CursorShape.PointingHandCursor)
        # 这个信号将在 app.py 中连接

        self.logout_button_vault_page = QPushButton("登出")
        self.logout_button_vault_page.setStyleSheet(
            f"background: transparent; border: none; color: {Color.PRIMARY.name()}; {Font.BODY}")
        self.logout_button_vault_page.setCursor(
            Qt.CursorShape.PointingHandCursor)
        self.logout_button_vault_page.clicked.connect(self.logout_request)

        status_bar_layout.addWidget(QLabel("已登录为:"))
        status_bar_layout.addWidget(self.user_email_label)
        status_bar_layout.addStretch()
        status_bar_layout.addWidget(self.manage_cloud_button)
        status_bar_layout.addSpacing(15)  # 增加间隔
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
        self.manage_cloud_button.clicked.connect(self.manage_cloud_request)
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

    def set_user_status(self, email: Optional[str]):
        is_logged_in = bool(email)

        if is_logged_in:
            self.user_email_label.setText(email)
        else:
            self.user_email_label.setText("未登录")

        self.logout_button_vault_page.setVisible(is_logged_in)
        self.manage_cloud_button.setVisible(is_logged_in)

    # --- 业务逻辑方法 ---
    def load_vaults_to_list(self):
        """
        从配置加载保险库列表并更新UI。
        使用 QSignalBlocker 确保在填充列表时信号被安全地阻塞。
        """
        # --- 核心修复：使用 QSignalBlocker ---
        with QSignalBlocker(self.vault_list):
            self.vault_list.clear()
            vault_paths = config.get("vault_paths", [])
            item_height = 65

            for path in vault_paths:
                list_item_widget = VaultListItem(path, self)

                # --- 核心修复：连接所有需要的信号 ---
                # 使用 lambda 捕获当前循环的变量，这是正确的
                list_item_widget.sync_requested.connect(
                    lambda p=path: self.manual_sync_request.emit(p)
                )

                # 读取本地 vault_id 和 name 以便发射删除信号
                from config_manager import ConfigManager
                from pathlib import Path
                local_repo_config = ConfigManager(
                    Path(path) / ".kcube" / "config.json")
                vault_id = local_repo_config.get("vault_id")
                vault_name = Path(path).name

                list_item_widget.delete_from_cloud_requested.connect(
                    lambda v_id=vault_id, v_name=vault_name: self.handle_delete_request(
                        v_id, v_name)
                )

                list_widget_item = QListWidgetItem(self.vault_list)
                list_widget_item.setSizeHint(
                    QSize(list_item_widget.width(), item_height))
                self.vault_list.addItem(list_widget_item)
                self.vault_list.setItemWidget(
                    list_widget_item, list_item_widget)

        # --- 退出 with 代码块后，信号会自动恢复 ---

        # --- 核心修复：手动设置和触发选中状态 ---
        if self.vault_list.count() > 0:
            # 确保在信号恢复后再设置当前行，这样才会触发 on_list_selection_changed
            self.vault_list.setCurrentRow(0)
        else:
            # 如果列表为空，确保没有残留的“选中”状态
            self.on_list_selection_changed(None, None)

    def handle_delete_request(self, vault_id, name):
        """
        处理来自列表项的删除请求，现在只发射信号，
        复杂的UI逻辑交给 app.py 处理。
        """
        self.delete_vault_request.emit(vault_id, name)

    def new_vault(self):
        """
        处理新建知识库的请求，使用“另存为”模式的对话框。
        """
        # --- 核心修复：使用 getSaveFileName ---
        # 我们用它来获取一个尚不存在的“文件”路径，然后把它当作文件夹路径来用
        # "K-Cube Vault" 是一个虚构的扩展名，只是为了让对话框看起来更友好
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "新建知识库并选择保存位置",
            "",  # 默认起始目录
            "K-Cube Vault (*.kc-vault)"  # 过滤器，实际上我们不会创建这个文件
        )

        if save_path:
            # 用户可能输入了 .kc-vault 后缀，我们需要去掉它
            if save_path.endswith(".kc-vault"):
                save_path = save_path[:-9]

            # 现在 save_path 就是用户期望的、新的、完整的文件夹路径
            # 例如: "E:/k-cube/MyNewVault"
            self.new_vault_request.emit(save_path)

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
                widget.set_status(status)
                if status in ["success", "error"] and message:
                    # --- 核心修改：创建一个新的、无父级的 Toast 实例 ---
                    toast = Toast()
                    toast.show_toast(message, status=status)
                break

    def closeEvent(self, event):
        self.hide()
        event.ignore()
