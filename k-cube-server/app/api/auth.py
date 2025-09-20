# k-cube-server/app/api/auth.py
from flask import Blueprint, request, jsonify
from app.models import User
from app import db  # 导入 db 实例

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/auth/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': '需要提供邮箱和密码'}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({'error': '该邮箱已被注册'}), 409  # 409 Conflict

    new_user = User(email=email)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()

    # 注册成功后，可以考虑直接返回一个 token，让用户无缝登录
    return jsonify({'message': '注册成功'}), 201


@auth_bp.route('/auth/token', methods=['POST'])
def get_token():
    # ... (此方法保持不变) ...
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify({'error': '需要提供邮箱和密码'}), 400
    user = User.query.filter_by(email=email).first()
    if user is None or not user.check_password(password):
        return jsonify({'error': '无效的凭证'}), 401
    return jsonify({'access_token': f'static-token-for-{user.email}'})
