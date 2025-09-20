# k-cube/k_cube/client.py

from typing import Dict, List, Optional
import requests


class APIError(Exception):
    pass


class AuthenticationError(APIError):
    pass


class APIClient:
    def __init__(self, remote_url: str, api_token: Optional[str] = None):
        if not remote_url:
            raise ValueError("远程仓库 URL 不能为空。")
        self.base_url = remote_url.rstrip('/')
        self.api_token = api_token
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "K-Cube-CLI/0.2.0"  # 版本升级
        })
        if self.api_token:
            self.session.headers.update(
                {"Authorization": f"Bearer {self.api_token}"})

    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            response = self.session.request(method, url, **kwargs)
            if response.status_code in [401, 403]:
                raise AuthenticationError(
                    f"认证失败: {response.json().get('detail', response.text)}")
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            raise APIError(
                f"API 请求失败 ({e.response.status_code}): {e.response.text}") from e
        except requests.RequestException as e:
            raise APIError(f"网络连接错误: {e}") from e

    def register(self, email: str, password: str) -> dict:
        """向服务器发送注册请求。"""
        register_url = self.base_url + "/auth/register"
        response = requests.post(
            register_url, json={"email": email, "password": password})
        response.raise_for_status()
        return response.json()

    # --- 新增 Vault 管理方法 ---
    def create_vault(self, name: str) -> dict:
        return self._request("POST", "api/v1/vaults", json={"name": name})

    def list_vaults(self) -> List[Dict]:
        """
        从云端获取当前用户的所有保险库列表。
        """
        return self._request("GET", "api/v1/vaults")

    def get_vault_details(self, vault_id: str) -> dict:
        """获取单个保险库的详细信息。"""
        return self._request("GET", f"api/v1/vaults/{vault_id}")

    # --- 修改 Sync 方法以包含 vault_id ---
    def check_sync_state(self, vault_id: str, local_versions: List[str]) -> dict:
        endpoint = f"api/v1/vaults/{vault_id}/sync/check"
        return self._request("POST", endpoint, json={"local_version_hashes": local_versions})

    def upload_blobs(self, vault_id: str, blobs: List[Dict]):
        endpoint = f"api/v1/vaults/{vault_id}/sync/blobs"
        return self._request("POST", endpoint, json={"blobs": blobs})

    def upload_versions(self, vault_id: str, versions_data: List[Dict]):
        endpoint = f"api/v1/vaults/{vault_id}/sync/versions"
        return self._request("POST", endpoint, json={"versions": versions_data})

    def download_blobs(self, vault_id: str, blob_hashes: List[str]) -> List[Dict]:
        endpoint = f"api/v1/vaults/{vault_id}/sync/blobs"
        response = self._request("GET", endpoint, params={"h": blob_hashes})
        return response.get("blobs", [])

    def download_versions(self, vault_id: str, version_hashes: List[str]) -> List[Dict]:
        endpoint = f"api/v1/vaults/{vault_id}/sync/versions"
        response = self._request("GET", endpoint, params={"h": version_hashes})
        return response.get("versions", [])

    # login 方法保持不变
    def login(self, email: str, password: str) -> str:
        login_url = self.base_url + "/auth/token"
        response = requests.post(
            login_url, json={"email": email, "password": password})
        response.raise_for_status()
        token = response.json().get("access_token")
        if not token:
            raise AuthenticationError("登录成功，但未返回 access_token。")
        return token
