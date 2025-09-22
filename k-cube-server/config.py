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
    SECRET_KEY = os.environ.get(
        'SECRET_KEY') or 'a-very-secret-and-hard-to-guess-key'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 提供一个默认的 SQLite 作为备用，但它不应该在生产中被使用
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'app.db')
