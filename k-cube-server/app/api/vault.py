# k-cube-server/app/api/vault.py

from flask import Blueprint, request, jsonify
from app import db
from app.models import Vault
from .sync import get_user_from_token  # 复用认证函数

vault_bp = Blueprint('vault', __name__, url_prefix='/api/v1/vaults')


@vault_bp.route('', methods=['POST'])
def create_vault():
    user = get_user_from_token()
    # ...
    data = request.get_json() or {}
    vault_name = data.get('name')
    vault_id = data.get('id')  # <-- 接收可选的 id

    if not vault_name:
        return jsonify({'error': '需要提供保险库名称'}), 400

    new_vault = Vault(name=vault_name, owner=user)
    if vault_id:  # 如果客户端提供了 id，就使用它
        if Vault.query.get(vault_id):
            return jsonify({'error': '该 ID 已存在'}), 409
        new_vault.id = vault_id

    db.session.add(new_vault)
    db.session.commit()
    return jsonify({'id': new_vault.id, 'name': new_vault.name}), 201


@vault_bp.route('/<string:vault_id>', methods=['DELETE'])
def delete_vault(vault_id):
    user = get_user_from_token()
    if not user:
        return jsonify({'detail': '需要认证'}), 401

    vault = Vault.query.filter_by(id=vault_id, user_id=user.id).first()
    if not vault:
        return jsonify({'error': '保险库未找到或无权访问'}), 404

    db.session.delete(vault)
    db.session.commit()
    return '', 204  # 204 No Content 表示成功删除


@vault_bp.route('', methods=['GET'])
def list_vaults():
    user = get_user_from_token()
    if not user:
        return jsonify({'detail': '需要认证'}), 401

    vaults = user.vaults.all()
    return jsonify([{'id': v.id, 'name': v.name} for v in vaults])


@vault_bp.route('/<string:vault_id>', methods=['GET'])
def get_vault(vault_id):
    """获取单个保险库的详细信息，用于验证。"""
    user = get_user_from_token()
    if not user:
        return jsonify({'detail': '需要认证'}), 401

    vault = Vault.query.filter_by(id=vault_id, user_id=user.id).first()
    if not vault:
        return jsonify({'error': '保险库未找到或无权访问'}), 404

    return jsonify({'id': vault.id, 'name': vault.name})
