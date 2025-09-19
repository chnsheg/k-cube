# k_cube/client.py

from typing import Dict, List, Optional
import requests

# 定义自定义异常，以便上层可以进行精细的错误处理


class APIError(Exception):
    """当API返回非2xx状态码时引发。"""
    pass


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

        self.base_url = remote_url.rstrip('/') + "/api/v1"
        self.api_token = api_token

        # 使用 requests.Session 来复用 TCP 连接并管理 headers，性能更佳
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "K-Cube-CLI/0.1.0"
        })
        if self.api_token:
            self.session.headers.update({
                "Authorization": f"Bearer {self.api_token}"
            })

    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """
        内部请求处理函数。

        Args:
            method (str): HTTP 方法 (GET, POST, etc.)。
            endpoint (str): API 端点路径。

        Returns:
            dict: API 返回的 JSON 数据。

        Raises:
            AuthenticationError: 如果认证失败。
            APIError: 如果发生其他 API 错误。
            requests.RequestException: 如果发生网络层错误。
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            response = self.session.request(method, url, **kwargs)

            if response.status_code in [401, 403]:
                raise AuthenticationError(
                    f"认证失败: {response.json().get('detail', response.text)}")

            response.raise_for_status()  # 对所有 4xx/5xx 错误码抛出异常

            return response.json()
        except requests.HTTPError as e:
            raise APIError(
                f"API 请求失败 ({e.response.status_code}): {e.response.text}") from e
        except requests.RequestException as e:
            # 处理网络连接问题，例如 DNS 查找失败、拒绝连接等
            raise APIError(f"网络连接错误: {e}") from e

    def login(self, email: str, password: str) -> str:
        """
        使用邮箱和密码登录，获取 API Token。
        这是一个特殊的、不需要认证的端点。
        """
        payload = {"email": email, "password": password}
        # 注意：登录端点不应包含在 /api/v1/ 前缀下，或者需要单独处理
        login_url = self.base_url.replace('/api/v1', '') + "/auth/token"
        response = requests.post(login_url, json=payload)
        response.raise_for_status()
        token = response.json().get("access_token")
        if not token:
            raise AuthenticationError("登录成功，但未返回 access_token。")
        return token

    def check_sync_state(self, local_versions: List[str]) -> dict:
        """
        向服务器发送本地版本哈希列表，获取同步状态。
        服务器会返回客户端需要下载的版本和服务器需要上传的版本。
        """
        payload = {"local_version_hashes": local_versions}
        return self._request("POST", "sync/check", json=payload)

    def upload_blobs(self, blobs: List[Dict]):
        """
        批量上传文件对象 (blobs)。
        """
        return self._request("POST", "sync/blobs", json={"blobs": blobs})

    def upload_versions(self, versions_data: List[Dict]):
        """
        批量上传版本元数据。
        """
        return self._request("POST", "sync/versions", json={"versions": versions_data})

    def download_blobs(self, blob_hashes: List[str]) -> List[Dict]:
        """
        根据哈希列表批量下载文件对象。
        """
        response = self._request(
            "GET", "sync/blobs", params={"h": blob_hashes})
        return response.get("blobs", [])

    def download_versions(self, version_hashes: List[str]) -> List[Dict]:
        """
        根据哈希列表批量下载版本元数据。
        """
        response = self._request(
            "GET", "sync/versions", params={"h": version_hashes})
        return response.get("versions", [])
