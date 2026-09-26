from __future__ import annotations

import time
from typing import Any, Callable

import requests

from spiderfarmer.envelope import USER_AGENT, decode_response, encrypt_body, systemdata
from spiderfarmer.errors import SpiderFarmerError
from spiderfarmer.models import Device, Room, Session, device_from, room_from, session_from_login

API = "https://api.spider-farmer.com"
Post = Callable[..., requests.Response]


class Client:
    """HTTP client for one Spider Farmer cloud.

    Pass ``post`` in tests. Production uses ``requests.post``.
    """

    def __init__(
        self,
        *,
        base_url: str = API,
        timezone: str = "Europe/Berlin",
        device_id: str = "spiderfarmer",
        app_version: str = "2.5.2",
        timeout: float = 20,
        post: Post = requests.post,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timezone = timezone
        self.device_id = device_id
        self.app_version = app_version
        self.timeout = timeout
        self._post = post
        self._req_seq = 0

    def login(self, email: str, password: str, *, now_s: int | None = None) -> Session:
        payload = self.call(
            "/api/ios/ulogin/mailLogin/v2",
            {"email": email, "loginMethod": 1, "password": password},
            session=None,
            now_s=now_s,
        )
        return session_from_login(payload)

    def rooms(self, session: Session, *, now_s: int | None = None) -> list[Room]:
        payload = self.call("/api/ios/udm/getUserRooms/v2", None, session, now_s=now_s)
        return [room_from(item) for item in _data_list(payload)]

    def devices(self, session: Session, room_id: int, *, now_s: int | None = None) -> list[Device]:
        try:
            user_id = int(session.user_id)
        except ValueError as exc:
            raise SpiderFarmerError("000", "userId is not an integer") from exc
        payload = self.call(
            "/api/ios/udm/getDeviceList/v2",
            {"belonginRoomId": room_id, "userId": user_id},
            session,
            now_s=now_s,
        )
        return [device_from(item) for item in _data_list(payload)]

    def call(
        self,
        path: str,
        body: dict[str, Any] | None,
        session: Session | None = None,
        *,
        now_s: int | None = None,
    ) -> dict[str, Any]:
        """POST one iOS path. ``body is None`` sends an empty body. A dict is encrypted."""
        stamp = int(time.time()) if now_s is None else now_s
        self._req_seq += 1
        token = None if session is None else session.token
        headers = {
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
            "systemdata": systemdata(
                stamp,
                token=token,
                device_id=self.device_id,
                app_version=self.app_version,
                timezone=self.timezone,
                req_id=stamp * 1000 + self._req_seq,
            ),
        }
        data = None if body is None else encrypt_body(body)
        try:
            response = self._post(
                self.base_url + path,
                data=data,
                headers=headers,
                timeout=self.timeout,
            )
        except SpiderFarmerError:
            raise
        except Exception as exc:
            raise SpiderFarmerError("network", "unreachable") from exc
        if response.status_code != 200:
            raise SpiderFarmerError(str(response.status_code), "http")
        payload = decode_response(response.text)
        code = "" if payload.get("code") is None else str(payload.get("code"))
        if code != "000":
            msg = payload.get("msg")
            raise SpiderFarmerError(code or "?", str(msg) if msg is not None else "request failed")
        return payload


def _data_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    if data is None:
        return []
    if not isinstance(data, list):
        raise SpiderFarmerError("000", "expected a list")
    rows: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            raise SpiderFarmerError("000", "expected objects")
        rows.append(item)
    return rows
