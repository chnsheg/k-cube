# k_cube/cli.py

from pathlib import Path
from typing import Tuple

import click
from rich.console import Console
from rich.panel import Panel
import sys

from .repository import Repository
from .config import ConfigManager
from .client import APIClient, APIError, AuthenticationError
from .sync import Synchronizer
from .utils import format_timestamp, find_vault_root  # <--- 修改这一行
from rich.table import Table


# 创建一个 Rich Console 实例，用于美化输出
console = Console()


@click.group()
def main():
    """
    K-Cube (kv): 一个为知识管理而生的版本控制工具。
    """
    pass


def get_global_config_path() -> Path:
    """获取全局配置文件的路径，并确保目录存在。"""
    config_dir = Path.home() / ".kcube"
    config_dir.mkdir(exist_ok=True)
    return config_dir / "global_config.json"


@main.group()
def vault():
    """
    管理云端的知识库 (保险库)。
    """
    pass


@vault.command(name="list")
def vault_list():
    """
    列出你云端账户下的所有保险库。
    """
    try:
        client = get_authenticated_client()
        with console.status("[bold green]正在从云端获取列表...[/bold green]"):
            vaults = client.list_vaults()

        if not vaults:
            console.print("[yellow]你在云端还没有任何保险库。[/yellow]")
            return

        table = Table(title="你的云端保险库")
        table.add_column("名称", style="cyan", no_wrap=True)
        table.add_column("保险库 ID (Vault ID)", style="magenta")

        for v in vaults:
            table.add_row(v['name'], v['id'])

        console.print(table)

    except Exception as e:
        console.print(Panel(f"[bold red]❌ 获取列表失败: {e}[/bold red]",
                            title="[bold]错误[/bold]", expand=False, border_style="red"))


def get_authenticated_client() -> APIClient:
    """辅助函数：加载全局配置并返回一个已认证的 API 客户端。"""
    global_config = ConfigManager(get_global_config_path())
    remote_url = global_config.get("remote_url")
    api_token = global_config.get("api_token")
    if not remote_url or not api_token:
        console.print(Panel("[bold red]❌ 操作失败[/bold red]\n\n需要全局配置和登录信息。\n请先运行 `kv remote <url>` 和 `kv login`。",
                            title="[bold]错误[/bold]", expand=False, border_style="red"))
        sys.exit(1)
    return APIClient(remote_url, api_token)


@main.command()
@click.argument('vault_id')
@click.argument('directory', required=False)
def clone(vault_id: str, directory: str):
    """
    从云端克隆一个已存在的保险库到本地。
    """
    # 如果用户只提供了 vault_id，我们使用一个默认的文件夹名
    # 为了避免歧义，我们从云端获取 vault name
    client = get_authenticated_client()
    vault_name_for_dir = "cloned-vault"  # 默认值
    try:
        vaults = client.list_vaults()
        for v in vaults:
            if v['id'] == vault_id:
                # 将非法字符替换为下划线，创建一个安全的文件夹名
                safe_name = "".join(
                    x if x.isalnum() else "_" for x in v['name'])
                vault_name_for_dir = safe_name
                break
    except Exception:
        pass  # 如果获取失败，就使用默认名

    target_path = Path(
        directory) if directory else Path.cwd() / vault_name_for_dir

    if target_path.exists() and any(target_path.iterdir()):
        console.print(Panel(f"[bold red]❌ 操作失败[/bold red]\n\n目标文件夹 '{target_path.name}' 已存在且不为空。",
                            title="[bold]错误[/bold]", expand=False, border_style="red"))
        sys.exit(1)

    target_path.mkdir(exist_ok=True, parents=True)

    try:
        console.print(
            f"正在克隆保险库 [yellow]{vault_id}[/yellow] 到 [cyan]{target_path}[/cyan]...")

        # 1. 初始化本地空仓库
        with console.status("[bold green]正在初始化本地结构...[/bold green]"):
            repo = Repository.initialize(target_path)

            # 2. 将 vault_id 和全局远程地址存入本地配置
            global_config = ConfigManager(get_global_config_path())
            remote_url = global_config.get("remote_url")
            repo.config.set("vault_id", vault_id)
            repo.config.set("remote_url", remote_url)

            # --- 核心修复 ---
            # 手动更新内存中 repo 实例的 vault_id 属性，以确保后续操作能获取到
            repo.vault_id = vault_id

        # 3. 执行第一次同步以下载所有数据
        synchronizer = Synchronizer(repo, client)
        synchronizer.sync()

        # 4. 自动恢复到最新状态
        latest_hash = repo.db.get_latest_version_hash()
        if latest_hash:
            with console.status("[bold green]正在检出最新文件...[/bold green]"):
                repo.restore(latest_hash)

        console.print(Panel(
            f"[bold green]✅ 保险库克隆成功！[/bold green]\n\n现在可以 `cd {target_path.name}` 并开始工作了。", expand=False))

    except Exception as e:
        import traceback
        traceback.print_exc()
        console.print(Panel(f"[bold red]❌ 克隆失败: {e}[/bold red]",
                            title="[bold]错误[/bold]", expand=False, border_style="red"))


@main.command()
@click.option('--name', prompt="请输入保险库名称", help="为这个新的保险库命名。")
def init(name: str):
    """
    在当前目录初始化一个新的保险库，并与云端关联。
    """
    current_path = Path.cwd()
    if find_vault_root(current_path):
        console.print(Panel("[bold red]❌ 操作失败[/bold red]\n\n当前目录或其父目录已经是一个 K-Cube 保险库。",
                            title="[bold]错误[/bold]", expand=False, border_style="red"))
        sys.exit(1)

    global_config = ConfigManager(get_global_config_path())
    remote_url = global_config.get("remote_url")
    api_token = global_config.get("api_token")
    if not remote_url or not api_token:
        console.print(Panel("[bold red]❌ 操作失败[/bold red]\n\n需要全局配置和登录信息。\n请先运行 `kv remote <url>` 和 `kv login`。",
                            title="[bold]错误[/bold]", expand=False, border_style="red"))
        sys.exit(1)

    try:
        with console.status("[bold green]正在云端创建保险库记录...[/bold green]"):
            client = APIClient(remote_url, api_token)
            vault_info = client.create_vault(name)
            vault_id = vault_info['id']

        repo = Repository.initialize(current_path)

        repo.config.set("vault_id", vault_id)
        repo.config.set("remote_url", remote_url)  # 也存一份在本地，方便未来操作

        success_message = (
            f"[bold green]✅ K-Cube 保险库 '{name}' 初始化成功！[/bold green]\n\n"
            f"本地路径: [cyan]{repo.vault_path}[/cyan]\n"
            f"云端 ID: [yellow]{vault_id}[/yellow]"
        )
        console.print(
            Panel(success_message, title="[bold]初始化完成[/bold]", expand=False))

    except Exception as e:
        console.print(Panel(f"[bold red]❌ 初始化失败: {e}[/bold red]",
                            title="[bold]错误[/bold]", expand=False, border_style="red"))


@main.command()
def status():
    """显示当前工作区的变更状态。"""
    repo = Repository.find()
    if not repo:
        console.print("[bold red]错误：[/bold red]当前目录不是一个 K-Cube 保险库。")
        sys.exit(1)

    status = repo.get_status()

    # 用于跟踪是否打印了任何变更信息
    has_printed_changes = False

    console.print(Panel("[bold]K-Cube 保险库状态[/bold]", expand=False))

    # --- 1. 显示已暂存的变更 (待提交) ---
    if status.has_staged_changes():
        has_printed_changes = True
        console.print("\n[bold]待提交的变更 (Changes to be committed):[/bold]")
        console.print("  (使用 'kv reset <文件>...' 来取消暂存)")
        if status.staged_new:
            for f in status.staged_new:
                console.print(f"  [green]new file:   {f}[/green]")
        if status.staged_modified:
            for f in status.staged_modified:
                console.print(f"  [green]modified:   {f}[/green]")
        if status.staged_deleted:
            for f in status.staged_deleted:
                console.print(f"  [green]deleted:    {f}[/green]")

    # --- 2. 显示未暂存的变更 ---
    if status.has_tracked_unstaged_changes():
        has_printed_changes = True
        # 如果前面已经打印过暂存区，这里加个空行分隔
        if status.has_staged_changes():
            console.print("")

        console.print("[bold]未暂存的变更 (Changes not staged for commit):[/bold]")
        console.print("  (这些是 [bold]已追踪文件[/bold] 的修改，使用 'kv add' 来暂存)")
        if status.unstaged_modified:
            for f in status.unstaged_modified:
                console.print(f"  [red]modified:   {f}[/red]")
        if status.unstaged_deleted:
            for f in status.unstaged_deleted:
                console.print(f"  [red]deleted:    {f}[/red]")

    # --- 3. 显示未追踪的文件 ---
    if status.untracked_files:
        has_printed_changes = True
        # 如果前面已经打印过变更，这里加个空行分隔
        if status.has_staged_changes() or status.has_tracked_unstaged_changes():
            console.print("")

        console.print("[bold]未追踪的文件 (Untracked files):[/bold]")
        console.print("  (这些是保险库不认识的 [bold]新文件[/bold]，使用 'kv add' 来开始追踪)")
        for f in status.untracked_files:
            console.print(f"  [red]{f}[/red]")

    # --- 4. 如果没有任何变更信息被打印，则显示最终的总结信息 ---
    if not has_printed_changes:
        if repo.db.get_latest_version_hash():
            # 如果有历史提交
            console.print("\n[bold green]✅ 没有需要提交的内容，工作区很干净。[/bold green]")
        else:
            # 如果是全新的仓库，没有任何提交
            console.print(
                "\n[bold]没有需要提交的内容 (可以创建/修改文件后使用 'kv add' 来追踪)[/bold]")
    elif not status.has_tracked_unstaged_changes() and not status.untracked_files:
        # 如果有暂存内容，但工作区是干净的
        console.print("\n[bold green]✅ 没有未暂存的变更。[/bold green]")


@main.command()
@click.argument('paths', nargs=-1, required=True)
def add(paths: Tuple[str]):
    """将文件变更添加到暂存区。"""
    repo = Repository.find()
    if not repo:
        console.print("[bold red]错误：[/bold red]当前目录不是一个 K-Cube 保险库。")
        sys.exit(1)

    console.print("正在更新暂存区...")
    path_objs = [Path(p).resolve() for p in paths]
    repo.add(path_objs)
    console.print("\n暂存区更新完成。使用 'kv status' 查看状态。")


@main.command(name='commit')
@click.option('-m', '--message', 'summary', help="本次提交的摘要信息。")
def commit_command(summary: str):
    """将暂存区的变更记录为一个新版本。"""
    repo = Repository.find()
    if not repo:
        console.print("[bold red]错误：[/bold red]当前目录不是一个 K-Cube 保险库。")
        sys.exit(1)

    # 检查暂存区是否为空
    status = repo.get_status()
    if not status.has_staged_changes():
        console.print("暂存区为空，没有需要提交的内容。")
        console.print("请先使用 'kv add <文件>...' 来暂存变更。")
        sys.exit(1)

    # 交互式获取message的逻辑
    message = {}
    if not summary:
        summary = click.prompt("摘要 (必填)")
    message['summary'] = summary
    save_type = click.prompt(
        "类型",
        type=click.Choice(['Feat', 'Fix', 'Refactor',
                          'Style', 'Doc'], case_sensitive=False),
        default='Feat'
    )
    message['type'] = save_type
    related = click.prompt(
        "关联知识点 (选填, 使用 [[链接]] 语法)", default="", show_default=False)
    if related:
        message['related'] = related

    try:
        repo.commit(message)
    except Exception as e:
        console.print(f"[bold red]❌ 提交失败: {e}[/bold red]")


@main.command()
@click.argument('paths', nargs=-1)
def reset(paths: Tuple[str]):
    """
    从暂存区移除文件，或重置整个暂存区。

    如果未提供文件路径，则清空整个暂存区。
    """
    repo = Repository.find()
    if not repo:
        console.print("[bold red]错误：[/bold red]当前目录不是一个 K-Cube 保险库。")
        sys.exit(1)

    # 将用户输入的路径转换为绝对路径，以进行正确的相对路径计算
    path_objs = [Path(p).resolve() for p in paths] if paths else None
    repo.reset(path_objs)


@main.command()
@click.argument('version')
def revert(version: str):
    """

    通过创建一个新的提交来撤销指定提交的更改。

    这不会修改历史记录，而是在历史的顶端添加一个新的提交。
    """
    repo = Repository.find()
    if not repo:
        console.print("[bold red]错误：[/bold red]当前目录不是一个 K-Cube 保险库。")
        sys.exit(1)

    if not click.confirm(f"你确定要创建一个新提交来撤销版本 '{version}' 的更改吗?", abort=True):
        return

    try:
        repo.revert(version)
    except Exception as e:
        error_message = f"[bold red]❌ Revert 失败[/bold red]\n\n{e}"
        console.print(
            Panel(error_message, title="[bold]错误[/bold]", expand=False, border_style="red"))


@main.command()
@click.argument('version')
@click.argument('file_path', required=False)
@click.option('--hard', is_flag=True, help="在恢复整个版本时，删除工作区多余的文件。")
def restore(version: str, file_path: str, hard: bool):
    """
    恢复文件或整个工作区到指定的历史版本。

    VERSION:   版本哈希的前缀。
    FILE_PATH: [可选] 要恢复的文件的相对路径。如果未提供，则恢复整个工作区。
    """
    repo = Repository.find()
    # ... (前置检查)

    path_obj = Path(file_path) if file_path else None

    # 根据操作对象，生成不同的确认信息
    if path_obj:
        confirm_msg = f"你确定要将 '{file_path}' 恢复到版本 '{version}' 吗?\n当前文件内容将被覆盖 (但会创建备份)."
    else:
        confirm_msg = f"你确定要将整个工作区恢复到版本 '{version}' 吗?\n所有未提交的本地修改都将丢失！"
        if hard:
            confirm_msg += "\n[bold red]--hard 模式将永久删除版本中不存在的文件！[/bold red]"

    if not click.confirm(confirm_msg, abort=True):
        return

    try:
        repo.restore(version, path_obj, hard_mode=hard)
        # ... (成功提示)
    except Exception as e:
        # ... (失败提示)
        pass


@main.command()
@click.argument('file_path', required=False)
def log(file_path: str):
    """
    显示整个仓库或单个文件的版本历史。
    """
    repo = Repository.find()
    if not repo:
        console.print("[bold red]错误：[/bold red]当前目录不是一个 K-Cube 保险库。")
        sys.exit(1)

    path_obj = Path(file_path) if file_path else None

    # 验证文件路径是否存在（如果提供的话）
    if path_obj and not (repo.vault_path / path_obj).exists() and not (repo.vault_path / path_obj).is_dir():
        # 稍微放宽检查，允许查看已删除文件的历史
        pass

    history = repo.get_history(path_obj)

    if not history:
        console.print("[yellow]没有找到任何版本历史。[/yellow]")
        return

    for version in history:
        message = version['message']

        header = (
            f"[bold yellow]Version:[/bold yellow] [cyan]{version['hash'][:12]}[/cyan]\n"
            f"[bold]Date:[/bold]    {format_timestamp(version['timestamp'])}"
        )

        body = (
            f"\n  [bold magenta]({message.get('type', 'N/A')})[/bold magenta] {message.get('summary', 'No summary')}"
        )
        if 'related' in message and message['related']:
            body += f"\n  [dim]Related: {message['related']}[/dim]"

        panel_content = f"{header}\n{body}"
        console.print(Panel(panel_content, expand=False))
        console.print(" │")
        console.print(" ▼")


@main.command()
def login():
    """
    [全局命令] 登录到 K-Cube 云端服务。
    """
    global_config = ConfigManager(get_global_config_path())
    remote_url = global_config.get("remote_url")
    if not remote_url:
        console.print(Panel("[bold red]❌ 操作失败[/bold red]\n\n请先使用 `kv remote <url>` 设置远程仓库地址。",
                            title="[bold]错误[/bold]", expand=False, border_style="red"))
        sys.exit(1)

    email = click.prompt("邮箱")
    password = click.prompt("密码", hide_input=True)

    try:
        with console.status("[bold green]正在登录...[/bold green]"):
            client = APIClient(remote_url)
            token = client.login(email, password)

        global_config.set("api_token", token)
        console.print(
            Panel("✅ [bold green]登录成功！[/bold green]\n\n全局认证信息已保存。", expand=False))
    except (APIError, AuthenticationError) as e:
        console.print(Panel(f"[bold red]❌ 登录失败: {e}[/bold red]",
                            title="[bold]错误[/bold]", expand=False, border_style="red"))
    except Exception as e:
        console.print(Panel(f"[bold red]❌ 发生未知错误: {e}[/bold red]",
                            title="[bold]错误[/bold]", expand=False, border_style="red"))


@main.command()
@click.argument('url')
def remote(url: str):
    """
    [全局命令] 设置 K-Cube 云端服务的远程仓库 URL。
    """
    global_config = ConfigManager(get_global_config_path())
    global_config.set("remote_url", url)
    console.print(Panel(f"✅ 全局远程仓库已设置为: [cyan]{url}[/cyan]", expand=False))


@main.command()
def sync():
    """与远程仓库同步当前保险库的变更。"""
    repo = Repository.find()
    if not repo:
        console.print(Panel("[bold red]❌ 操作失败[/bold red]\n\n当前目录不是一个 K-Cube 保险库。请先运行 `kv init`。",
                            title="[bold]错误[/bold]", expand=False, border_style="red"))
        sys.exit(1)

    remote_url = repo.config.get("remote_url")
    vault_id = repo.config.get("vault_id")

    global_config = ConfigManager(get_global_config_path())
    api_token = global_config.get("api_token")

    if not remote_url or not api_token or not vault_id:
        console.print(Panel("[bold red]❌ 配置不完整[/bold red]\n\n保险库配置或全局登录信息不完整。请检查配置或重新登录。",
                            title="[bold]错误[/bold]", expand=False, border_style="red"))
        sys.exit(1)

    try:
        client = APIClient(remote_url, api_token)
        synchronizer = Synchronizer(repo, client)
        synchronizer.sync()
    except AuthenticationError:
        console.print(Panel("[bold red]❌ 认证失败！[/bold red]\n\n你的 token 可能已过期，请重新使用 `kv login` 登录。",
                            title="[bold]错误[/bold]", expand=False, border_style="red"))
    except APIError as e:
        console.print(Panel(f"[bold red]❌ 同步失败: {e}[/bold red]",
                            title="[bold]错误[/bold]", expand=False, border_style="red"))
    except Exception as e:
        import traceback
        traceback.print_exc()
        console.print(Panel(f"[bold red]❌ 发生未知错误: {e}[/bold red]",
                            title="[bold]错误[/bold]", expand=False, border_style="red"))
