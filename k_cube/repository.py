# k_cube/repository.py

import json
from pathlib import Path
from typing import Optional

from .database import Database
from .utils import KCUBE_DIR, find_vault_root

import time
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

from .utils import compress_blob, hash_blob, KCUBE_DIR

import shutil
from .utils import decompress_blob

from .config import ConfigManager  # <--- 确保导入 ConfigManager

# 使用 dataclass 来定义一个清晰的数据结构，用于表示仓库状态


@dataclass
class VaultStatus:
    staged_new: List[str] = field(default_factory=list)
    staged_modified: List[str] = field(default_factory=list)
    staged_deleted: List[str] = field(default_factory=list)
    unstaged_modified: List[str] = field(default_factory=list)
    unstaged_deleted: List[str] = field(default_factory=list)
    untracked_files: List[str] = field(default_factory=list)

    def has_staged_changes(self) -> bool:
        return bool(self.staged_new or self.staged_modified or self.staged_deleted)

    def has_unstaged_changes(self) -> bool:
        return bool(self.unstaged_modified or self.unstaged_deleted or self.untracked_files)

    def has_tracked_unstaged_changes(self) -> bool:
        """只检查已追踪文件的未暂存变更（修改或删除）。"""
        return bool(self.unstaged_modified or self.unstaged_deleted)


class Repository:
    """
    代表一个 K-Cube 保险库，封装了所有核心业务逻辑。
    """

    def __init__(self, vault_path: Path):
        self.vault_path = vault_path
        self.kcube_path = self.vault_path / KCUBE_DIR
        self.db_path = self.kcube_path / "index.db"
        self.versions_path = self.kcube_path / "versions"
        self.db = Database(self.db_path)
        self.staging_path = self.kcube_path / "staging.json"
        # --- 新增 ---
        local_config_path = self.kcube_path / "config.json"
        self.config = ConfigManager(local_config_path)
        self.vault_id = self.config.get("vault_id")

    def _read_staging_area(self) -> Dict[str, str]:
        """读取暂存区内容。"""
        if not self.staging_path.exists():
            return {}
        with open(self.staging_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _write_staging_area(self, staging_data: Dict[str, str]):
        """写入暂存区内容。"""
        with open(self.staging_path, 'w', encoding='utf-8') as f:
            json.dump(staging_data, f, indent=4)

    @classmethod
    def find(cls, path: Path = Path('.')) -> Optional['Repository']:
        """
        查找并加载一个已存在的保险库。

        Args:
            path (Path): 开始查找的路径。

        Returns:
            Optional['Repository']: 如果找到，返回Repository实例；否则返回None。
        """
        root = find_vault_root(path)
        if root:
            return cls(root)
        return None

    @classmethod
    def initialize(cls, path: Path) -> 'Repository':
        if find_vault_root(path):
            raise FileExistsError(f"无法在 '{path}' 初始化：已存在保险库。")

        kcube_path = path / KCUBE_DIR
        versions_path = kcube_path / "versions"

        try:
            # --- 核心修复：使用 parents=True 来创建所有必需的父目录 ---
            kcube_path.mkdir(parents=True, exist_ok=True)
            versions_path.mkdir(exist_ok=True)
        except OSError as e:
            raise OSError(f"创建目录失败: {e}")

        db = Database(kcube_path / "index.db")
        db.initialize_schema()

        # 创建默认配置文件（未来可扩展）
        default_config = {"version": "1.0"}
        config_path = kcube_path / "config.json"
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4)

        # 返回新创建的仓库实例
        return cls(path)

    def get_status(self) -> VaultStatus:
        status = VaultStatus()

        # 1. 获取三个核心状态的清单 (manifest)
        # 最新提交 (HEAD)
        latest_version_hash = self.db.get_latest_version_hash()
        last_manifest = self.db.get_version_manifest(
            latest_version_hash) if latest_version_hash else {}

        # 暂存区 (Index / Staging Area)
        staged_manifest = self._read_staging_area()

        # 工作区 (Working Directory)
        work_tree_files: Dict[str, str] = {}
        for file_path in self.vault_path.rglob('*'):
            # 忽略 .kcube 目录和非文件项
            if KCUBE_DIR in file_path.parts or not file_path.is_file():
                continue

            relative_path_str = str(file_path.relative_to(
                self.vault_path)).replace('\\', '/')
            with open(file_path, 'rb') as f:
                # 注意：这里我们只计算内容的哈希，压缩和写入对象库是 `add` 的职责
                content = f.read()
            blob_hash = hash_blob(compress_blob(content))  # 保持与add一致的哈希计算
            work_tree_files[relative_path_str] = blob_hash

        # 2. 对比“暂存区” vs “最新提交”，找出 staged changes
        staged_vs_last_paths = set(
            staged_manifest.keys()) | set(last_manifest.keys())
        for path in sorted(list(staged_vs_last_paths)):
            staged_hash = staged_manifest.get(path)
            last_hash = last_manifest.get(path)

            if staged_hash and staged_hash != last_hash:
                if staged_hash == "_DELETED_":
                    status.staged_deleted.append(path)
                elif not last_hash:
                    status.staged_new.append(path)
                else:  # 哈希不同
                    status.staged_modified.append(path)

        # 3. 对比“工作区” vs “暂存区”，找出 unstaged changes
        work_vs_staged_paths = set(
            work_tree_files.keys()) | set(staged_manifest.keys())
        for path in sorted(list(work_vs_staged_paths)):
            work_hash = work_tree_files.get(path)
            staged_hash = staged_manifest.get(path)

            if not work_hash and staged_hash and staged_hash != "_DELETED_":
                # 在暂存区存在，但在工作区被删了
                status.unstaged_deleted.append(path)
            elif work_hash and staged_hash and staged_hash != "_DELETED_" and work_hash != staged_hash:
                # 在暂存区和工作区都存在，但内容不同 (被修改)
                status.unstaged_modified.append(path)

        # 4. 找出“未追踪的文件”
        # 存在于工作区，但既不存在于暂存区，也不存在于最新提交中
        for path in sorted(work_tree_files.keys()):
            if path not in staged_manifest and path not in last_manifest:
                status.untracked_files.append(path)

        return status

    def add(self, paths_to_add: List[Path]):
        """
        将指定路径的变更添加到暂存区。
        该方法能正确处理文件、目录、新增、修改和删除操作，并提供详细输出。
        """
        from rich.console import Console
        console = Console()

        staging_data = self._read_staging_area()

        # 获取所有已知文件的集合，作为判断“删除”和“新增”的依据
        latest_version_hash = self.db.get_latest_version_hash()
        last_manifest = self.db.get_version_manifest(
            latest_version_hash) if latest_version_hash else {}

        # 已知文件 = 上次提交的文件 + 当前已暂存的文件
        # 我们需要处理暂存区里可能存在的 "_DELETED_" 标记
        tracked_in_staging = {
            p for p, h in staging_data.items() if h != "_DELETED_"}
        all_tracked_files = set(last_manifest.keys()) | tracked_in_staging

        # 1. 规范化输入路径，并找出用户意图操作的所有文件
        files_to_process: Set[Path] = set()
        dirs_to_process: List[Path] = []

        for path_obj in paths_to_add:
            full_path = path_obj.resolve()

            # 安全检查：确保路径在保险库内
            try:
                full_path.relative_to(self.vault_path.resolve())
            except ValueError:
                console.print(f"警告：路径 '{path_obj}' 不在保险库中，已忽略。")
                continue

            if full_path.is_dir():
                dirs_to_process.append(full_path)
                # 展开目录下所有当前存在的文件
                for p in full_path.rglob('*'):
                    if p.is_file() and KCUBE_DIR not in p.parts:
                        files_to_process.add(p)
            elif full_path.is_file():
                files_to_process.add(full_path)
            elif not full_path.exists():
                # 如果用户明确指定了一个不存在的路径，我们也需要处理它（可能是一个删除操作）
                files_to_process.add(full_path)

        # 2. 处理被删除的文件
        # 遍历所有已知文件，检查它们是否存在于工作区
        files_known_before_add = set(
            last_manifest.keys()) | set(staging_data.keys())
        for tracked_file_str in files_known_before_add:
            if tracked_file_str == "_DELETED_":
                continue

            tracked_file_abs = self.vault_path.joinpath(
                tracked_file_str).resolve()

            # 检查这个被追踪的文件是否在我们当前操作的范围内
            in_scope = False
            # 如果是 `add .` (即 dirs_to_process 包含仓库根目录)，则所有文件都在范围内
            if self.vault_path.resolve() in dirs_to_process:
                in_scope = True
            else:
                for d in dirs_to_process:
                    try:
                        if tracked_file_abs.relative_to(d):
                            in_scope = True
                            break
                    except ValueError:
                        continue

            if not in_scope and tracked_file_abs not in files_to_process:
                continue  # 如果文件不在操作范围内，则跳过

            # 如果文件在操作范围内，但现在不存在了，就标记为删除
            if not tracked_file_abs.exists():
                relative_path_str = str(tracked_file_abs.relative_to(
                    self.vault_path)).replace('\\', '/')
                if staging_data.get(relative_path_str) != "_DELETED_":
                    staging_data[relative_path_str] = "_DELETED_"
                    console.print(
                        f"  [red]delete:[/red]     {relative_path_str}")

        # 3. 处理新增和修改的文件
        for file_path_abs in files_to_process:
            if not file_path_abs.is_file():  # 只处理实际存在的文件
                continue

            relative_path_str = str(file_path_abs.relative_to(
                self.vault_path)).replace('\\', '/')

            with open(file_path_abs, 'rb') as f:
                content = f.read()

            compressed = compress_blob(content)
            blob_hash = hash_blob(compressed)

            current_staged_hash = staging_data.get(relative_path_str)

            # 判断是新增还是修改
            is_new = relative_path_str not in all_tracked_files

            if current_staged_hash != blob_hash:
                if is_new:
                    console.print(
                        f"  [green]new file:[/green] {relative_path_str}")
                else:
                    console.print(
                        f"  [cyan]modify:[/cyan]   {relative_path_str}")

                staging_data[relative_path_str] = blob_hash
                if not self.db.blob_exists(blob_hash):
                    self._write_blob(blob_hash, compressed, is_compressed=True)

        # 4. 将更新后的暂存区数据写回文件
        self._write_staging_area(staging_data)

    def commit(self, message: dict):
        """
        将暂存区的内容固化为一个新版本。
        这个方法现在能正确处理新增、修改和删除操作。
        """
        staged_changes = self._read_staging_area()
        if not staged_changes:
            print("暂存区为空，没有需要提交的内容。")
            return

        # 1. 获取上一个版本的清单，作为我们构建新清单的基础。
        #    如果是第一次提交，基础就是一个空字典。
        latest_version_hash = self.db.get_latest_version_hash()
        new_manifest = self.db.get_version_manifest(
            latest_version_hash) if latest_version_hash else {}

        # 2. 遍历暂存区中的所有变更，并应用到新清单上。
        changes_applied = False
        for path, blob_hash in staged_changes.items():
            changes_applied = True
            if blob_hash == "_DELETED_":
                # 如果是删除标记，就从新清单中移除这个文件
                if path in new_manifest:
                    del new_manifest[path]
            else:
                # 如果是新增或修改，就更新或添加到新清单中
                new_manifest[path] = blob_hash

        if not changes_applied:
            print("暂存区没有检测到有效的变更可以提交。")
            return

        # 3. 创建版本元信息并计算哈希
        timestamp = int(time.time())
        # 我们只将最终的、干净的清单存入版本元信息中
        version_meta = {
            "timestamp": timestamp,
            "message": message,
            "manifest": new_manifest
        }
        version_meta_str = json.dumps(version_meta, sort_keys=True)
        version_hash = hash_blob(version_meta_str.encode('utf-8'))

        # 4. 将新版本写入数据库
        self.db.insert_version(version_hash, timestamp, message, new_manifest)

        # 5. 清空暂存区，为下一次 `add` 做准备
        self._write_staging_area({})

        from rich.console import Console
        console = Console()
        console.print(
            f"✅ [bold green]新版本提交成功！[/bold green] 版本号: [cyan]{version_hash[:12]}[/cyan]")

    def get_history(self, relative_path: Optional[Path] = None):
        """获取仓库或文件的版本历史。"""
        path_str = str(relative_path).replace(
            '\\', '/') if relative_path else None
        return self.db.get_version_history(path_str)

    def restore(self, version_prefix: str, file_path: Optional[Path] = None, hard_mode: bool = False):
        """
        恢复文件或整个工作区到指定版本。
        """
        # 1. 解析版本哈希
        full_version_hash = self.db.find_version_by_prefix(version_prefix)
        if not full_version_hash:
            raise ValueError(f"版本前缀 '{version_prefix}' 不明确或不存在。")

        # 2. 根据是恢复单个文件还是整个版本，分发任务
        if file_path:
            self._restore_single_file(file_path, full_version_hash)
        else:
            self._restore_full_vault(full_version_hash, hard_mode)

    def _restore_single_file(self, relative_path: Path, version_hash: str):
        """恢复单个文件到指定版本。"""
        path_str = str(relative_path).replace('\\', '/')
        blob_hash = self.db.get_blob_hash_for_file_in_version(
            version_hash, path_str)

        target_file_path = self.vault_path / relative_path

        if not blob_hash:
            # 如果目标版本中没有这个文件，意味着应该删除它
            if target_file_path.exists():
                target_file_path.unlink()
                print(f"文件 '{relative_path}' 在目标版本中不存在，已删除。")
            return

        content = self._read_blob(blob_hash)
        target_file_path.parent.mkdir(parents=True, exist_ok=True)
        target_file_path.write_bytes(content)
        print(f"文件 '{relative_path}' 已恢复。")

    def _restore_full_vault(self, version_hash: str, hard_mode: bool):
        """恢复整个保险库到指定版本。"""
        target_manifest = self.db.get_version_manifest(version_hash)

        # 1. 获取当前工作区所有已追踪的文件
        #    “已追踪”的定义是：存在于上一个版本或暂存区中的文件
        latest_version_hash = self.db.get_latest_version_hash()
        last_manifest = self.db.get_version_manifest(
            latest_version_hash) if latest_version_hash else {}
        staged_manifest = self._read_staging_area()
        files_to_check = set(last_manifest.keys()) | set(
            staged_manifest.keys())

        # 2. 恢复/更新目标版本中存在的文件
        for path_str, blob_hash in target_manifest.items():
            content = self._read_blob(blob_hash)
            target_file = self.vault_path / path_str
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_bytes(content)
            # 从待检查列表中移除，因为它已经被正确处理
            files_to_check.discard(path_str)

        # 3. 删除那些在当前已追踪、但在目标版本中不存在的文件
        files_to_delete = files_to_check - set(target_manifest.keys())
        for path_str in files_to_delete:
            file_to_delete = self.vault_path / path_str
            if file_to_delete.exists():
                file_to_delete.unlink()
                print(f"删除过时文件: {path_str}")

        # 4. 如果是 hard_mode，还要删除所有未追踪的文件
        if hard_mode:
            work_tree_files = set()
            for file_path in self.vault_path.rglob('*'):
                if KCUBE_DIR in file_path.parts or not file_path.is_file():
                    continue
                work_tree_files.add(str(file_path.relative_to(
                    self.vault_path)).replace('\\', '/'))

            untracked_to_delete = work_tree_files - set(target_manifest.keys())
            for path_str in untracked_to_delete:
                file_to_delete = self.vault_path / path_str
                if file_to_delete.exists():
                    file_to_delete.unlink()
                    print(f"硬模式：删除未追踪文件: {path_str}")

        # 5. 清空暂存区，因为工作区已经和指定版本完全一致
        self._write_staging_area({})
        print(f"工作区已恢复到版本 {version_hash[:8]}。")

    def _restore_version(self, version_hash: str, hard_mode: bool):
        target_manifest = self.db.get_version_manifest(version_hash)

        # 1. 恢复/更新版本中存在的文件
        for path_str, blob_hash in target_manifest.items():
            content = self._read_blob(blob_hash)
            target_file = self.vault_path / path_str
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_bytes(content)

        # 2. 处理 hard 模式下的删除操作
        if hard_mode:
            work_tree_files = set()
            for file_path in self.vault_path.rglob('*'):
                if KCUBE_DIR in file_path.parts or not file_path.is_file():
                    continue
                work_tree_files.add(str(file_path.relative_to(
                    self.vault_path)).replace('\\', '/'))

            files_to_delete = work_tree_files - set(target_manifest.keys())
            for path_str in files_to_delete:
                (self.vault_path / path_str).unlink()

        print(f"工作区已恢复到版本 {version_hash[:8]}。")

    def _read_blob(self, blob_hash: str) -> bytes:
        """从对象库读取并解压一个 blob。"""
        blob_path = self.versions_path / blob_hash[:2] / blob_hash[2:]
        if not blob_path.exists():
            raise IOError(f"数据损坏：找不到 blob 文件 {blob_hash}")
        compressed = blob_path.read_bytes()
        return decompress_blob(compressed)

    # 新增 reset 方法
    def reset(self, paths_to_reset: List[Path] = None):
        """
        从暂存区移除文件，或重置整个暂存区。

        Args:
            paths_to_reset (List[Path], optional): 如果提供，只移除指定路径。否则清空暂存区。
        """
        staging_data = self._read_staging_area()
        if not staging_data:
            print("暂存区已为空。")
            return

        if not paths_to_reset:
            # 清空整个暂存区
            self._write_staging_area({})
            print("已清空暂存区。")
        else:
            # 移除指定文件
            for path_obj in paths_to_reset:
                relative_path_str = str(path_obj.relative_to(
                    self.vault_path)).replace('\\', '/')
                if relative_path_str in staging_data:
                    del staging_data[relative_path_str]
                    print(f"已从暂存区移除 '{relative_path_str}'。")
            self._write_staging_area(staging_data)

    # 新增 revert 方法 (简化版：创建一个反向提交)
    def revert(self, version_prefix: str):
        """
        通过创建一个新的提交来撤销指定提交的更改。

        Args:
            version_prefix (str): 要撤销的提交的版本哈希前缀。
        """
        # 1. 找到要撤销的提交 (C) 和它的父提交 (P)
        target_hash = self.db.find_version_by_prefix(version_prefix)
        if not target_hash:
            raise ValueError(f"版本前缀 '{version_prefix}' 不明确或不存在。")

        parent_hash_cursor = self.db.conn.execute(
            "SELECT hash FROM versions WHERE timestamp < (SELECT timestamp FROM versions WHERE hash=?) ORDER BY timestamp DESC LIMIT 1",
            (target_hash,)
        )
        parent_hash_result = parent_hash_cursor.fetchone()
        parent_hash = parent_hash_result[0] if parent_hash_result else None

        target_manifest = self.db.get_version_manifest(target_hash)
        parent_manifest = self.db.get_version_manifest(
            parent_hash) if parent_hash else {}

        # 2. 以当前最新提交 (HEAD) 为基础
        latest_hash = self.db.get_latest_version_hash()
        if not latest_hash:
            raise RuntimeError("仓库为空，无法执行 revert。")

        head_manifest = self.db.get_version_manifest(latest_hash)
        new_manifest = head_manifest.copy()

        # 3. 计算反向变更并应用
        # 遍历被撤销的提交中的所有文件
        for path, target_blob in target_manifest.items():
            parent_blob = parent_manifest.get(path)
            if not parent_blob:  # 文件是在 C 中新增的 -> 应该删除
                if path in new_manifest:
                    del new_manifest[path]
            elif parent_blob != target_blob:  # 文件是在 C 中修改的 -> 应该恢复到 P 的版本
                new_manifest[path] = parent_blob

        # 遍历父提交，找出在 C 中被删除的文件
        for path, parent_blob in parent_manifest.items():
            if path not in target_manifest:  # 文件是在 C 中删除的 -> 应该加回来
                new_manifest[path] = parent_blob

        # 4. 创建一个新的 revert 提交
        revert_message = {
            "type": "Revert",
            "summary": f"Revert commit {target_hash[:8]}",
            "reverted_commit": target_hash
        }

        # (复用 commit 的核心逻辑)
        timestamp = int(time.time())
        version_meta = {"timestamp": timestamp,
                        "message": revert_message, "manifest": new_manifest}
        version_meta_str = json.dumps(version_meta, sort_keys=True)
        version_hash = hash_blob(version_meta_str.encode('utf-8'))

        self.db.insert_version(version_hash, timestamp,
                               revert_message, new_manifest)
        print(f"已创建 Revert 提交: {version_hash}")

    def _read_blob(self, blob_hash: str, compressed: bool = False) -> bytes:
        """从对象库读取一个 blob。"""
        blob_path = self.versions_path / blob_hash[:2] / blob_hash[2:]
        if not blob_path.exists():
            raise IOError(f"数据损坏：找不到 blob 文件 {blob_hash}")

        content = blob_path.read_bytes()

        if compressed:
            return content
        return decompress_blob(content)

    def _write_blob(self, blob_hash: str, content: bytes, is_compressed: bool = False):
        """向对象库写入一个 blob。"""
        if self.db.blob_exists(blob_hash):
            return  # Blob 已存在，无需写入

        blob_dir = self.versions_path / blob_hash[:2]
        blob_dir.mkdir(exist_ok=True)
        blob_file = blob_dir / blob_hash[2:]

        final_content = content if is_compressed else compress_blob(content)

        blob_file.write_bytes(final_content)

        # 注意：写入 blob 时，通常也需要更新数据库记录
        # 这里假设下载的 blob 已经在服务器端计算好了大小
        # 在一个完整的实现中，我们可能需要解压来获取 uncompressed_size
        uncompressed_size = len(decompress_blob(
            final_content)) if is_compressed else len(content)
        compressed_size = len(final_content)

        self.db.insert_blob(blob_hash, uncompressed_size, compressed_size)
