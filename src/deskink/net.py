import json
import ssl
import urllib.request
from typing import Any

from . import __version__

USER_AGENT = f"deskink/{__version__} (+https://github.com/Alpostros/deskink)"
_INSECURE = ssl.create_default_context()
_INSECURE.check_hostname = False
_INSECURE.verify_mode = ssl.CERT_NONE


def request(url: str, headers: dict | None = None, timeout: float = 10, insecure: bool = False,
            limit: int = 1 << 20) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    ctx = _INSECURE if insecure else None
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return resp.status, resp.read(limit)


def get_json(url: str, headers: dict | None = None, timeout: float = 10) -> Any:
    _, body = request(url, {"Accept": "application/json", **(headers or {})}, timeout)
    return json.loads(body)
