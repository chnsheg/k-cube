# k-cube/k_cube/config.py

import json
from pathlib import Path
from typing import Optional, Any


class ConfigManager:
    """
    通用配置管理类，封装了对单个 JSON 配置文件的所有读写操作。
    """

    def __init__(self, config_file_path: Path):
        """
        初始化配置管理器。

        Args:
            config_file_path (Path): 要管理的 JSON 配置文件的完整路径。
        """
        # --- 核心修改 ---
        # 直接使用传入的文件路径，不再追加 "/config.json"
        self.config_path = config_file_path
        self.config_data = self._load()

    def _load(self) -> dict:
        """
        从磁盘加载配置文件。如果文件不存在，则返回一个空字典。
        """
        if not self.config_path.exists():
            return {}
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _save(self) -> None:
        """
        将当前配置数据写入磁盘。
        在写入前，确保父目录存在。
        """
        try:
            # --- 关键补充 ---
            # 确保配置文件所在的目录存在
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=4)
        except IOError as e:
            print(f"错误：无法写入配置文件 {self.config_path}: {e}")
            raise

    def get(self, key: str, default: Any = None) -> Optional[Any]:
        """
        根据键获取配置值。
        """
        return self.config_data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        设置一个配置项并立即保存到磁盘。
        """
        self.config_data[key] = value
        self._save()
