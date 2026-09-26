# spiderfarmer

Log in to your own Spider Farmer account from Python and read your tents over the same cloud the official app uses. [MIT](LICENSE) licensed.

**No liability.** The authors of this repository accept no liability, of any kind, for anything that happens because you use, copy, modify, or rely on this software. That includes dead plants, damaged lights, fans, or controllers, a locked or banned account, lost data, wrong readings, downtime, and any claim by Spider Farmer or anyone else. There is no warranty. You use it entirely at your own risk. If you cannot accept that, do not use it.

Unofficial. Not affiliated with Spider Farmer. The cloud can change or reject this client at any time.

## Install

Python 3.11 or newer.

```bash
pip install "spiderfarmer[mqtt] @ git+https://github.com/zeroXmrcl/spider-farmer.git"
```

`spiderfarmer` without `[mqtt]` is the same install if you only need login and the device list. This package is not on PyPI. The command above installs it from GitHub.

## Quick start

One login, then every room and device on the account:

```python
from spiderfarmer import Client

client = Client()
session = client.login("you@example.com", "your password")

for room in client.rooms(session):
    for device in client.devices(session, room.id):
        print(room.name, device.name, device.serial, device.prefix, device.online)
```

`session.mqtt_name` is your email. `session.mqtt_pwd` is the broker password, a different value. `session.token` is what later REST calls send. Keep all three off GitHub, out of logs, and out of screenshots.

The password is the account password as you type it. It is not an MD5 hash.

## Live readings

Temperature and device state are not in the device list. Subscribe to the `UP` topic, then ask on `DOWN`.

```python
from spiderfarmer.mqtt import MqttSession

mqtt = MqttSession(session)
mqtt.connect()
mqtt.subscribe(device.prefix, device.serial)
mqtt.publish(device.prefix, device.serial, "getDevSta")
mqtt.close()
```

`device.prefix` is `CB` for a control box, `LC` for a light controller, and `PS` for a power strip.

Commands that start with `set` change the hardware. They are refused unless you pass `writes=True`.

```python
mqtt.publish(device.prefix, device.serial, "setLight", {"level": 40}, writes=True)
```

## What you get

| Piece | Behavior |
| --- | --- |
| `Client.login` | Email and password in, REST token and MQTT credentials out |
| `Client.rooms` / `Client.devices` | Rooms, then the devices in one room |
| `Client.call` | Any other `/api/ios/.../v2` path. `body=None` sends an empty body |
| `MqttSession` | MQTT 3.1 on `sf.mqtt.spider-farmer.com:8883`, with the broker CA pinned |

`Client(timezone="Europe/Berlin", device_id="spiderfarmer", timeout=20)` follows the Spider Farmer iOS app 2.5.2. Change `timezone` if your account is not in Berlin.

Only call this with an account you own. A wrong password comes back as code `100`. The cloud can lock that login for about two hours. An Apple-only account has no email password until you set one in the app.

<details>
<summary>Wire format</summary>

`POST https://api.spider-farmer.com/api/ios/ulogin/mailLogin/v2`

Headers: `Content-Type: application/json`, `User-Agent: Dart/3.5 (dart:io)`, and a compact `systemdata` JSON header. After login, `systemdata` also carries `token`.

The body is Base64 of AES-128-CBC ciphertext. Key `Meizhi1234567890`, IV `1234567890123456`, PKCS7 padding. The IV is not prepended. Login plaintext, with no spaces:

```json
{"email":"you@example.com","loginMethod":1,"password":"your password"}
```

`loginMethod` is the number `1`, not the string `"1"`. Success is `code` equal to `"000"`. The same key decrypts the response.

Device list sends `belonginRoomId` and `userId` as numbers. That spelling is the cloud's. Topics are `SF/GGS/{CB|PS|LC}/API/UP/{SERIAL}` and `.../DOWN/{SERIAL}`. The MQTT client id is `{userId}_{unixSeconds}`.

</details>

## No liability

Read this before you install.

The authors of this repository accept no liability whatsoever. Not for plants, harvests, or grow rooms. Not for lights, fans, controllers, power strips, or any other hardware. Not for electricity use, fire, water, heat, or humidity. Not for a locked, banned, or emptied Spider Farmer account. Not for wrong numbers, missed alarms, or a command that did something you did not expect. Not for data loss, credentials, privacy, or downtime. Not for Spider Farmer changing the API, blocking this client, or claiming you broke their terms. Not for anything else, whether or not anyone warned you it could happen.

The software is provided as is. There is no warranty of any kind, express or implied, including merchantability, fitness for a particular purpose, and non-infringement. To the maximum extent the law allows, the authors are not liable for any claim, damages, or other liability, whether in contract, tort, or otherwise, arising from this software or from your use of it.

The [MIT license](LICENSE) says the same thing in license language. The paragraphs above are the plain-language version, and they are the condition of using this repository. If you need a warranty or someone to blame, this is the wrong project.

## License

[MIT](LICENSE). You can use this in your own project. You still carry the risk described above.
