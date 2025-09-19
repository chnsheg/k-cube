# k_cube/sync.py

import base64
from rich.console import Console
from rich.progress import Progress

from .repository import Repository
from .client import APIClient, APIError

console = Console()


class Synchronizer:
    """
    负责执行本地与远程仓库之间的同步操作。
    """

    def __init__(self, repo: Repository, api_client: APIClient):
        self.repo = repo
        self.client = api_client

    def sync(self) -> bool:
        """
        执行一个完整的双向同步周期。
        """
        # --- 关键修改：检查 vault_id ---
        if not self.repo.vault_id:
            console.print("[bold red]错误：本地保险库未与云端关联 (缺少 vault_id)。[/bold red]")
            raise ValueError("缺少 vault_id")

        console.print("🔄 开始同步...")

        with console.status("[bold green]正在检查远程状态...[/bold green]"):
            local_versions = self.repo.db.get_all_version_hashes()
            # --- 关键修改：传入 vault_id ---
            sync_state = self.client.check_sync_state(
                self.repo.vault_id, local_versions)

        console.print("🔄 开始同步...")

        # 1. 检查本地与远程的状态差异
        with console.status("[bold green]正在检查远程状态...[/bold green]"):
            local_versions = self.repo.db.get_all_version_hashes()
            sync_state = self.client.check_sync_state(
                self.repo.vault_id, local_versions)

        versions_to_upload = sync_state.get('versions_to_upload', [])
        versions_to_download = sync_state.get('versions_to_download', [])

        console.print(f"  - [cyan]本地有 {len(local_versions)} 个版本。[/cyan]")
        console.print(
            f"  - [yellow]{len(versions_to_upload)}[/yellow] 个版本需要上传。")
        console.print(
            f"  - [green]{len(versions_to_download)}[/green] 个版本需要下载。")

        did_download = False

        # 2. 推送本地变更到远程
        if versions_to_upload:
            self._push_changes(versions_to_upload)

        # 3. 拉取远程变更到本地
        if versions_to_download:
            self._pull_changes(versions_to_download)
            did_download = True  # <--- 修改3：如果下载了，就设置标志位

        if not versions_to_upload and not versions_to_download:
            console.print("[bold green]✅ 你的知识库已经是最新的了！[/bold green]")
        else:
            console.print("[bold green]✅ 同步完成！[/bold green]")

        return did_download  # <--- 修改4：返回标志位

    def _push_changes(self, version_hashes: list):
        """处理上传逻辑。"""
        console.print("\n[bold yellow]⬆️ 正在上传本地变更...[/bold yellow]")

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
                console.print(f"[red]错误：无法读取 blob {b_hash[:8]}: {e}[/red]")

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
        console.print("\n[bold green]⬇️ 正在下载远程变更...[/bold green]")

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
