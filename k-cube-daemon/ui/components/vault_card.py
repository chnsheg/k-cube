# k-cube-daemon/ui/components/vault_card.py
# (替换完整内容)
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMenu, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QColor
from ui.theme import Color, Font, STYLESHEET
import qtawesome as qta


class VaultCard(QFrame):
    selected = pyqtSignal(str, str)  # id, name
    delete_requested = pyqtSignal(str, str)  # id, name

    def __init__(self, vault_id: str, name: str, parent=None):
        super().__init__(parent)
        self.vault_id = vault_id
        self.name = name

        self.setFixedSize(200, 160)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {Color.CONTENT_BACKGROUND.name()};
                border: 1px solid {Color.BORDER.name()};
                border-radius: 12px;
            }}
            QFrame:hover {{
                border: 1.5px solid {Color.PRIMARY.name()};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # --- 顶部栏：图标和更多按钮 ---
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        icon_label = QLabel()
        icon_label.setPixmap(
            qta.icon('fa5s.book-open', color=Color.TEXT_SECONDARY.name()).pixmap(24, 24))

        self.more_button = QPushButton(
            qta.icon('fa5s.ellipsis-h', color=Color.TEXT_SECONDARY), "")
        self.more_button.setFixedSize(24, 24)
        self.more_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.more_button.setStyleSheet("""
            QPushButton { border: none; background-color: transparent; border-radius: 5px; }
            QPushButton:hover { background-color: #e5e5e5; }
        """)
        self.more_button.clicked.connect(self.show_menu)

        top_layout.addWidget(icon_label)
        top_layout.addStretch()
        top_layout.addWidget(self.more_button)

        # --- 中间内容 ---
        name_label = QLabel(name)
        name_label.setStyleSheet(Font.SUBTITLE)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setWordWrap(True)

        # --- 底部按钮 ---
        select_button = QPushButton("同步到此设备")
        select_button.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {Color.PRIMARY.name()};
                {Font.BODY}
                font-weight: 500;
            }}
            QPushButton:hover {{
                text-decoration: underline;
            }}
        """)
        select_button.setCursor(Qt.CursorShape.PointingHandCursor)
        select_button.clicked.connect(
            lambda: self.selected.emit(self.vault_id, self.name))

        layout.addLayout(top_layout)
        layout.addStretch()
        layout.addWidget(name_label, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()
        layout.addWidget(select_button, 0, Qt.AlignmentFlag.AlignCenter)

        # 添加悬浮阴影
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 30))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

    def show_menu(self):
        menu = QMenu(self)
        # --- 核心修改：应用全局样式 ---
        menu.setStyleSheet(STYLESHEET)

        delete_action = menu.addAction(
            qta.icon('fa5s.trash-alt', color=Color.RED.name()), "从云端永久删除...")

        action = menu.exec(self.mapToGlobal(
            QPoint(self.more_button.x(), self.more_button.y() + self.more_button.height())))

        if action == delete_action:
            self.delete_requested.emit(self.vault_id, self.name)
