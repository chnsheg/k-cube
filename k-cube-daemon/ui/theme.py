# k-cube-daemon/ui/theme.py

from PyQt6.QtGui import QColor

# --- 色彩定义 (苹果风格) ---


class Color:
    BACKGROUND = QColor("#f2f2f7")
    CONTENT_BACKGROUND = QColor("#ffffff")
    PRIMARY = QColor("#007aff")
    PRIMARY_PRESSED = QColor("#0056b3")
    SECONDARY = QColor("#e9e9ed")
    SECONDARY_PRESSED = QColor("#d1d1d6")
    TEXT_PRIMARY = QColor("#1c1c1e")
    TEXT_SECONDARY = QColor("#8e8e93")
    BORDER = QColor("#dcdce1")
    GREEN = QColor("#34c759")
    RED = QColor("#ff3b30")
    WINDOW_BORDER = QColor("#c4c4c4")

# --- 字体定义 ---


class Font:
    FAMILY = "'PingFang SC', 'Microsoft YaHei', '.SF NS Text', 'Segoe UI', 'Arial', sans-serif"
    TITLE = f"font-family: {FAMILY}; font-size: 20px; font-weight: 600; color: {Color.TEXT_PRIMARY.name()};"
    # --- 核心修改：调整字重和颜色，拉开层级 ---
    SUBTITLE = f"font-family: {FAMILY}; font-size: 15px; font-weight: 500; color: {Color.TEXT_PRIMARY.name()};"
    BODY = f"font-family: {FAMILY}; font-size: 14px; color: {Color.TEXT_PRIMARY.name()};"
    CAPTION = f"font-family: {FAMILY}; font-size: 12px; color: {Color.TEXT_SECONDARY.name()};"
    FORM_LABEL = f"font-family: {FAMILY}; font-size: 14px; font-weight: 500; color: {Color.TEXT_PRIMARY.name()};"

# --- 新增尺寸定义 ---


class Size:
    INPUT_HEIGHT = 42  # 增加高度
    BUTTON_HEIGHT = 44  # 增加高度
    SPACING_SMALL = 8
    SPACING_MEDIUM = 15
    SPACING_LARGE = 25


class QSS:
    USER_STATUS = f"""
        QLabel {{
            color: {Color.TEXT_SECONDARY.name()};
            {Font.CAPTION}
        }}
    """


STYLESHEET = f"""
    /* 全局窗口 */
    #mainWindow, #loginWindow {{
        background-color: {Color.BACKGROUND.name()};
    }}

    /* 标签 */
    QLabel {{
        background-color: transparent;
        {Font.BODY}
    }}

    /* --- 核心修改：列表样式 --- */
    QListWidget {{
        background-color: transparent; /* 完全透明 */
        border: none; /* 去掉边框 */
        padding: 0px;
        outline: 0; /* 去掉选中时的虚线框 */
    }}
    
    /* 禁用默认的 item 悬浮和选中效果，我们将自己在 item widget 中实现 */
    QListWidget::item:hover {{
        background-color: transparent;
    }}
    QListWidget::item:selected {{
        background-color: transparent;
    }}
"""
