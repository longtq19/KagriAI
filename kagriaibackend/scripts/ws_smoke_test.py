import asyncio
import json
import websockets
import os

async def run():
    host = os.getenv("LAN_HOST", os.getenv("HOST", "198.168.88.111"))
    port = int(os.getenv("PORT", "8000"))
    uri = f"ws://{host}:{port}/ws/kagriai"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"id": "smoke-1", "text": "mấy giờ"}))
        msgs = []
        for _ in range(5):
            try:
                m = await asyncio.wait_for(ws.recv(), timeout=3)
                msgs.append(m)
                if '"type": "end"' in m or '"type":"end"' in m:
                    break
            except asyncio.TimeoutError:
                break
        print("WS msgs:", len(msgs))
        if msgs:
            print("First:", msgs[0][:200])
            print("Last:", msgs[-1][:200])

if __name__ == "__main__":
    asyncio.run(run())
