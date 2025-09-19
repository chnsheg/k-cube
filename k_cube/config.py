# k_cube/config.py

import json
from pathlib import Path
from typing import Optional, Any

class ConfigManager:
    """
    管理保险库的本地配置文件 (.kcube/config.json)。
    
    该类封装了所有对配置文件的读写操作，实现了与核心逻辑的解耦。
    """
    def __init__(self, kcube_path: Path):
        """
        初始化配置管理器。

        Args:
            kcube_path (Path): .kcube 目录的路径。
        """
        self.config_path = kcube_path / "config.json"
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
            # 在配置文件损坏或无法读取时返回空配置，保证健壮性
            return {}

    def _save(self) -> None:
        """
        将当前配置数据写入磁盘。
        """
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=4)
        except IOError as e:
            # 实际应用中可以加入日志记录
            print(f"错误：无法写入配置文件 {self.config_path}: {e}")
            raise

    def get(self, key: str) -> Optional[Any]:
        """
        根据键获取配置值。

        Args:
            key (str): 配置项的键。

        Returns:
            Optional[Any]: 配置值，如果键不存在则返回 None。
        """
        return self.config_data.get(key)

    def set(self, key: str, value: Any) -> None:
        """
        设置一个配置项并立即保存到磁盘。

        Args:
            key (str): 配置项的键。
            value (Any): 配置项的值。
        """
        self.config_data[key] = value
        self._save()