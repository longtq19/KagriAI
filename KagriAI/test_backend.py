import asyncio
import json
import base64
import io
from PIL import Image
import requests
import websockets

BASE_HTTP = "http://127.0.0.1:8001"
WS_URL = "ws://127.0.0.1:8001/ws/kagri-ai"

def make_dummy_image_b64() -> str:
    img = Image.new("RGB", (64, 64), color=(200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")

def test_http_health():
    try:
        r = requests.get(BASE_HTTP + "/")
        print("HTTP / status:", r.status_code, r.text[:200])
    except Exception as e:
        print("HTTP / error:", e)

def test_http_openapi():
    try:
        r = requests.get(BASE_HTTP + "/openapi.json", timeout=5)
        print("HTTP /openapi.json:", r.status_code)
    except Exception as e:
        print("OpenAPI error:", e)

def test_http_diagnose():
    try:
        payload = {"image": make_dummy_image_b64()}
        r = requests.post(BASE_HTTP + "/api/diagnose/durian", json=payload, timeout=10)
        print("Diagnose durian:", r.status_code, r.text[:200])
    except Exception as e:
        print("Diagnose error:", e)

def test_http_convert():
    try:
        r1 = requests.post(BASE_HTTP + "/api/convert/lunar-to-solar", json={"date": "ngày 01 tháng 01 năm 2026"}, timeout=10)
        print("Convert lunar->solar:", r1.status_code, r1.text[:200])
        r2 = requests.post(BASE_HTTP + "/api/convert/solar-to-lunar", json={"date": "06/01/2026"}, timeout=10)
        print("Convert solar->lunar:", r2.status_code, r2.text[:200])
    except Exception as e:
        print("Convert API error:", e)

async def test_ws_chat():
    try:
        async with websockets.connect(WS_URL) as ws:
            await ws.send("Thông tin công ty")
            print("WS sent: Thông tin công ty")
            # Read a few messages then stop
            for _ in range(15):
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=15)
                    print("WS recv:", msg[:200])
                    data = json.loads(msg)
                    if data.get("type") == "end":
                        break
                except asyncio.TimeoutError:
                    print("WS timeout waiting for message")
                    break
    except Exception as e:
        print("WS connect/send error:", e)

def main():
    print("== Test HTTP ==")
    test_http_health()
    test_http_openapi()
    test_http_diagnose()
    test_http_convert()
    print("\n== Test WebSocket ==")
    asyncio.run(test_ws_chat())
    print("\n== Test WebSocket: Convert Lunar->Solar ==")
    async def test_ws_convert():
        try:
            async with websockets.connect(WS_URL) as ws:
                msg = "Ngày 01 tháng 01 năm 2026 âm lịch là ngày bao nhiêu dương"
                await ws.send(msg)
                print("WS sent:", msg)
                for _ in range(20):
                    try:
                        resp = await asyncio.wait_for(ws.recv(), timeout=10)
                        print("WS recv:", resp[:200])
                        data = json.loads(resp)
                        if data.get("type") == "end":
                            break
                    except asyncio.TimeoutError:
                        print("WS timeout waiting for message")
                        break
        except Exception as e:
            print("WS convert error:", e)
    asyncio.run(test_ws_convert())

if __name__ == "__main__":
    main()
