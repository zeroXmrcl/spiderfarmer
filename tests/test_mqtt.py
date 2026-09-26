import json
import ssl
import unittest

from spiderfarmer.errors import SpiderFarmerError
from spiderfarmer.models import Session, topic_prefix
from spiderfarmer.mqtt import MqttSession, bundled_ca, command, ssl_context, topics


def _session() -> Session:
    return Session(token="rest-token", mqtt_name="a@b.c", mqtt_pwd="broker-secret", user_id="42", raw={})


class TopicTests(unittest.TestCase):
    def test_prefixes(self) -> None:
        self.assertEqual(topic_prefix("SF-GGS-CB"), "CB")
        self.assertEqual(topic_prefix("SF-GGS-LC"), "LC")
        self.assertEqual(topic_prefix("SF-GGS-PS10"), "PS")

    def test_topic_strings(self) -> None:
        up, down = topics("cb", "aa:bb:cc:dd:ee:ff")
        self.assertEqual(up, "SF/GGS/CB/API/UP/AABBCCDDEEFF")
        self.assertEqual(down, "SF/GGS/CB/API/DOWN/AABBCCDDEEFF")

    def test_unknown_prefix(self) -> None:
        with self.assertRaises(SpiderFarmerError):
            topics("ZZ", "ABC")


class PublishTests(unittest.TestCase):
    def test_get_dev_sta_payload(self) -> None:
        payload = command("getDevSta", "AABBCCDDEEFF", None, now_ms=1234)
        self.assertEqual(
            payload,
            {"method": "getDevSta", "params": {"pid": "AABBCCDDEEFF"}, "msgId": "1234"},
        )

    def test_set_is_refused_until_writes_are_enabled(self) -> None:
        session = MqttSession(_session())

        class Fake:
            def publish(self, topic, payload, qos=0):  # noqa: ANN001
                self.topic = topic
                self.payload = payload

        session._client = Fake()
        with self.assertRaises(SpiderFarmerError) as caught:
            session.publish("CB", "ABC", "setLight", now_ms=1)
        self.assertEqual(caught.exception.code, "write")
        down, payload = session.publish("CB", "ABC", "setLight", {"level": 10}, writes=True, now_ms=5)
        self.assertEqual(down, "SF/GGS/CB/API/DOWN/ABC")
        self.assertEqual(json.loads(session._client.payload)["method"], "setLight")
        self.assertEqual(payload["params"]["level"], 10)


class TlsTests(unittest.TestCase):
    def test_context_requires_the_pinned_ca_and_drops_strict(self) -> None:
        context = ssl_context(bundled_ca())
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        strict = getattr(ssl, "VERIFY_X509_STRICT", 0)
        if strict:
            self.assertEqual(context.verify_flags & strict, 0)
