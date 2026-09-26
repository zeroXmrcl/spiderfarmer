import json
import unittest

from spiderfarmer import Client, SpiderFarmerError
from spiderfarmer.envelope import decrypt_body, encrypt_body
from spiderfarmer.models import Session


def _response(text: str, status: int = 200):
    class Response:
        def __init__(self) -> None:
            self.text = text
            self.status_code = status

    return Response()


def _session() -> Session:
    return Session(token="rest-token", mqtt_name="a@b.c", mqtt_pwd="broker-secret", user_id="42", raw={})


class LoginTests(unittest.TestCase):
    def test_posts_encrypted_ios_v2_body(self) -> None:
        seen: dict[str, object] = {}

        def post(url, data=None, headers=None, timeout=None):  # noqa: ANN001
            seen["url"] = url
            seen["data"] = data
            seen["headers"] = headers
            seen["timeout"] = timeout
            return _response(
                encrypt_body(
                    {
                        "code": "000",
                        "msg": "success",
                        "data": {
                            "mqttName": "a@b.c",
                            "mqttPwd": "broker-secret",
                            "userId": 42,
                            "token": "rest-token",
                        },
                    }
                )
            )

        session = Client(post=post).login("a@b.c", "secret", now_s=1_700_000_000)
        self.assertEqual(seen["url"], "https://api.spider-farmer.com/api/ios/ulogin/mailLogin/v2")
        self.assertEqual(seen["timeout"], 20)
        headers = seen["headers"]
        assert isinstance(headers, dict)
        self.assertEqual(headers["User-Agent"], "Dart/3.5 (dart:io)")
        system = json.loads(headers["systemdata"])
        self.assertEqual(system["appVersion"], "2.5.2")
        self.assertEqual(system["osType"], "iOS")
        self.assertEqual(system["timestamp"], 1_700_000_000)
        self.assertEqual(system["reqId"], 1_700_000_000_001)
        self.assertNotIn("token", system)
        self.assertEqual(
            decrypt_body(seen["data"]),
            {"email": "a@b.c", "loginMethod": 1, "password": "secret"},
        )
        self.assertIsInstance(decrypt_body(seen["data"])["loginMethod"], int)
        self.assertEqual(session.user_id, "42")
        self.assertEqual(session.mqtt_name, "a@b.c")
        self.assertEqual(session.token, "rest-token")

    def test_bad_password_does_not_echo_the_password(self) -> None:
        def post(url, data=None, headers=None, timeout=None):  # noqa: ANN001
            return _response(json.dumps({"code": "100", "msg": "The password entered is incorrect.", "data": None}))

        with self.assertRaises(SpiderFarmerError) as caught:
            Client(post=post).login("a@b.c", "secret-value", now_s=1)
        self.assertEqual(caught.exception.code, "100")
        self.assertNotIn("secret-value", str(caught.exception))

    def test_missing_user_id_is_an_error(self) -> None:
        def post(url, data=None, headers=None, timeout=None):  # noqa: ANN001
            return _response(
                encrypt_body(
                    {
                        "code": "000",
                        "data": {"mqttName": "a@b.c", "mqttPwd": "broker-secret", "token": "rest-token"},
                    }
                )
            )

        with self.assertRaises(SpiderFarmerError) as caught:
            Client(post=post).login("a@b.c", "secret", now_s=1)
        self.assertEqual(caught.exception.msg, "missing userId")


class InventoryTests(unittest.TestCase):
    def test_rooms_use_an_empty_body_and_read_the_name(self) -> None:
        seen: dict[str, object] = {}

        def post(url, data=None, headers=None, timeout=None):  # noqa: ANN001
            seen["url"] = url
            seen["data"] = data
            seen["headers"] = headers
            return _response(
                encrypt_body(
                    {
                        "code": "000",
                        "data": [{"id": 7, "userId": 42, "roomName": "Tent", "isDelete": 0}],
                    }
                )
            )

        rooms = Client(post=post).rooms(_session(), now_s=50)
        self.assertIsNone(seen["data"])
        self.assertIn("token", json.loads(seen["headers"]["systemdata"]))
        self.assertEqual(rooms[0].id, 7)
        self.assertEqual(rooms[0].name, "Tent")
        self.assertTrue(seen["url"].endswith("/api/ios/udm/getUserRooms/v2"))

    def test_devices_send_room_and_user_ids(self) -> None:
        seen: dict[str, object] = {}

        def post(url, data=None, headers=None, timeout=None):  # noqa: ANN001
            seen["data"] = data
            return _response(
                encrypt_body(
                    {
                        "code": "000",
                        "data": [
                            {
                                "deviceSerialnum": "AABBCCDDEEFF",
                                "deviceName": "Control",
                                "productType": "SF-GGS-CB",
                                "belonginRroom": 7,
                                "connectStatus": 1,
                            }
                        ],
                    }
                )
            )

        devices = Client(post=post).devices(_session(), 7, now_s=50)
        self.assertEqual(decrypt_body(seen["data"]), {"belonginRoomId": 7, "userId": 42})
        self.assertEqual(devices[0].serial, "AABBCCDDEEFF")
        self.assertEqual(devices[0].prefix, "CB")
        self.assertEqual(devices[0].room_id, 7)
        self.assertTrue(devices[0].online)


class ReplayTests(unittest.TestCase):
    def test_two_calls_in_the_same_second_use_different_request_ids(self) -> None:
        seen: list[int] = []

        def post(url, data=None, headers=None, timeout=None):  # noqa: ANN001
            seen.append(json.loads(headers["systemdata"])["reqId"])
            return _response(json.dumps({"code": "000", "data": []}))

        client = Client(post=post)
        client.rooms(_session(), now_s=1_700_000_000)
        client.rooms(_session(), now_s=1_700_000_000)
        self.assertEqual(seen, [1_700_000_000_001, 1_700_000_000_002])


class EnvelopeTests(unittest.TestCase):
    def test_block_aligned_plaintext_still_roundtrips(self) -> None:
        body = {"email": "abcd@ef.gh", "loginMethod": 1, "password": "0123456789abcdef0123456789ab"}
        raw = json.dumps(body, separators=(",", ":")).encode()
        self.assertEqual(len(raw) % 16, 0)
        self.assertEqual(decrypt_body(encrypt_body(body)), body)
