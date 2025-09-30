import base64
from rich.console import Console
from rich.progress import Progress
from dataclasses import dataclass
import logging
from .repository import Repository
from .client import APIClient, APIError

log = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """封装同步操作的结果。"""
    versions_uploaded: int = 0
    versions_downloaded: int = 0

    @property
    def has_changes(self) -> bool:
        return self.versions_uploaded > 0 or self.versions_downloaded > 0

    @property
    def direction(self) -> str:
        if self.versions_uploaded > 0 and self.versions_downloaded > 0:
            return "bidirectional"
        elif self.versions_uploaded > 0:
            return "upload"
        elif self.versions_downloaded > 0:
            return "download"
        else:
            return "none"


class Synchronizer:
    """
    负责执行本地与远程仓库之间的同步操作。
    """

    def __init__(self, repo: Repository, api_client: APIClient):
        self.repo = repo
        self.client = api_client

    def sync(self) -> SyncResult:
        """
        执行一个完整的双向同步周期，并返回详细结果。
        """
        log.info("🔄 开始同步...")

        local_versions = self.repo.db.get_all_version_hashes()
        sync_state = self.client.check_sync_state(
            self.repo.vault_id, local_versions)

        versions_to_upload = sync_state.get('versions_to_upload', [])
        versions_to_download = sync_state.get('versions_to_download', [])

        result = SyncResult(
            versions_uploaded=len(versions_to_upload),
            versions_downloaded=len(versions_to_download)
        )

        if versions_to_upload:
            log.info(
                f"  - [yellow]正在上传 {result.versions_uploaded} 个版本...[/yellow]")
            self._push_changes(versions_to_upload)
        if versions_to_download:
            log.info(
                f"  - [green]正在下载 {result.versions_downloaded} 个版本...[/green]")
            self._pull_changes(versions_to_download)

        if not result.has_changes:
            log.info("[bold green]✅ 你的知识库已经是最新的了！[/bold green]")
        else:
            log.info("[bold green]✅ 同步完成！[/bold green]")

        return result

    def _push_changes(self, version_hashes: list):
        """处理上传逻辑。"""
        log.info("\n[bold yellow]⬆️ 正在上传本地变更...[/bold yellow]")

        # a. 收集所有待上传版本的数据和涉及的 blob
        versions_data_to_upload = []
        blobs_to_upload_hashes = set()

        for v_hash in version_hashes:
            v_data = self.repo.db.get_version_data(v_hash)
            if v_data:
                versions_data_to_upload.append(v_data)
                blobs_to_upload_hashes.update(v_data['manifest'].values())

        # b. 筛选出远程不存在的 blob
        local_blob_hashes = set(self.repo.db.get_all_blob_hashes())
        # (在真实场景中，check_sync_state 也应返回需要上传的blob哈希)
        # 为简化，我们这里假设上传所有相关 blob

        # c. 准备并上传 blob 数据
        blobs_payload = []
        for b_hash in blobs_to_upload_hashes:
            try:
                # 注意: 我们需要发送原始（解压后）的内容，或者让服务器知道是压缩的。
                # 为简单起见，我们发送 base64 编码的压缩后内容。
                compressed_content = self.repo._read_blob(
                    b_hash, compressed=True)
                encoded_content = base64.b64encode(
                    compressed_content).decode('ascii')
                blobs_payload.append(
                    {"hash": b_hash, "content_b64": encoded_content})
            except IOError as e:
                log.info(f"[red]错误：无法读取 blob {b_hash[:8]}: {e}[/red]")

        if blobs_payload:
            with Progress() as progress:
                task = progress.add_task(
                    "[cyan]上传对象...", total=len(blobs_payload))
                self.client.upload_blobs(self.repo.vault_id, blobs_payload)
                progress.update(task, advance=len(blobs_payload))

        # d. 上传版本数据
        with Progress() as progress:
            task = progress.add_task(
                "[cyan]上传版本...", total=len(versions_data_to_upload))
            self.client.upload_versions(
                self.repo.vault_id, versions_data_to_upload)
            progress.update(task, advance=len(versions_data_to_upload))

    def _pull_changes(self, version_hashes: list):
        """处理下载逻辑。"""
        log.info("\n[bold green]⬇️ 正在下载远程变更...[/bold green]")

        # a. 下载版本元数据
        with Progress() as progress:
            task = progress.add_task(
                "[cyan]下载版本...", total=len(version_hashes))
            versions_data = self.client.download_versions(
                self.repo.vault_id, version_hashes)
            progress.update(task, advance=len(version_hashes))

        # b. 找出所有需要的 blob 哈希并下载
        blobs_needed = set()
        for v_data in versions_data:
            blobs_needed.update(v_data['manifest'].values())

        local_blobs = set(self.repo.db.get_all_blob_hashes())
        blobs_to_download = list(blobs_needed - local_blobs)

        if blobs_to_download:
            with Progress() as progress:
                task = progress.add_task(
                    "[cyan]下载对象...", total=len(blobs_to_download))
                downloaded_blobs = self.client.download_blobs(
                    self.repo.vault_id, blobs_to_download)
                progress.update(task, advance=len(blobs_to_download))

            # c. 将下载的 blob 写入本地对象库
            for blob in downloaded_blobs:
                self.repo._write_blob(blob['hash'], base64.b64decode(
                    blob['content_b64']), is_compressed=True)

        # d. 将下载的版本数据写入数据库
        self.repo.db.bulk_insert_versions(versions_data)
