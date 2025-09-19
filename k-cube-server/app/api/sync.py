# k-cube-server/app/api/sync.py

from flask import Blueprint, request, jsonify
from app.models import Version, Blob, VersionFile, User
from app import db
import base64
import json

sync_bp = Blueprint('sync', __name__, url_prefix='/api/v1')

# --- 认证辅助函数 (未来可以优化为装饰器) ---


def get_user_from_token():
    """一个临时的、用于测试的 token 认证函数"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer static-token-for-'):
        return None
    email = auth_header.split('Bearer static-token-for-')[1]
    return User.query.filter_by(email=email).first()

# --- 同步端点 ---


@sync_bp.route('/sync/check', methods=['POST'])
def check_sync_state():
    user = get_user_from_token()
    if not user:
        return jsonify({'detail': '需要认证'}), 401

    data = request.get_json() or {}
    local_hashes = set(data.get('local_version_hashes', []))

    server_hashes_query = db.session.query(
        Version.hash).filter_by(author_id=user.id).all()
    server_hashes = {h for h, in server_hashes_query}

    versions_to_upload = list(local_hashes - server_hashes)
    versions_to_download = list(server_hashes - local_hashes)

    return jsonify({
        'versions_to_upload': versions_to_upload,
        'versions_to_download': versions_to_download
    })


@sync_bp.route('/sync/blobs', methods=['POST'])
def upload_blobs():
    user = get_user_from_token()
    if not user:
        return jsonify({'detail': '需要认证'}), 401

    data = request.get_json() or {}
    blobs_to_upload = data.get('blobs', [])

    for blob_data in blobs_to_upload:
        blob_hash = blob_data['hash']
        if not Blob.query.get(blob_hash):
            content = base64.b64decode(blob_data['content_b64'])
            new_blob = Blob(hash=blob_hash, content=content)
            db.session.add(new_blob)

    db.session.commit()
    return jsonify({'status': '成功'}), 201


@sync_bp.route('/sync/versions', methods=['POST'])
def upload_versions():
    user = get_user_from_token()
    if not user:
        return jsonify({'detail': '需要认证'}), 401

    data = request.get_json() or {}
    versions_to_upload = data.get('versions', [])

    for v_data in versions_to_upload:
        if not Version.query.get(v_data['hash']):
            new_version = Version(
                hash=v_data['hash'],
                timestamp=v_data['timestamp'],
                message_json=json.dumps(v_data['message']),
                author_id=user.id
            )
            for path, blob_hash in v_data['manifest'].items():
                vf = VersionFile(file_path=path, blob_hash=blob_hash)
                new_version.files.append(vf)
            db.session.add(new_version)

    db.session.commit()
    return jsonify({'status': '成功'}), 201


@sync_bp.route('/sync/blobs', methods=['GET'])
def download_blobs():
    user = get_user_from_token()
    if not user:
        return jsonify({'detail': '需要认证'}), 401

    blob_hashes = request.args.getlist('h')
    if not blob_hashes:
        return jsonify({'error': '没有提供 blob 哈希'}), 400

    blobs = Blob.query.filter(Blob.hash.in_(blob_hashes)).all()

    response_blobs = [
        {
            'hash': b.hash,
            'content_b64': base64.b64encode(b.content).decode('ascii')
        } for b in blobs
    ]
    return jsonify({'blobs': response_blobs})


@sync_bp.route('/sync/versions', methods=['GET'])
def download_versions():
    user = get_user_from_token()
    if not user:
        return jsonify({'detail': '需要认证'}), 401

    version_hashes = request.args.getlist('h')
    versions = Version.query.filter(Version.hash.in_(version_hashes)).all()

    response_versions = []
    for v in versions:
        manifest = {vf.file_path: vf.blob_hash for vf in v.files}
        response_versions.append({
            'hash': v.hash,
            'timestamp': v.timestamp,
            'message': v.message,
            'manifest': manifest
        })
    return jsonify({'versions': response_versions})
