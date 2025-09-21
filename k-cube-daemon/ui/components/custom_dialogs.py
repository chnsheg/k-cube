# k-cube-daemon/ui/components/custom_dialogs.py
# (替换完整内容)
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
                             QSpacerItem, QSizePolicy, QWidget)
from PyQt6.QtCore import Qt
import qtawesome as qta

from .title_bar import TitleBar
from .styled_button import StyledButton
from .styled_line_edit import StyledLineEdit
from ui.theme import Color, Font, Size


class CustomDialog(QDialog):
    """所有自定义对话框的基类，提供统一的无边框样式。"""

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)

        self.title_bar = TitleBar(self)
        self.title_bar.setTitle(title)

        self.background_frame = QFrame(self)
        self.background_frame.setObjectName("backgroundFrame")
        self.background_frame.setStyleSheet(f"""
            #backgroundFrame {{
                background-color: {Color.BACKGROUND.name()};
                border: 1px solid {Color.WINDOW_BORDER.name()};
                border-radius: 12px;
            }}
        """)

        self.content_widget = QWidget()

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.button_layout = button_layout  # 暴露给子类添加按钮

        frame_layout = QVBoxLayout(self.background_frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)
        frame_layout.addWidget(self.title_bar)
        frame_layout.addWidget(self.content_widget, 1)  # 内容区域可伸展
        frame_layout.addLayout(self.button_layout)
        frame_layout.setContentsMargins(1, 1, 1, 1)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.background_frame)


class PasswordConfirmDialog(CustomDialog):
    """一个自定义的、需要输入密码确认的对话框。"""

    def __init__(self, title, text, parent=None):
        super().__init__(title, parent)

        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(25, 25, 25, 25)
        content_layout.setSpacing(15)

        text_label = QLabel(text)
        text_label.setStyleSheet(Font.BODY)
        text_label.setWordWrap(True)

        self.password_input = StyledLineEdit(is_password=True)
        self.password_input.setMinimumHeight(Size.INPUT_HEIGHT)

        self.confirm_button = StyledButton("确认", is_primary=True)
        self.cancel_button = StyledButton("取消", is_primary=False)

        self.confirm_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

        self.button_layout.addWidget(self.cancel_button)
        self.button_layout.addWidget(self.confirm_button)
        self.button_layout.setContentsMargins(0, 0, 20, 20)

        content_layout.addWidget(text_label)
        content_layout.addWidget(self.password_input)
        self.password_input.setFocus()

    def get_password(self):
        return self.password_input.text()


class CustomMessageBox(CustomDialog):
    """一个功能完备、样式统一的自定义消息框。"""

    def __init__(self, icon_name, icon_color, title, text,
                 ok_text="确定", cancel_text=None, parent=None):
        super().__init__(title, parent)

        content_layout = QHBoxLayout(self.content_widget)
        content_layout.setContentsMargins(25, 25, 25, 25)
        content_layout.setSpacing(20)

        icon_label = QLabel()
        icon_label.setPixmap(
            qta.icon(icon_name, color=icon_color).pixmap(36, 36))

        text_label = QLabel(text)
        text_label.setStyleSheet(Font.BODY)
        text_label.setWordWrap(True)

        content_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)
        content_layout.addWidget(text_label, 1)

        self.ok_button = StyledButton(ok_text, is_primary=True)
        self.ok_button.clicked.connect(self.accept)

        if cancel_text:
            self.cancel_button = StyledButton(cancel_text, is_primary=False)
            self.cancel_button.clicked.connect(self.reject)
            self.button_layout.addWidget(self.cancel_button)

        self.button_layout.addWidget(self.ok_button)
        self.button_layout.setContentsMargins(0, 0, 20, 20)

    @staticmethod
    def show_critical(parent, title, text):
        dialog = CustomMessageBox(
            'fa5s.times-circle', Color.RED, title, text, parent=parent)
        return dialog.exec()

    @staticmethod
    def show_question(parent, title, text):
        dialog = CustomMessageBox('fa5s.question-circle', Color.PRIMARY, title, text,
                                  ok_text="是", cancel_text="否", parent=parent)
        return dialog.exec() == QDialog.DialogCode.Accepted
