# wsgi.py
from app.models import User
from app import create_app, db
from dotenv import load_dotenv
import os
import click

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)


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
