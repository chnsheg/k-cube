# k-cube-server/app/__init__.py

from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# 1. 在顶层实例化扩展，但此时不关联任何具体 app
db = SQLAlchemy()
migrate = Migrate()


def create_app(config_class=Config):
    """
    应用工厂函数 (Application Factory)。
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    # 2. 将扩展实例与创建的 app 绑定
    db.init_app(app)
    migrate.init_app(app, db)

    # 3. 在工厂函数内部导入并注册蓝图
    #    这可以确保在导入蓝图前，db 等对象已经完全初始化
    from app.api.auth import auth_bp
    from app.api.sync import sync_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(sync_bp)

    return app
