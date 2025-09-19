# k-cube-server/app/models.py

from app import db
from werkzeug.security import generate_password_hash, check_password_hash
import json
import uuid

# 新增 Vault 模型


class Vault(db.Model):
    id = db.Column(db.String(36), primary_key=True,
                   default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # 关系：一个保险库可以有多个版本
    versions = db.relationship(
        'Version', backref='vault', cascade="all, delete-orphan")


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(128))

    # 关系：一个用户可以拥有多个保险库
    vaults = db.relationship('Vault', backref='owner', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Blob(db.Model):
    hash = db.Column(db.String(64), primary_key=True)
    content = db.Column(db.LargeBinary, nullable=False)


class Version(db.Model):
    hash = db.Column(db.String(64), primary_key=True)
    timestamp = db.Column(db.Integer, index=True, nullable=False)
    message_json = db.Column(db.Text, nullable=False)

    # 关键修改：不再关联 author_id，而是关联 vault_id
    vault_id = db.Column(db.String(36), db.ForeignKey(
        'vault.id'), nullable=False)

    files = db.relationship(
        'VersionFile', backref='version', cascade="all, delete-orphan")

    @property
    def message(self):
        return json.loads(self.message_json)


class VersionFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    version_hash = db.Column(db.String(64), db.ForeignKey(
        'version.hash'), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)
    blob_hash = db.Column(db.String(64), db.ForeignKey(
        'blob.hash'), nullable=False)

    blob = db.relationship('Blob')
