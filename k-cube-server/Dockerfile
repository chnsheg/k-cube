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