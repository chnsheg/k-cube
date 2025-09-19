# k_cube/cli.py

from pathlib import Path
from typing import Tuple

import click
from rich.console import Console
from rich.panel import Panel
import sys

from .repository import Repository
from .utils import format_timestamp
from .config import ConfigManager
from .client import APIClient, APIError, AuthenticationError
from .sync import Synchronizer


# 创建一个 Rich Console 实例，用于美化输出
console = Console()


@click.group()
def main():
    """
    K-Cube (kv): 一个为知识管理而生的版本控制工具。
    """
    pass


@main.command()
def init():
    """
    在当前目录初始化一个新的 K-Cube 保险库。
    """
    current_path = Path.cwd()
    try:
        repo = Repository.initialize(current_path)

        # 使用 Rich Panel 创建一个漂亮的成功提示框
        success_message = (
            f"[bold green]✅ K-Cube 保险库初始化成功！[/bold green]\n\n"
            f"路径: [cyan]{repo.vault_path}[/cyan]"
        )
        console.print(
            Panel(success_message, title="[bold]初始化完成[/bold]", expand=False))

    except FileExistsError as e:
        error_message = f"[bold red]❌ 初始化失败[/bold red]\n\n{e}"
        console.print(
            Panel(error_message, title="[bold]错误[/bold]", expand=False, border_style="red"))
    except Exception as e:
        # 捕获其他潜在的错误
        error_message = f"[bold red]❌ 发生未知错误[/bold red]\n\n{e}"
        console.print(
            Panel(error_message, title="[bold]错误[/bold]", expand=False, border_style="red"))


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

    path_objs = [Path(p).resolve() for p in paths]
    repo.add(path_objs)
    console.print(f"已处理 {len(paths)} 个路径的变更。使用 'kv status' 查看暂存状态。")


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
    """登录到 K-Cube 云端服务。"""
    repo = Repository.find()
    if not repo:
        console.print("[bold red]错误：[/bold red]请在 K-Cube 保险库内执行登录。")
        sys.exit(1)

    config = ConfigManager(repo.kcube_path)
    remote_url = config.get("remote_url")
    if not remote_url:
        console.print(
            "[bold red]错误：[/bold red]未设置远程仓库。请先使用 'kv remote add <url>'。")
        sys.exit(1)

    email = click.prompt("邮箱")
    password = click.prompt("密码", hide_input=True)

    try:
        client = APIClient(remote_url)
        token = client.login(email, password)
        config.set("api_token", token)
        console.print("[bold green]✅ 登录成功！认证信息已保存。[/bold green]")
    except (APIError, AuthenticationError) as e:
        console.print(f"[bold red]❌ 登录失败: {e}[/bold red]")
    except Exception as e:
        console.print(f"[bold red]❌ 发生未知错误: {e}[/bold red]")


@main.command()
@click.argument('url')
def remote(url: str):
    """
    设置此本地保险库关联的远程仓库 URL。
    """
    repo = Repository.find()
    if not repo:
        console.print("[bold red]错误：[/bold red]请在 K-Cube 保险库内设置远程地址。")
        sys.exit(1)

    config = ConfigManager(repo.kcube_path)
    config.set("remote_url", url)
    console.print(f"[bold green]✅ 远程仓库已设置为: {url}[/bold green]")


@main.command()
def sync():
    """与远程仓库同步变更。"""
    repo = Repository.find()
    if not repo:
        console.print("[bold red]错误：[/bold red]当前目录不是一个 K-Cube 保险库。")
        sys.exit(1)

    config = ConfigManager(repo.kcube_path)
    remote_url = config.get("remote_url")
    api_token = config.get("api_token")

    if not remote_url or not api_token:
        console.print("[bold red]错误：[/bold red]未配置远程仓库或未登录。")
        console.print("请先使用 'kv remote add <url>' 和 'kv login'。")
        sys.exit(1)

    try:
        client = APIClient(remote_url, api_token)
        synchronizer = Synchronizer(repo, client)
        synchronizer.sync()
    except AuthenticationError:
        console.print(
            "[bold red]❌ 认证失败！你的 token 可能已过期，请重新使用 'kv login' 登录。[/bold red]")
    except APIError as e:
        console.print(f"[bold red]❌ 同步失败: {e}[/bold red]")
    except Exception as e:
        console.print(f"[bold red]❌ 发生未知错误: {e}[/bold red]")
