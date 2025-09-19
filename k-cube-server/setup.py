# k-cube-server/setup.py

from setuptools import setup, find_packages

setup(
    name='k-cube-server',
    version='0.1.0',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'Flask>=2.2.0',
        'Flask-SQLAlchemy>=3.0.0',
        'Flask-Migrate>=4.0.0',
        'python-dotenv>=1.0.0',
        'Werkzeug>=2.2.0',
    ],
)
