# k_cube/utils.py

import os
from pathlib import Path
from typing import Optional

import hashlib
import zlib
from datetime import datetime

# 定义保险库的元数据目录名，便于全局统一修改
KCUBE_DIR = ".kcube"


def find_vault_root(path: Path = Path('.')) -> Optional[Path]:
    """
    从指定路径开始向上查找 K-Cube 保险库的根目录。

    根目录的标识是其下存在一个名为 ".kcube" 的子目录。

    Args:
        path (Path): 开始查找的路径，默认为当前目录。

    Returns:
        Optional[Path]: 如果找到，返回根目录的Path对象；否则返回None。
    """
    # 将输入路径转为绝对路径以处理边界情况
    current_path = path.resolve()

    while True:
        # 检查当前路径下是否存在 .kcube 目录
        if (current_path / KCUBE_DIR).is_dir():
            return current_path

        # 如果已经到达文件系统的根目录，则停止查找
        if current_path.parent == current_path:
            return None

        # 向上移动到父目录
        current_path = current_path.parent


def hash_blob(content: bytes) -> str:
    """
    计算文件内容的 SHA-256 哈希值。

    Args:
        content (bytes): 文件的二进制内容。

    Returns:
        str: 64位的十六进制哈希字符串。
    """
    return hashlib.sha256(content).hexdigest()


def compress_blob(content: bytes) -> bytes:
    """
    使用 zlib 压缩文件内容。

    Args:
        content (bytes): 待压缩的二进制内容。

    Returns:
        bytes: 压缩后的二进制内容。
    """
    return zlib.compress(content)


def decompress_blob(compressed_content: bytes) -> bytes:
    """
    使用 zlib 解压文件内容。

    Args:
        compressed_content (bytes): 压缩后的二进制内容。

    Returns:
        bytes: 解压后的原始二进制内容。
    """
    return zlib.decompress(compressed_content)


def format_timestamp(ts: int) -> str:
    """
    将 Unix 时间戳格式化为易于阅读的字符串。

    Args:
        ts (int): Unix 时间戳。

    Returns:
        str: 格式化后的日期时间字符串。
    """
    return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
