# k-cube-server/wsgi.py

from app import create_app

# 从应用工厂创建 app 实例
app = create_app()


@app.shell_context_processor
def make_shell_context():
    """
    为 `flask shell` 提供上下文，方便调试。
    将导入语句放在函数内部是避免潜在启动问题的最佳实践。
    """
    from app import db
    from app.models import User, Blob, Version, VersionFile
    return {
        'db': db,
        'User': User,
        'Blob': Blob,
        'Version': Version,
        'VersionFile': VersionFile
    }
