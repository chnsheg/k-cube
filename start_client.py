# E:/k-cube/k-cube/start.py
import subprocess
import sys
import os
from pathlib import Path


def print_step(step, title):
    print("\n" + "="*60)
    print(f"[STEP {step}] {title}")
    print("="*60)


def run_command(command, cwd, venv_python_exe):
    full_command = [str(venv_python_exe), "-m", *command]
    print(f"  -> CWD: {cwd}")
    print(f"  -> CMD: {' '.join(full_command)}")
    try:
        result = subprocess.run(full_command, cwd=cwd, check=True,
                                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if result.stderr:
            print(
                f"  [WARN] STDERR:\n{result.stderr.decode('utf-8', errors='ignore')}")
    except subprocess.CalledProcessError as e:
        print("\n" + "#"*60)
        print(f"[FATAL] Command failed with exit code {e.returncode}")
        if e.stderr:
            print(
                f"[FATAL] STDERR:\n{e.stderr.decode('utf-8', errors='ignore')}")
        print("#"*60)
        sys.exit(1)
    except FileNotFoundError:
        print(f"[FATAL] Command not found: {command[0]}.")
        sys.exit(1)


if __name__ == "__main__":
    print_step(0, "Defining and Verifying Paths")

    project_root = Path(__file__).parent.resolve()
    daemon_dir = project_root / "k-cube-daemon"

    # --- 核心修复：CLI 项目的根目录是 project_root 本身 ---
    cli_project_dir = project_root

    venv_dir = daemon_dir / "venv"

    if sys.platform == "win32":
        python_exe = venv_dir / "Scripts" / "python.exe"
        pythonw_exe = venv_dir / "Scripts" / "pythonw.exe"
    else:
        python_exe = venv_dir / "bin" / "python"
        pythonw_exe = python_exe

    print(f"  -> Project Root: {project_root}")
    if not all([daemon_dir.is_dir(), cli_project_dir.is_dir(), (cli_project_dir / "pyproject.toml").is_file()]):
        print(
            "[FATAL] Project structure incorrect. Ensure 'pyproject.toml' is in the root. Halting.")
        sys.exit(1)
    print("[OK] Project structure verified.")

    print_step(1, "Setting up Client Virtual Environment")
    if not venv_dir.exists():
        print(
            f"  -> Virtual environment not found. Creating in '{venv_dir}'...")
        subprocess.run([sys.executable, "-m", "venv",
                       str(venv_dir)], check=True)

    print("  -> Installing/Updating dependencies...")
    run_command(["pip", "install", "--upgrade", "pip"],
                cwd=daemon_dir, venv_python_exe=python_exe)
    run_command(["pip", "install", "PyQt6", "qtawesome", "watchdog"],
                cwd=daemon_dir, venv_python_exe=python_exe)

    # --- 核心修复：使用正确的路径进行安装 ---
    run_command(["pip", "install", "-e", str(cli_project_dir)],
                cwd=daemon_dir, venv_python_exe=python_exe)
    print("[OK] Client environment is ready.")

    print_step(2, "Launching K-Cube Daemon")

    print("  -> Starting GUI in the background...")
    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        # 启动一个独立的、分离的进程
        subprocess.Popen([str(pythonw_exe), str(daemon_dir / "app.py")],
                         cwd=daemon_dir,
                         creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         env=env)  # 传入新的环境变量
    except Exception as e:
        print(f"[ERROR] Failed to launch GUI: {e}")

    print("\n" + "="*60)
    print("K-Cube Client has been launched!")
    print("="*60)

    input("\nPress Enter to exit this launcher window...")
