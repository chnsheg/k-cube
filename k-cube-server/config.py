# k-cube-server/config.py

import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    """基础配置"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-very-secret-key'

    # --- 数据库配置 ---
    # 本地开发使用 SQLite，部署到云端时只需修改此行为 PostgreSQL 等数据库的地址
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')

    SQLALCHEMY_TRACK_MODIFICATIONS = False
