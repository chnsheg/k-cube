# k_cube/database.py

import sqlite3
from pathlib import Path
import json
from typing import Dict, Optional, Tuple, List
from typing import Optional, List, Dict, Any


class Database:
    """
    数据库管理类，封装所有与SQLite的交互。
    """

    def __init__(self, db_path: Path):
        """
        初始化数据库连接。

        Args:
            db_path (Path): SQLite数据库文件的路径。
        """
        self.db_path = db_path
        self.conn = None

    def connect(self) -> None:
        """建立数据库连接。"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            # 开启外键约束支持，对于关系型数据很重要
            self.conn.execute("PRAGMA foreign_keys = ON;")
        except sqlite3.Error as e:
            # 实际应用中这里应该有更详细的日志和错误处理
            print(f"数据库连接错误: {e}")
            raise

    def close(self) -> None:
        """关闭数据库连接。"""
        if self.conn:
            self.conn.close()

    def _create_schema(self) -> None:
        """
        创建数据库表结构（如果不存在）。
        这是定义系统数据模型的蓝图。
        """
        if not self.conn:
            raise ConnectionError("数据库未连接，无法创建表结构。")

        schema_sql = """
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS blobs (
            hash TEXT PRIMARY KEY,
            uncompressed_size INTEGER NOT NULL,
            compressed_size INTEGER NOT NULL
        );
        
        CREATE TABLE IF NOT EXISTS versions (
            hash TEXT PRIMARY KEY,
            timestamp INTEGER NOT NULL,
            message_json TEXT NOT NULL,
            author TEXT
        );

        CREATE TABLE IF NOT EXISTS version_files (
            version_hash TEXT NOT NULL,
            file_path TEXT NOT NULL,
            blob_hash TEXT NOT NULL,
            PRIMARY KEY (version_hash, file_path),
            FOREIGN KEY (version_hash) REFERENCES versions(hash),
            FOREIGN KEY (blob_hash) REFERENCES blobs(hash)
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
            path,
            title,
            content,
            content='version_files',
            content_rowid='rowid'
        );
        """
        try:
            with self.conn:
                self.conn.executescript(schema_sql)
        except sqlite3.Error as e:
            print(f"创建表结构失败: {e}")
            raise

    def initialize_schema(self) -> None:
        """
        公开的初始化方法，连接并创建表结构。
        """
        self.connect()
        self._create_schema()
        # 初始化后可以保持连接，也可以选择关闭
        # self.close()

    def get_latest_version_hash(self) -> Optional[str]:
        """查询最新的版本哈希。"""
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT hash FROM versions ORDER BY timestamp DESC LIMIT 1")
        result = cursor.fetchone()
        return result[0] if result else None

    def get_version_manifest(self, version_hash: str) -> Dict[str, str]:
        """获取指定版本的文件清单 (file_path -> blob_hash)。"""
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT file_path, blob_hash FROM version_files WHERE version_hash = ?",
            (version_hash,)
        )
        return {row[0]: row[1] for row in cursor.fetchall()}

    def blob_exists(self, blob_hash: str) -> bool:
        """检查指定的 blob 哈希是否存在。"""
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT 1 FROM blobs WHERE hash = ? LIMIT 1", (blob_hash,))
        return cursor.fetchone() is not None

    def insert_blob(self, blob_hash: str, uncompressed_size: int, compressed_size: int):
        """插入一条新的 blob 记录。"""
        if not self.conn:
            self.connect()
        with self.conn:
            self.conn.execute(
                "INSERT INTO blobs (hash, uncompressed_size, compressed_size) VALUES (?, ?, ?)",
                (blob_hash, uncompressed_size, compressed_size)
            )

    def insert_version(self, version_hash: str, timestamp: int, message: dict, manifest: Dict[str, str]):
        """插入一个完整的新版本记录（版本信息 + 文件清单）。"""
        if not self.conn:
            self.connect()
        message_str = json.dumps(message)

        with self.conn:
            # 插入版本元信息
            self.conn.execute(
                "INSERT INTO versions (hash, timestamp, message_json) VALUES (?, ?, ?)",
                (version_hash, timestamp, message_str)
            )
            # 批量插入文件清单
            version_files_data = [
                (version_hash, path, blob) for path, blob in manifest.items()
            ]
            self.conn.executemany(
                "INSERT INTO version_files (version_hash, file_path, blob_hash) VALUES (?, ?, ?)",
                version_files_data
            )

    def get_version_history(self, file_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取整个仓库或单个文件的版本历史。

        Args:
            file_path (Optional[str]): 如果提供，则只查询包含此文件的版本历史。

        Returns:
            List[Dict[str, Any]]: 版本历史列表，每个版本是一个包含哈希、时间戳和消息的字典。
        """
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()

        if file_path:
            # 查询单个文件的历史：需要连接 versions 和 version_files 表
            sql = """
            SELECT v.hash, v.timestamp, v.message_json
            FROM versions v
            JOIN version_files vf ON v.hash = vf.version_hash
            WHERE vf.file_path = ?
            ORDER BY v.timestamp DESC
            """
            cursor.execute(sql, (file_path,))
        else:
            # 查询整个仓库的历史
            sql = "SELECT hash, timestamp, message_json FROM versions ORDER BY timestamp DESC"
            cursor.execute(sql)

        versions = []
        for row in cursor.fetchall():
            versions.append({
                "hash": row[0],
                "timestamp": row[1],
                "message": json.loads(row[2])
            })
        return versions

    def find_version_by_prefix(self, prefix: str) -> Optional[str]:
        """
        通过哈希前缀查找完整的版本哈希。

        Args:
            prefix (str): 版本哈希的前缀。

        Returns:
            Optional[str]: 如果找到唯一的完整哈希，则返回它，否则返回None。
        """
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        # 使用 LIKE 操作符进行前缀匹配
        cursor.execute(
            "SELECT hash FROM versions WHERE hash LIKE ?", (f"{prefix}%",))
        results = cursor.fetchall()

        if len(results) == 1:
            return results[0][0]
        # 如果找到0个或多个匹配项，则认为是不明确的
        return None

    def get_blob_hash_for_file_in_version(self, version_hash: str, file_path: str) -> Optional[str]:
        """获取特定版本中特定文件的 blob 哈希。"""
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT blob_hash FROM version_files WHERE version_hash = ? AND file_path = ?",
            (version_hash, file_path)
        )
        result = cursor.fetchone()
        return result[0] if result else None

    def get_all_version_hashes(self) -> List[str]:
        """获取数据库中所有版本的哈希列表。"""
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        cursor.execute("SELECT hash FROM versions")
        return [row[0] for row in cursor.fetchall()]

    def get_all_blob_hashes(self) -> List[str]:
        """获取数据库中所有 blob 的哈希列表。"""
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        cursor.execute("SELECT hash FROM blobs")
        return [row[0] for row in cursor.fetchall()]

    def get_version_data(self, version_hash: str) -> Optional[Dict[str, Any]]:
        """获取单个版本的完整数据，用于上传。"""
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT timestamp, message_json, author FROM versions WHERE hash = ?",
            (version_hash,)
        )
        version_row = cursor.fetchone()
        if not version_row:
            return None

        manifest = self.get_version_manifest(version_hash)

        return {
            "hash": version_hash,
            "timestamp": version_row[0],
            "message": json.loads(version_row[1]),
            "author": version_row[2],
            "manifest": manifest
        }

    def bulk_insert_versions(self, versions_data: List[Dict]):
        """批量插入从服务器下载的版本数据。"""
        if not self.conn:
            self.connect()

        versions_to_insert = []
        version_files_to_insert = []

        for version in versions_data:
            versions_to_insert.append(
                (version['hash'], version['timestamp'], json.dumps(
                    version['message']), version.get('author'))
            )
            for path, blob_hash in version['manifest'].items():
                version_files_to_insert.append(
                    (version['hash'], path, blob_hash)
                )

        with self.conn:
            self.conn.executemany(
                "INSERT OR IGNORE INTO versions (hash, timestamp, message_json, author) VALUES (?, ?, ?, ?)",
                versions_to_insert
            )
            self.conn.executemany(
                "INSERT OR IGNORE INTO version_files (version_hash, file_path, blob_hash) VALUES (?, ?, ?)",
                version_files_to_insert
            )
