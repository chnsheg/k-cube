# K-Cube 项目启动指南

本文档旨在为 K-Cube 项目的开发者提供清晰的启动说明。项目包含三个独立的部分，每个部分都需要在各自独立的终端窗口和虚拟环境中运行。

## 目录
- [K-Cube 项目启动指南](#k-cube-项目启动指南)
  - [目录](#目录)
  - [1. 云端服务器 (`k-cube-server`)](#1-云端服务器-k-cube-server)
    - [环境准备 (仅需一次)](#环境准备-仅需一次)
    - [启动服务器](#启动服务器)
  - [2. 命令行客户端 (`k-cube`)](#2-命令行客户端-k-cube)
    - [环境准备 (仅需一次)](#环境准备-仅需一次-1)
    - [如何使用](#如何使用)
  - [3. 桌面守护进程 (`k-cube-daemon`)](#3-桌面守护进程-k-cube-daemon)

---

## 1. 云端服务器 (`k-cube-server`)

服务器是整个同步功能的核心，为所有客户端提供数据存储和 API 服务。

### 环境准备 (仅需一次)

1.  **进入项目目录**:
    ```bash
    cd path/to/your/k-cube-server
    ```

2.  **创建并激活虚拟环境**:
    ```bash
    # 创建
    python -m venv venv
    
    # 激活 (Windows)
    .\venv\Scripts\activate
    
    # 激活 (macOS / Linux)
    source venv/bin/activate
    ```

3.  **安装依赖**:
    ```bash
    # (可选) 如果你还没有 requirements.txt，可以根据 setup.py 创建
    pip install -e .
    ```
    这条命令会读取 `setup.py` 并安装 Flask, SQLAlchemy 等所有必需的库。

4.  **初始化数据库**:
    这是**至关重要**的一步，它会根据你的 `app/models.py` 文件创建数据库结构。
    ```bash
    # 如果是首次初始化，或者数据库模型有重大变更
    flask db init
    flask db migrate -m "Some descriptive message for the migration"
    flask db upgrade
    ```
    - `init`: 只需在项目首次设置时运行一次。
    - `migrate` 和 `upgrade`: 每当 `app/models.py` 文件发生变化时，都需要运行这两个命令来更新数据库表结构。

5.  **创建测试用户 (可选，但推荐)**:
    为了能让客户端登录，你需要至少创建一个用户。
    ```bash
    # 启动 Flask 的交互式 Shell
    flask shell
    ```
    在打开的 Python Shell 中，输入以下命令：
    ```python
    >>> from app.models import User
    >>> from app import db
    >>> u = User(email='test@example.com')
    >>> u.set_password('password123')
    >>> db.session.add(u)
    >>> db.session.commit()
    >>> exit()
    ```

### 启动服务器

**确保服务器的虚拟环境已激活**，并且你位于 `k-cube-server` 目录下。
```bash
flask run
```
当你看到类似下面的输出时，表示服务器已成功启动，并正在监听 http://127.0.0.1:5000。

 * Serving Flask app 'app'
 * Debug mode: on
 * Running on http://127.0.0.1:5000
Press CTRL+C to quit```
**请保持这个终端窗口持续运行。**

---

## 2. 命令行客户端 (`k-cube`)

`kv` 命令是进行手动版本控制和与云端交互的基础工具。

### 环境准备 (仅需一次)

1.  **打开一个新的终端窗口**。
2.  **进入项目目录**:
    ```bash
    cd path/to/your/k-cube
    ```
3.  **创建并激活虚拟环境**:
    ```bash
    python -m venv venv
    # ... (激活步骤同上)
    ```
4.  **以可编辑模式安装**:
    这个模式能让你的代码修改立即生效，无需重装。
    ```bash
    pip install -e .
    ```

### 如何使用

**确保客户端的虚拟环境已激活**。你可以在**任何**文件目录下使用 `kv` 命令。

**首次使用流程**:
```bash
# 1. 全局配置 (只需一次)
kv remote http://127.0.0.1:5000
kv login

# 2. 创建你的第一个知识库
mkdir my-notes
cd my-notes
kv init

# 3. 开始使用
kv status
kv add .
kv commit -m "My first note"
kv sync
```

## 3. 桌面守护进程 (`k-cube-daemon`)

这是一个带图形界面的后台应用，负责实现“无感同步”，是日常使用的主要方式。
环境准备 (仅需一次)
1. 打开一个新的终端窗口。
2. 进入项目目录:

    ```bash
    cd path/to/your/k-cube-daemon
    ```

3. 创建并激活虚拟环境:
    重要: 为了复用 k-cube 的核心逻辑，理论上守护进程应该和 k-cube CLI 共享同一个虚拟环境。如果分开，你需要确保 k-cube 作为一个包被正确安装到守护进程的环境中。为简单起见，推荐共享。如果分开安装：
    ```bash
    # 创建并激活守护进程的虚拟环境
    python -m venv venv
    # ... (激活步骤)

    # 安装守护进程的依赖
    pip install PyQt6 watchdog

    # 安装 CLI 核心库
    pip install -e ../k-cube # 假设 k-cube 在守护进程目录的上一级
    ```

**启动守护进程**
确保守护进程的虚拟环境已激活，并且你位于 k-cube-daemon 目录下。
```bash
python main.py
```

启动后，你会看到：
如果从未配置过，会弹出一个“K-Cube 设置”窗口，让你添加要监控的知识库。
如果已配置，应用会直接在后台启动，你只会在操作系统的系统托盘（Windows右下角）或菜单栏（macOS右上角）看到一个 K-Cube 图标。
如何使用:
- 通过主窗口添加/移除你想自动同步的知识库文件夹。
- 在这些文件夹中正常工作（创建/编辑/删除文件）。
- 观察系统托盘图标的状态变化，它会自动为你完成同步。
- 右键点击图标可以打开设置窗口或退出应用。