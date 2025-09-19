# k-cube-server/app/models.py

from app import db
from werkzeug.security import generate_password_hash, check_password_hash
import json


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(128))

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
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))

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
