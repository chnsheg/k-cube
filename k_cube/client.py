# k-cube/k_cube/client.py

import requests
from typing import Dict, List, Optional

# --- 自定义异常类 ---
# 升级后的异常类，可以携带 HTTP 状态码


class APIError(Exception):
    """当API返回非2xx状态码或发生网络错误时引发。"""

    def __init__(self, message, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class AuthenticationError(APIError):
    """当认证失败 (401/403) 时引发。"""
    pass


class APIClient:
    """
    封装了所有与 K-Cube 云端服务器的 HTTP 通信。
    """

    def __init__(self, remote_url: str, api_token: Optional[str] = None):
        if not remote_url:
            raise ValueError("远程仓库 URL 不能为空。")

        self.base_url = remote_url.rstrip('/')
        self.api_token = api_token

        # 使用 requests.Session 来复用 TCP 连接并管理 headers，性能更佳
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "K-Cube-Client/0.3.0"  # 更新版本号
        })
        if self.api_token:
            self.session.headers.update({
                "Authorization": f"Bearer {self.api_token}"
            })

    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """
        内部请求处理核心函数，包含健壮的错误处理。

        Args:
            method (str): HTTP 方法 (GET, POST, etc.)。
            endpoint (str): API 端点路径 (e.g., '/api/v1/vaults')。

        Returns:
            dict: API 返回的 JSON 数据。

        Raises:
            AuthenticationError: 如果认证失败。
            APIError: 如果发生其他 API 错误或网络层错误。
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            response = self.session.request(method, url, timeout=15, **kwargs)

            # 尝试解析 JSON，如果失败则将响应文本作为错误信息
            try:
                json_data = response.json()
            except requests.exceptions.JSONDecodeError:
                # 如果响应不是 JSON (例如 Flask debug 模式下的 HTML 错误页)
                # 将响应文本的前200个字符作为错误详情
                json_data = {'error': response.text[:200]}

            # 检查 HTTP 状态码是否表示成功 (2xx)
            if not response.ok:
                message = json_data.get('detail') or json_data.get(
                    'error') or "未知服务端错误"
                if response.status_code in [401, 403]:
                    raise AuthenticationError(
                        f"认证失败: {message}", status_code=response.status_code)
                else:
                    raise APIError(
                        f"API 请求失败: {message}", status_code=response.status_code)

            return json_data

        except requests.RequestException as e:
            # 处理网络连接层面的错误 (e.g., DNS, Connection Refused)
            raise APIError(f"网络连接错误: {e}") from e

    # --- 认证方法 ---
    def login(self, email: str, password: str) -> str:
        """使用邮箱和密码登录，获取 API Token。"""
        # 登录端点通常在 API 版本控制之外
        payload = {"email": email, "password": password}
        response_data = self._request("POST", "auth/token", json=payload)
        token = response_data.get("access_token")
        if not token:
            raise AuthenticationError("登录成功，但未返回 access_token。")
        return token

    def register(self, email: str, password: str) -> dict:
        """向服务器发送注册请求。"""
        payload = {"email": email, "password": password}
        return self._request("POST", "auth/register", json=payload)

    # --- 保险库管理方法 ---
    def create_vault(self, name: str, vault_id: Optional[str] = None) -> dict:
        """创建新仓库，可选择性地提供 ID。"""
        payload = {"name": name}
        if vault_id:
            payload['id'] = vault_id
        return self._request("POST", "api/v1/vaults", json=payload)

    def list_vaults(self) -> List[Dict]:
        """从云端获取当前用户的所有保险库列表。"""
        return self._request("GET", "api/v1/vaults")

    def get_vault_details(self, vault_id: str) -> dict:
        """获取单个保险库的详细信息，用于验证。"""
        return self._request("GET", f"api/v1/vaults/{vault_id}")

    def delete_vault(self, vault_id: str):
        """删除云端仓库。"""
        # DELETE 请求通常返回 204 No Content，此时 response.json() 会失败
        # _request 需要被调整或在这里特殊处理
        # 为保持一致性，我们假设服务器即使在204时也返回一个空的json对象 {}
        return self._request("DELETE", f"api/v1/vaults/{vault_id}")

    # --- 同步方法 ---
    def check_sync_state(self, vault_id: str, local_versions: List[str]) -> dict:
        """向服务器发送本地版本哈希列表，获取同步状态。"""
        endpoint = f"api/v1/vaults/{vault_id}/sync/check"
        payload = {"local_version_hashes": local_versions}
        return self._request("POST", endpoint, json=payload)

    def upload_blobs(self, vault_id: str, blobs: List[Dict]):
        """批量上传文件对象 (blobs)。"""
        endpoint = f"api/v1/vaults/{vault_id}/sync/blobs"
        return self._request("POST", endpoint, json={"blobs": blobs})

    def upload_versions(self, vault_id: str, versions_data: List[Dict]):
        """批量上传版本元数据。"""
        endpoint = f"api/v1/vaults/{vault_id}/sync/versions"
        return self._request("POST", endpoint, json={"versions": versions_data})

    def download_blobs(self, vault_id: str, blob_hashes: List[str]) -> List[Dict]:
        """根据哈希列表批量下载文件对象。"""
        endpoint = f"api/v1/vaults/{vault_id}/sync/blobs"
        response = self._request("GET", endpoint, params={"h": blob_hashes})
        return response.get("blobs", [])

    def download_versions(self, vault_id: str, version_hashes: List[str]) -> List[Dict]:
        """根据哈希列表批量下载版本元数据。"""
        endpoint = f"api/v1/vaults/{vault_id}/sync/versions"
        response = self._request("GET", endpoint, params={"h": version_hashes})
        return response.get("versions", [])
