# k-cube-daemon/ui/main_window.py

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QLabel,
                             QPushButton, QListWidget, QListWidgetItem,
                             QFileDialog, QHBoxLayout, QMessageBox)
from PyQt6.QtCore import pyqtSignal, Qt
from config_manager import config
from pathlib import Path  # 修正：添加缺失的导入


class MainWindow(QMainWindow):
    # 信号：当保险库列表变更时发射
    vaults_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("K-Cube 守护进程管理")
        self.setMinimumSize(500, 300)

        self.central_widget = QWidget()
        self.layout = QVBoxLayout(self.central_widget)

        self.label = QLabel("正在监控以下知识库:")
        self.vault_list = QListWidget()
        self.load_vaults_to_list()

        self.button_layout = QHBoxLayout()
        self.add_button = QPushButton("添加保险库")
        self.remove_button = QPushButton("移除保险库")

        self.button_layout.addWidget(self.add_button)
        self.button_layout.addWidget(self.remove_button)

        self.layout.addWidget(self.label)
        self.layout.addWidget(self.vault_list)
        self.layout.addLayout(self.button_layout)

        self.setCentralWidget(self.central_widget)

        # 连接信号
        self.add_button.clicked.connect(self.add_vault)
        self.remove_button.clicked.connect(self.remove_vault)

    def load_vaults_to_list(self):
        self.vault_list.clear()
        vault_paths = config.get("vault_paths", [])
        for path in vault_paths:
            item = QListWidgetItem(path)
            self.vault_list.addItem(item)

    def add_vault(self):
        path = QFileDialog.getExistingDirectory(
            self, "选择一个已初始化的 K-Cube 保险库文件夹")
        if path:
            vault_paths = config.get("vault_paths", [])
            if path in vault_paths:
                QMessageBox.warning(self, "重复", "这个保险库已经在监控列表中了。")
                return

            # 验证这是否是一个有效的 K-Cube 文件夹
            if not (Path(path) / ".kcube").exists():
                QMessageBox.critical(
                    self, "错误", "选择的文件夹不是一个有效的 K-Cube 保险库。\n请先使用 `kv init` 命令初始化。")
                return

            vault_paths.append(path)
            config.set("vault_paths", vault_paths)
            self.load_vaults_to_list()
            self.vaults_changed.emit()

    def remove_vault(self):
        current_item = self.vault_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "提示", "请先在列表中选择一个要移除的保险库。")
            return

        path_to_remove = current_item.text()
        reply = QMessageBox.question(
            self, "确认", f"你确定要停止监控\n{path_to_remove}\n吗？\n（这不会删除你的文件）")

        if reply == QMessageBox.StandardButton.Yes:
            vault_paths = config.get("vault_paths", [])
            if path_to_remove in vault_paths:
                vault_paths.remove(path_to_remove)
                config.set("vault_paths", vault_paths)
                self.load_vaults_to_list()
                self.vaults_changed.emit()

    def closeEvent(self, event):
        # 隐藏窗口而不是关闭它
        self.hide()
        event.ignore()
