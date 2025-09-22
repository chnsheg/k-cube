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