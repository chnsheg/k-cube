
# **文件 2: `config_manager.py`**
from typing import Optional, Any
from pathlib import Path
import json
# k-cube-daemon/config_manager.py


class ConfigManager:
    def __init__(self, config_name="k_cube_daemon_config.json"):
        self.config_path = Path.home() / ".kcube" / config_name
        # self.config_path.parent.mkdir(exist_ok=True)
        self.config = self._load()

    def _load(self) -> dict:
        if not self.config_path.exists():
            return {}
        try:
            with self.config_path.open('r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def save(self):
        with self.config_path.open('w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=4)

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        self.config[key] = value
        self.save()


# 创建一个全局实例，方便在应用各处使用
config = ConfigManager()
