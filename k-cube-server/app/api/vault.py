# k-cube-server/app/api/vault.py

from flask import Blueprint, request, jsonify
from app import db
from app.models import Vault
from .sync import get_user_from_token  # 复用认证函数

vault_bp = Blueprint('vault', __name__, url_prefix='/api/v1/vaults')


@vault_bp.route('', methods=['POST'])
def create_vault():
    user = get_user_from_token()
    if not user:
        return jsonify({'detail': '需要认证'}), 401

    data = request.get_json() or {}
    vault_name = data.get('name')
    if not vault_name:
        return jsonify({'error': '需要提供保险库名称'}), 400

    new_vault = Vault(name=vault_name, owner=user)
    db.session.add(new_vault)
    db.session.commit()

    return jsonify({'id': new_vault.id, 'name': new_vault.name}), 201


@vault_bp.route('', methods=['GET'])
def list_vaults():
    user = get_user_from_token()
    if not user:
        return jsonify({'detail': '需要认证'}), 401

    vaults = user.vaults.all()
    return jsonify([{'id': v.id, 'name': v.name} for v in vaults])
