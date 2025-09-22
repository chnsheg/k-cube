# K-Cube 服务器终极部署指南 (Ubuntu/Debian)

本文档旨在提供一个完整的、从零开始的 K-Cube 服务器部署流程。按照本指南的步骤，你可以在一台全新的、干净的 Ubuntu 22.04 LTS 或 Debian 12 服务器上，成功部署一个生产级别的 K-Cube 服务。

## 目录
1.  [**核心技术栈**](#1-核心技术栈)
2.  [**第一步：准备本地项目文件**](#2-第一步准备本地项目文件)
3.  [**第二步：配置云服务器**](#3-第二步配置云服务器)
4.  [**第三步：上传代码并启动服务**](#4-第三步上传代码并启动服务)
5.  [**第四步：最终测试**](#5-第四步最终测试)
6.  [**日常维护命令**](#6-日常维护命令)

---

## 1. 核心技术栈

*   **云服务商**: 任何提供 VPS 的服务商 (DigitalOcean, Vultr, AWS, etc.)
*   **操作系统**: Ubuntu 22.04 LTS / Debian 12 (Bookworm)
*   **容器化**: Docker & Docker Compose
*   **数据库**: PostgreSQL (在 Docker 容器中运行)
*   **Web 服务器 (反向代理)**: Nginx
*   **应用服务器**: Gunicorn

---

## 2. 第一步：准备本地项目文件

在开始服务器配置之前，请确保你的**本地电脑**上的 `k-cube-server` 项目文件夹中，包含以下 **6 个**配置文件。

### 文件 1: `Dockerfile`
**用途**: 定义如何构建 K-Cube 应用的 Docker 镜像。
**位置**: `k-cube-server/Dockerfile`

```dockerfile
# Dockerfile
# 使用官方 Python 3.11 slim 镜像作为基础
FROM python:3.11-slim

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# --- 核心修复：在安装 Python 依赖之前，先安装系统依赖 ---
# 运行 apt-get update 更新包列表
# 安装 netcat-openbsd，它提供了 nc 命令
# --no-install-recommends 避免安装不必要的推荐包，保持镜像苗条
# 最后清理 apt 缓存
RUN apt-get update && \
    apt-get install -y --no-install-recommends netcat-openbsd && \
    rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制依赖文件到工作目录
COPY requirements.txt .

# 使用 pip 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 将你本地的所有项目代码复制到容器的 /app 目录中
COPY . .

# 声明容器将监听 5000 端口
EXPOSE 5000

# 定义容器启动时要执行的默认命令
CMD ["/app/entrypoint.sh"]
```
### 文件 2: `docker-compose.yml`
**用途**: 定义和管理多个 Docker 容器（应用容器和数据库容器）。
**位置**: `k-cube-server/docker-compose.yml`

```yaml
# k-cube-server/docker-compose.yml

# 使用 Docker Compose 文件格式的版本 3.8
version: '3.8'

# 定义我们的服务 (容器)
services:
  # --- 1. 数据库服务 ---
  db:
    # 使用官方的 PostgreSQL 14 镜像，alpine 版本体积更小
    image: postgres:14-alpine
    # 为容器指定一个易于识别的名称
    container_name: k_cube_db
    # 数据持久化：
    # 将容器内部的 /var/lib/postgresql/data/ 目录 (PostgreSQL 存储数据的地方)
    # 映射到 Docker 的一个名为 'postgres_data' 的持久化卷 (volume) 上。
    # 这可以确保即使容器被删除，你的数据库数据也不会丢失。
    volumes:
      - postgres_data:/var/lib/postgresql/data/
    # 环境变量：
    # 从项目根目录下的 .env 文件加载数据库的用户名、密码和数据库名。
    # 这样做更安全，避免了将敏感信息硬编码在 yml 文件中。
    env_file:
      - .env
    # 重启策略：
    # 无论容器因何种原因停止，Docker 都会自动尝试重启它。
    restart: always

  # --- 2. 应用服务 ---
  app:
    # 为容器指定一个易于识别的名称
    container_name: k_cube_app
    # 构建指令：
    # 告诉 Docker Compose 在当前目录下寻找 Dockerfile 并用它来构建镜像。
    build: .
    # 卷映射：
    # 将宿主机的当前目录 ( . ) 映射到容器内部的 /app 目录。
    # 这是一个关键的开发特性，它允许你在本地修改代码，
    # Gunicorn 会自动检测到变化并重载，无需重新构建整个镜像。
    volumes:
      - .:/app
    # 端口映射：
    # 将容器的 5000 端口，绑定到宿主机的 5000 端口上。
    # 127.0.0.1 表示只允许从宿主机本机访问，这是安全的做法，
    # 因为公网流量应该由 Nginx 代理。
    # 如果你想直接从公网访问，可以改为 "5000:5000"。
    ports:
      - "5000:5000"
    # 环境变量：
    # 同样从 .env 文件加载配置。
    # 此外，我们还在这里明确定义了 DATABASE_URL，
    # 组合了 .env 文件中的变量，确保 Gunicorn 能获取到。
    env_file:
      - .env
    environment:
      - DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      - FLASK_APP=wsgi.py
      - FLASK_DEBUG=0 # 生产环境设置为0，关闭调试模式
    # 依赖关系：
    # 确保在 db 服务完全启动并准备就绪后，才开始启动 app 服务。
    depends_on:
      - db
    # 重启策略
    restart: always
    # 容器启动时执行的命令：
    # 首先赋予 entrypoint.sh 执行权限，然后执行它。
    command: sh -c "chmod +x /app/entrypoint.sh && /app/entrypoint.sh"

# --- 定义持久化卷 ---
volumes:
  # 定义一个名为 postgres_data 的 Docker 卷
  postgres_data:
```
### 文件 3: `entrypoint.sh`
**用途**: 容器启动时的初始化脚本，确保数据库可用并运行数据库迁移。
**位置**: `k-cube-server/entrypoint.sh`

```bash
#!/bin/sh

# 如果任何命令失败，立即退出脚本
set -e

# 等待 PostgreSQL 数据库完全准备就绪
echo "Waiting for postgres..."
while ! nc -z db 5432; do
  echo "  - waiting for db..."
  sleep 1
done
echo "PostgreSQL started"

# 确保 migrations/versions 目录存在
echo "Ensuring migrations directory exists..."
mkdir -p /app/migrations/versions

# 自动生成数据库迁移脚本 (如果模型有变化)
echo "Generating database migration script (if needed)..."
flask --app wsgi db migrate -m "Auto-deployment migration"

# 将迁移应用到数据库，创建所有表
echo "Running database migrations..."
flask --app wsgi db upgrade

# 创建一个默认用户，方便首次测试
echo "Creating default user..."
flask --app wsgi create-user test@example.com password123

# 使用 exec 启动 Gunicorn，使其成为容器的主进程
echo "Starting Gunicorn server..."
exec gunicorn --bind 0.0.0.0:5000 --workers 3 wsgi:app
```
### 文件 4: `.env`
**用途**: 存储环境变量，包含数据库连接信息等敏感数据。
**位置**: `k-cube-server/.env`

```env
POSTGRES_DB=k_cube_prod
POSTGRES_USER=k_cube_prod_user
POSTGRES_PASSWORD=your_strong_password
```
### 文件 5: `config.py`
**用途**: Flask 应用的配置文件，读取数据库连接字符串等配置。
**位置**: `k-cube-server/config.py`

```python
# k-cube-server/config.py
# (替换完整内容)
import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    """
    基础配置类。
    这里只定义静态的、默认的配置。
    动态的配置（如从环境变量读取）将在应用工厂中处理。
    """
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-very-secret-and-hard-to-guess-key'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 提供一个默认的 SQLite 作为备用，但它不应该在生产中被使用
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'app.db')
```

### 文件 6: `wsgi.py`
**用途**: WSGI 入口文件，供 Gunicorn 使用。
**位置**: `k-cube-server/wsgi.py`

```python
# wsgi.py
from dotenv import load_dotenv
import os
import click

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

from app import create_app, db
from app.models import User

app = create_app()

@app.cli.command("create-user")
@click.argument("email")
@click.argument("password")
def create_user_command(email, password):
    """创建一个新用户。"""
    with app.app_context():
        if User.query.filter_by(email=email).first():
            print(f"User '{email}' already exists.")
            return
        new_user = User(email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        print(f"Successfully created user '{email}'.")

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User}
```
### 文件7: `requirements.txt`
**用途**: 列出 Python 依赖包。
**位置**: `k-cube-server/requirements.txt`

```
Flask
Flask-SQLAlchemy
Flask-Migrate
python-dotenv
Werkzeug
psycopg2-binary
gunicorn
```

## 3. 第二步：配置云服务器
登录到你全新的 Ubuntu 22.04 / Debian 12 服务器，然后逐步执行以下命令。
### 3.1 更新系统
```bash
sudo -i
apt update && apt upgrade -y
apt install -y curl git nano
```
### 3.2 安装 Docker 和 Docker Compose
```bash
# 卸载任何可能冲突的旧版本
for pkg in docker.io docker-doc docker-compose podman-docker containerd runc; do apt-get remove -y $pkg; done

# 手动创建缺失的目录 (针对精简版 Debian)
install -m 0755 -d /etc/apt/keyrings
install -m 0755 -d /etc/apt/sources.list.d

# 使用官方脚本安装 Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# 安装 Docker Compose 插件
apt install -y docker-compose-plugin
```
### 3.3 配置防火墙（默认5000端口）

### 允许 SSH 和 HTTP/HTTPS 流量
```bash
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 5000/tcp
ufw enable
ufw status
```

### 3.4 配置 Nginx
```bash
# 安装 Nginx
apt install -y nginx

# 创建 Nginx 配置文件
nano /etc/nginx/sites-available/k-cube
```

将以下内容复制进去，将 YOUR_SERVER_IP 替换为你的服务器 IP 地址。
```nginx
server {
    listen 80;
    server_name YOUR_SERVER_IP;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
启用配置并重启 Nginx:
```bash
ln -s /etc/nginx/sites-available/k-cube /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx
```

## 4. 第三步：上传代码并启动服务
### 4.1 上传代码
在本地电脑上，使用 `scp` 或 `rsync` 将 `k-cube-server` 文件夹上传到服务器的 `/home/your_user/` 目录下。
```bash
scp -r /path/to/k-cube-server your_user
@YOUR_SERVER_IP:/home/your_user/
```
### 4.2 启动服务
```bash
cd /home/your_user/k-cube-server
docker compose up -d --build
docker compose ps
docker compose logs -f app
docker compose logs -f db
```
### 4.3 检查服务状态
确保所有容器都在运行：
```bash
docker compose ps
# 检查应用日志，确保没有错误
docker compose logs -f app
docker compose logs -f db
# 检查 Nginx 状态
systemctl status nginx
# 检查防火墙状态
ufw status
```
## 5. 第四步：最终测试
客户端打开，填写URL地址为 `http://YOUR_SERVER_IP:5000`，然后注册一个新用户，登录后新建端口库，测试上传文件等功能，确保一切正常。