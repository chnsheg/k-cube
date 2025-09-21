# k-cube-server/app/api/sync.py

from flask import Blueprint, request, jsonify
from app.models import Version, Blob, VersionFile, User, Vault
from app import db
import base64
import json

# 关键修改：蓝图 URL 现在包含 vault_id
sync_bp = Blueprint(
    'sync', __name__, url_prefix='/api/v1/vaults/<string:vault_id>/sync')

# 辅助函数：复用


def get_user_from_token():
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer static-token-for-'):
            return None
        email = auth_header.split('Bearer static-token-for-')[1]
        # --- 核心修复：确保查询不会出错 ---
        user = User.query.filter_by(email=email).first()
        return user
    except Exception:
        # 即使发生未知错误，也返回 None，而不是让 Flask 崩溃
        return None

# 辅助函数：验证用户是否有权访问此保险库


def get_vault_for_user(vault_id, user):
    return Vault.query.filter_by(id=vault_id, user_id=user.id).first()


@sync_bp.route('/check', methods=['POST'])
def check_sync_state(vault_id):
    user = get_user_from_token()
    if not user:
        return jsonify({'detail': '需要认证'}), 401

    vault = get_vault_for_user(vault_id, user)
    if not vault:
        return jsonify({'error': '保险库未找到或无权访问'}), 404

    data = request.get_json() or {}
    local_hashes = set(data.get('local_version_hashes', []))

    server_hashes_query = db.session.query(
        Version.hash).filter_by(vault_id=vault.id).all()
    server_hashes = {h for h, in server_hashes_query}

    versions_to_upload = list(local_hashes - server_hashes)
    versions_to_download = list(server_hashes - local_hashes)

    return jsonify({
        'versions_to_upload': versions_to_upload,
        'versions_to_download': versions_to_download
    })


@sync_bp.route('/versions', methods=['POST'])
def upload_versions(vault_id):
    user = get_user_from_token()
    if not user:
        return jsonify({'detail': '需要认证'}), 401

    vault = get_vault_for_user(vault_id, user)
    if not vault:
        return jsonify({'error': '保险库未找到或无权访问'}), 404

    data = request.get_json() or {}
    versions_to_upload = data.get('versions', [])

    for v_data in versions_to_upload:
        if not Version.query.get(v_data['hash']):
            new_version = Version(
                hash=v_data['hash'],
                timestamp=v_data['timestamp'],
                message_json=json.dumps(v_data['message']),
                vault_id=vault.id  # 关联到正确的保险库
            )
            for path, blob_hash in v_data['manifest'].items():
                vf = VersionFile(file_path=path, blob_hash=blob_hash)
                new_version.files.append(vf)
            db.session.add(new_version)

    db.session.commit()
    return jsonify({'status': '成功'}), 201

# ... upload_blobs, download_blobs, download_versions 的逻辑基本不变 ...
# ... 但为了完整性，我们提供完整文件 ...


@sync_bp.route('/blobs', methods=['POST'])
def upload_blobs(vault_id):
    user = get_user_from_token()
    if not user:
        return jsonify({'detail': '需要认证'}), 401
    vault = get_vault_for_user(vault_id, user)
    if not vault:
        return jsonify({'error': '保险库未找到或无权访问'}), 404

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


@sync_bp.route('/blobs', methods=['GET'])
def download_blobs(vault_id):
    user = get_user_from_token()
    if not user:
        return jsonify({'detail': '需要认证'}), 401
    vault = get_vault_for_user(vault_id, user)
    if not vault:
        return jsonify({'error': '保险库未找到或无权访问'}), 404

    blob_hashes = request.args.getlist('h')
    if not blob_hashes:
        return jsonify({'error': '没有提供 blob 哈希'}), 400
    blobs = Blob.query.filter(Blob.hash.in_(blob_hashes)).all()
    response_blobs = [{'hash': b.hash, 'content_b64': base64.b64encode(
        b.content).decode('ascii')} for b in blobs]
    return jsonify({'blobs': response_blobs})


@sync_bp.route('/versions', methods=['GET'])
def download_versions(vault_id):
    user = get_user_from_token()
    if not user:
        return jsonify({'detail': '需要认证'}), 401
    vault = get_vault_for_user(vault_id, user)
    if not vault:
        return jsonify({'error': '保险库未找到或无权访问'}), 404

    version_hashes = request.args.getlist('h')
    versions = Version.query.filter(Version.hash.in_(version_hashes)).all()
    response_versions = []
    for v in versions:
        manifest = {vf.file_path: vf.blob_hash for vf in v.files}
        response_versions.append(
            {'hash': v.hash, 'timestamp': v.timestamp, 'message': v.message, 'manifest': manifest})
    return jsonify({'versions': response_versions})
