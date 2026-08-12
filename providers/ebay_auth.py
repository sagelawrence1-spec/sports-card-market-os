import base64, os, time
from dataclasses import dataclass
from typing import Optional
import requests

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SCOPE = "https://api.ebay.com/oauth/api_scope"

@dataclass
class EbayAppToken:
    access_token: str
    expires_at: float

class EbayOAuthClient:
    def __init__(self, client_id: Optional[str]=None, client_secret: Optional[str]=None, timeout: int=20):
        self.client_id = client_id or os.getenv("EBAY_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("EBAY_CLIENT_SECRET")
        self.timeout = timeout
        self._token: Optional[EbayAppToken] = None

    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def get_application_token(self) -> str:
        if self._token and self._token.expires_at > time.time()+60:
            return self._token.access_token
        if not self.configured():
            raise RuntimeError("eBay credentials missing. Set EBAY_CLIENT_ID and EBAY_CLIENT_SECRET in the runtime environment.")
        basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        r = requests.post(
            TOKEN_URL,
            headers={"Authorization": f"Basic {basic}", "Content-Type":"application/x-www-form-urlencoded"},
            data={"grant_type":"client_credentials", "scope":SCOPE},
            timeout=self.timeout,
        )
        r.raise_for_status()
        data=r.json()
        self._token=EbayAppToken(data["access_token"], time.time()+int(data.get("expires_in",7200)))
        return self._token.access_token
