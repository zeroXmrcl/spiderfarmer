from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from spiderfarmer.errors import SpiderFarmerError


@dataclass(frozen=True)
class Session:
    """Credentials returned by mail login. ``mqtt_pwd`` is the broker password, not the account password."""

    token: str
    mqtt_name: str
    mqtt_pwd: str
    user_id: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class Room:
    id: int
    name: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class Device:
    serial: str
    name: str
    product_type: str
    prefix: str
    room_id: int | None
    online: bool | None
    raw: dict[str, Any]


def topic_prefix(product_type: str) -> str:
    """MQTT topic prefix for a ``productType`` string. Light controllers are ``LC``, strips ``PS``, everything else ``CB``."""
    folded = product_type.upper()
    if "LC" in folded or "LIGHT" in folded:
        return "LC"
    if any(token in folded for token in ("PS10", "AC10", "PS5", "AC5", "PS")):
        return "PS"
    return "CB"


def session_from_login(payload: dict[str, Any]) -> Session:
    data = _data_object(payload)
    mqtt_name = str(data.get("mqttName") or "").strip()
    mqtt_pwd = str(data.get("mqttPwd") or "").strip()
    token = str(data.get("token") or "").strip()
    user_id = str(data.get("userId") or "").strip()
    if not mqtt_name or not mqtt_pwd:
        raise _missing("missing mqtt credentials")
    if not token:
        raise _missing("missing token")
    if not user_id:
        raise _missing("missing userId")
    return Session(
        token=token,
        mqtt_name=mqtt_name,
        mqtt_pwd=mqtt_pwd,
        user_id=user_id,
        raw=data,
    )


def room_from(record: dict[str, Any]) -> Room:
    room_id = record.get("id")
    if not isinstance(room_id, int):
        raise _missing("room missing id")
    return Room(id=room_id, name=str(record.get("roomName") or ""), raw=record)


def device_from(record: dict[str, Any]) -> Device:
    serial = str(record.get("deviceSerialnum") or "").replace(":", "").upper()
    product_type = str(record.get("productType") or "")
    if not serial or not product_type:
        raise _missing("device missing serial or productType")
    room = record.get("belonginRroom")
    status = record.get("connectStatus")
    return Device(
        serial=serial,
        name=str(record.get("deviceName") or serial),
        product_type=product_type,
        prefix=topic_prefix(product_type),
        room_id=room if isinstance(room, int) else None,
        online=None if status is None else status == 1,
        raw=record,
    )


def _data_object(payload: dict[str, Any]) -> dict[str, Any]:
    code = "" if payload.get("code") is None else str(payload.get("code"))
    if code != "000":
        msg = payload.get("msg")
        raise SpiderFarmerError(code or "?", str(msg) if msg is not None else "request failed")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise SpiderFarmerError("000", "missing data")
    return data


def _missing(msg: str) -> SpiderFarmerError:
    return SpiderFarmerError("000", msg)
