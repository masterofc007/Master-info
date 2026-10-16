import asyncio
import time
import httpx
import json
import threading
import base64
from collections import defaultdict
from flask import Flask, request, jsonify
from flask_cors import CORS
from proto import main_pb2, AccountPersonalShow_pb2
from google.protobuf import json_format
from Crypto.Cipher import AES
from urllib.parse import parse_qs

MAIN_KEY = base64.b64decode('WWcmdGMlREV1aDYlWmNeOA==')
MAIN_IV = base64.b64decode('Nm95WkRyMjJFM3ljaGpNJQ==')
RELEASEVERSION = "OB55"
USERAGENT = "Dalvik/2.1.0 (Linux; U; Android 13; CPH2095 Build/RKQ1.211119.001)"
SUPPORTED_REGIONS = ["IND", "BR", "US", "SAC", "NA", "SG", "RU", "ID", "TW", "VN", "TH", "ME", "PK", "CIS", "BD", "EUROPE"]

app = Flask(__name__)
CORS(app)
cached_tokens = defaultdict(dict)
uid_region_cache = {}

# === Helpers ===

def pad(text: bytes) -> bytes:
    n = AES.block_size - (len(text) % AES.block_size)
    return text + bytes([n] * n)

def aes_cbc_encrypt(key: bytes, iv: bytes, plaintext: bytes) -> bytes:
    return AES.new(key, AES.MODE_CBC, iv).encrypt(pad(plaintext))

def decode_protobuf(data: bytes, msg_type):
    inst = msg_type()
    inst.ParseFromString(data)
    return inst

def get_account_credentials(region: str) -> str:
    r = region.upper()
    if r == "IND":
        return "uid=4363983977&password=ISHITA_0AFN5_BY_SPIDEERIO_GAMING_UY12H"
    elif r in {"BR", "US", "SAC", "NA"}:
        return "uid=4682784982&password=GHOST_TNVW1_RIZER_QTFT0"
    else:
        return "uid=4418979127&password=RIZER_K4CY1_RIZER_WNX02"

# === Token Generation (Parallel, Inline Encoded) ===

async def create_jwt(region: str):
    try:
        creds = parse_qs(get_account_credentials(region))
        uid = creds.get("uid", [""])[0]
        password = creds.get("password", [""])[0]
        _z = base64.b64decode("aHR0cHM6Ly9mbGFzaC10" + "b2tlbi12Mi52ZXJjZWwu" + "YXBwL3Rva2Vu").decode()
        _y = base64.b64decode("Rmxh" + "c2g=").decode()
        url = f"{_z}?uid={uid}&password={password}&key={_y}"
        headers = {"User-Agent": USERAGENT, "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=headers)
            msg = resp.json()
            cached_tokens[region] = {
                'token': f"Bearer {msg.get('token','0')}",
                'region': msg.get('lockRegion') or msg.get('region') or region,
                'server_url': msg.get('serverUrl','0'),
                'expires_at': msg.get('expiry_time', time.time() + 25200)
            }
    except:
        pass

async def initialize_tokens():
    await asyncio.gather(*[create_jwt(r) for r in SUPPORTED_REGIONS], return_exceptions=True)

async def refresh_tokens_periodically():
    while True:
        await asyncio.sleep(25200)
        await initialize_tokens()

async def get_token_info(region: str):
    info = cached_tokens.get(region)
    if info and time.time() < info['expires_at'] - 60:
        return info['token'], info['region'], info['server_url']
    await create_jwt(region)
    info = cached_tokens[region]
    return info['token'], info['region'], info['server_url']

async def GetAccountInformation(uid, unk, region, endpoint):
    req = main_pb2.GetPlayerPersonalShow()
    json_format.ParseDict({'a': uid, 'b': unk}, req)
    data_enc = aes_cbc_encrypt(MAIN_KEY, MAIN_IV, req.SerializeToString())
    token, lock, server = await get_token_info(region)
    headers = {
        'User-Agent': USERAGENT,
        'Connection': "Keep-Alive",
        'Accept-Encoding': "gzip",
        'Content-Type': "application/octet-stream",
        'Expect': "100-continue",
        'Authorization': token,
        'X-Unity-Version': "2018.4.11f1",
        'X-GA': "v1 1",
        'ReleaseVersion': RELEASEVERSION
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(server + endpoint, data=data_enc, headers=headers)
        return json.loads(json_format.MessageToJson(
            decode_protobuf(resp.content, AccountPersonalShow_pb2.AccountPersonalShowInfo)
        ))

# === Routes ===

@app.route('/player-info')
def get_account_info():
    uid = request.args.get('uid')
    if not uid:
        return jsonify({"error": "Please provide UID."}), 400

    if uid in uid_region_cache:
        try:
            data = asyncio.run(GetAccountInformation(uid, "7", uid_region_cache[uid], "/GetPlayerPersonalShow"))
            return json.dumps(data, indent=2, ensure_ascii=False), 200, {'Content-Type': 'application/json; charset=utf-8'}
        except:
            pass

    for region in SUPPORTED_REGIONS:
        try:
            data = asyncio.run(GetAccountInformation(uid, "7", region, "/GetPlayerPersonalShow"))
            uid_region_cache[uid] = region
            return json.dumps(data, indent=2, ensure_ascii=False), 200, {'Content-Type': 'application/json; charset=utf-8'}
        except:
            continue

    return jsonify({"error": "UID not found in any region."}), 404

def start_background_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    async def runner():
        await initialize_tokens()
        asyncio.create_task(refresh_tokens_periodically())
        while True:
            await asyncio.sleep(3600)
    loop.run_until_complete(runner())

if __name__ == '__main__':
    threading.Thread(target=start_background_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)