# k-cube-server/app/api/auth.py

from flask import Blueprint, request, jsonify
from app.models import User

# 蓝图是组织一组相关视图（路由）和其他代码的方式
auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/auth/token', methods=['POST'])
def get_token():
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': '需要提供邮箱和密码'}), 400

    user = User.query.filter_by(email=email).first()

    if user is None or not user.check_password(password):
        return jsonify({'error': '无效的凭证'}), 401

    # 在生产环境中，这里应该生成一个有时效性的 JWT (JSON Web Token)
    # 为了本地测试，我们返回一个简单的静态 token
    return jsonify({'access_token': f'static-token-for-{user.email}'})
