# k-cube-server/app/__init__.py

from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# 1. 在顶层实例化扩展，但此时不关联任何具体 app
db = SQLAlchemy()
migrate = Migrate()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)

    from app.api.auth import auth_bp
    from app.api.sync import sync_bp
    from app.api.vault import vault_bp  # <--- 新增导入

    app.register_blueprint(auth_bp)
    app.register_blueprint(sync_bp)
    app.register_blueprint(vault_bp)  # <--- 新增注册

    return app
