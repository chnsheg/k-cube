# k-cube-daemon/ui/components/styled_button.py
# (替换完整内容)
from PyQt6.QtWidgets import QPushButton, QGraphicsDropShadowEffect
from PyQt6.QtCore import QVariantAnimation, QPropertyAnimation, QRect, QEasingCurve
from PyQt6.QtGui import QColor
from ui.theme import Color, Font


class StyledButton(QPushButton):
    def __init__(self, text, is_primary=True, parent=None):
        super().__init__(text, parent)

        self.is_primary = is_primary
        self._color = Color.PRIMARY if is_primary else Color.SECONDARY
        self._text_color = QColor(
            "white") if is_primary else Color.TEXT_PRIMARY
        self._hover_color = self._color.lighter(115)
        self._pressed_color = Color.PRIMARY_PRESSED if is_primary else Color.SECONDARY_PRESSED
        self.setAutoDefault(False)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._color.name()};
                color: {self._text_color.name()};
                border: none;
                border-radius: 8px;
                padding: 10px 16px;
                {Font.BODY}
                font-weight: 500;
                outline: none;
            }}
            QPushButton:pressed {{
                background-color: {self._pressed_color.name()};
            }}
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 60 if is_primary else 40))
        shadow.setOffset(0, 3 if is_primary else 2)
        self.setGraphicsEffect(shadow)

        self.animation = QVariantAnimation(self)
        self.animation.setDuration(150)
        self.animation.valueChanged.connect(self._on_color_changed)
        self.current_bg_color = self._color
        self.pos_animation = QPropertyAnimation(self, b"geometry")
        self.pos_animation.setDuration(100)
        self.pos_animation.setEasingCurve(QEasingCurve.Type.OutQuad)

    def _on_color_changed(self, color):
        # 这是一个更可靠的更新样式的方法
        style = self.styleSheet()
        start = style.find("background-color:")
        end = style.find(";", start)
        new_style = style[:start] + \
            f"background-color: {color.name()}" + style[end:]
        self.setStyleSheet(new_style)
        self.current_bg_color = color

    def enterEvent(self, event):
        self.animation.setStartValue(self.current_bg_color)
        self.animation.setEndValue(self._hover_color)
        self.animation.start()
        super().enterEvent(event)

    def mousePressEvent(self, event):
        self.initial_geometry = self.geometry()
        target_rect = QRect(
            self.initial_geometry.x() + 1,
            self.initial_geometry.y() + 1,
            self.initial_geometry.width() - 2,
            self.initial_geometry.height() - 2
        )
        self.pos_animation.setStartValue(self.initial_geometry)
        self.pos_animation.setEndValue(target_rect)
        self.pos_animation.start()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.pos_animation.setStartValue(self.geometry())
        self.pos_animation.setEndValue(self.initial_geometry)
        self.pos_animation.start()
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        self.animation.setStartValue(self.current_bg_color)
        self.animation.setEndValue(self._color)
        self.animation.start()
        super().leaveEvent(event)
