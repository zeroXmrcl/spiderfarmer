from __future__ import annotations

import json
import ssl
import time
from pathlib import Path
from typing import Any

from spiderfarmer.errors import SpiderFarmerError
from spiderfarmer.models import Session

MQTT_HOST = "sf.mqtt.spider-farmer.com"
MQTT_PORT = 8883
PREFIXES = {"CB", "PS", "LC"}


def bundled_ca() -> Path:
    return Path(__file__).resolve().parent / "certs" / "mqtt-ca.pem"


def topics(prefix: str, serial: str) -> tuple[str, str]:
    folded = prefix.upper()
    if folded not in PREFIXES:
        raise SpiderFarmerError("topic", f"unknown prefix {prefix!r}")
    clean = serial.replace(":", "").upper()
    if not clean:
        raise SpiderFarmerError("topic", "missing serial")
    return (
        f"SF/GGS/{folded}/API/UP/{clean}",
        f"SF/GGS/{folded}/API/DOWN/{clean}",
    )


def command(method: str, serial: str, params: dict[str, Any] | None, *, now_ms: int) -> dict[str, Any]:
    body: dict[str, Any] = {"pid": serial.replace(":", "").upper()}
    if params:
        body.update(params)
    return {"method": method, "params": body, "msgId": str(now_ms)}


def ssl_context(ca_file: Path) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = True
    context.load_verify_locations(cafile=str(ca_file))
    strict = getattr(ssl, "VERIFY_X509_STRICT", 0)
    if strict:
        context.verify_flags &= ~strict
    return context


class MqttSession:
    """Cloud MQTT for one logged-in account.

    ``set*`` methods are refused unless ``writes=True``. Reading does not need that flag.
    """

    def __init__(
        self,
        session: Session,
        *,
        writes: bool = False,
        ca_file: Path | None = None,
        host: str = MQTT_HOST,
        port: int = MQTT_PORT,
    ) -> None:
        self.session = session
        self.writes = writes
        self.ca_file = ca_file or bundled_ca()
        self.host = host
        self.port = port
        self._client: Any = None

    def connect(self) -> None:
        import paho.mqtt.client as mqtt

        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"{self.session.user_id}_{int(time.time())}",
            protocol=mqtt.MQTTv31,
            clean_session=True,
        )
        client.tls_set_context(ssl_context(self.ca_file))
        client.username_pw_set(self.session.mqtt_name, self.session.mqtt_pwd)
        client.connect(self.host, self.port, keepalive=30)
        client.loop_start()
        self._client = client

    def subscribe(self, prefix: str, serial: str) -> tuple[str, str]:
        up, down = topics(prefix, serial)
        result, _mid = self._require().subscribe(up, qos=0)
        if result != 0:
            raise SpiderFarmerError("mqtt", f"subscribe failed ({result})")
        return up, down

    def publish(
        self,
        prefix: str,
        serial: str,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        writes: bool | None = None,
        now_ms: int | None = None,
    ) -> tuple[str, dict[str, Any]]:
        allow = self.writes if writes is None else writes
        if method.startswith("set") and not allow:
            raise SpiderFarmerError("write", "pass writes=True to publish set* commands")
        _up, down = topics(prefix, serial)
        payload = command(
            method,
            serial,
            params,
            now_ms=int(time.time() * 1000) if now_ms is None else now_ms,
        )
        self._require().publish(down, json.dumps(payload, separators=(",", ":")), qos=0)
        return down, payload

    def close(self) -> None:
        client = self._client
        self._client = None
        if client is None:
            return
        client.loop_stop()
        client.disconnect()

    def _require(self) -> Any:
        if self._client is None:
            raise SpiderFarmerError("mqtt", "not connected")
        return self._client
