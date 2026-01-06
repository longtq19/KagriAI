# KagriAI — Hướng dẫn Sử Dụng

KagriAI là hệ thống trợ lý AI tiếng Việt cho nông nghiệp, gồm:
- Backend FastAPI phục vụ WebSocket/REST, xử lý RAG, chẩn đoán bệnh cây trồng
- WebClient giao diện web nhẹ (static)
- TTS server tùy chọn (giọng đọc chất lượng cao)

## Cấu Trúc Dự Án
- Backend: [KagriAI](file:///Users/kagritech/Desktop/KagriAI/KagriAI)
  - Ứng dụng FastAPI: [run_server.py](file:///Users/kagritech/Desktop/KagriAI/KagriAI/run_server.py), [main.py](file:///Users/kagritech/Desktop/KagriAI/KagriAI/app/main.py)
  - WebSocket: [websocket.py](file:///Users/kagritech/Desktop/KagriAI/KagriAI/app/api/websocket.py)
  - Cấu hình: [config.py](file:///Users/kagritech/Desktop/KagriAI/KagriAI/app/core/config.py)
  - Dịch vụ AI: [llm_engine.py](file:///Users/kagritech/Desktop/KagriAI/KagriAI/app/services/llm_engine.py), [hybrid_search.py](file:///Users/kagritech/Desktop/KagriAI/KagriAI/app/services/hybrid_search.py)
  - Chẩn đoán bệnh: [diagnosis.py](file:///Users/kagritech/Desktop/KagriAI/KagriAI/app/services/diagnosis.py)
- WebClient: [Test/WebClient](file:///Users/kagritech/Desktop/KagriAI/Test/WebClient)
  - Ứng dụng tĩnh: [index.html](file:///Users/kagritech/Desktop/KagriAI/Test/WebClient/index.html), [app.js](file:///Users/kagritech/Desktop/KagriAI/Test/WebClient/app.js), [styles.css](file:///Users/kagritech/Desktop/KagriAI/Test/WebClient/styles.css)
  - Cấu hình id: [id_config.json](file:///Users/kagritech/Desktop/KagriAI/Test/WebClient/id_config.json)
  - TTS server: [tts_server.py](file:///Users/kagritech/Desktop/KagriAI/Test/WebClient/tts_server.py)

## Yêu Cầu Môi Trường
- Python 3.9+
- Khuyến nghị tạo venv và cài dependencies theo `KagriAI/requirements.txt`
- Trình duyệt hiện đại (Chrome/Edge/Firefox)

## Khởi Chạy Nhanh
1) Backend FastAPI:
```bash
cd KagriAI
python3 run_server.py
```
- Server chạy tại: http://127.0.0.1:8001

2) WebClient (static):
```bash
cd Test/WebClient
python3 -m http.server 8000
```
- Truy cập: http://localhost:8000

3) TTS server (tùy chọn, giọng đọc chất lượng cao):
```bash
cd Test/WebClient
python3 tts_server.py
```
- API TTS: http://127.0.0.1:5500

## Cấu Hình ID Cho WebClient
- Sửa file: [id_config.json](file:///Users/kagritech/Desktop/KagriAI/Test/WebClient/id_config.json)
```json
{
  "client_id": "webclient-local-1"
}
```
- WebClient sẽ đọc `client_id` và gắn vào mọi yêu cầu WebSocket.

## Giao Thức WebSocket
- URL: `ws://127.0.0.1:8001/ws/kagri-ai`
- Mọi yêu cầu bắt buộc là JSON có `id`. Mọi phản hồi đều kèm `id`.
- Bối cảnh trò chuyện được lưu theo `id`, tối đa 5 lượt (cặp yêu cầu/đáp ứng) gần nhất và được xoá khi client (id đó) ngắt kết nối.

### Giới Hạn Đồng Thời & Hàng Đợi
- Tham số tại: [config.py](file:///Users/kagritech/Desktop/KagriAI/KagriAI/app/core/config.py)
  - `WS_MAX_CONCURRENCY` (mặc định 5): số yêu cầu xử lý đồng thời
  - `WS_MAX_QUEUE` (mặc định 10): số yêu cầu tối đa chờ trong hàng đợi
- Áp dụng trong: [websocket.py](file:///Users/kagritech/Desktop/KagriAI/KagriAI/app/api/websocket.py)
  - ConnectionManager tạo semaphore và hàng đợi từ `settings.WS_MAX_CONCURRENCY` và `settings.WS_MAX_QUEUE`

### Định Dạng Yêu Cầu
- Text:
```json
{
  "id": "webclient-local-1",
  "type": "text",
  "text": "Xin chào, cho tôi hỏi giá cà phê hôm nay?"
}
```
- Chẩn đoán qua ảnh:
```json
{
  "id": "webclient-local-1",
  "type": "image_query",
  "text": "Chẩn đoán bệnh cho lá sầu riêng này",
  "image_base64": "data:image/png;base64,iVBORw0KGgoAAA..."
}
```

### Định Dạng Phản Hồi
- Dòng tiến trình:
```json
{ "id": "webclient-local-1", "type": "start" }
{ "id": "webclient-local-1", "type": "stream", "content": "..." }
{ "id": "webclient-local-1", "type": "end" }
```
- Lỗi:
```json
{ "id": "webclient-local-1", "type": "error", "content": "Thông điệp lỗi" }
```

## API REST (Chẩn Đoán Ảnh)
- POST /api/diagnose/durian
- POST /api/diagnose/coffee
- Tham khảo: [main.py](file:///Users/kagritech/Desktop/KagriAI/KagriAI/app/main.py)

## Cấu Hình & Tham Số Mô Hình
- Nhiều tham số nằm trong: [config.py](file:///Users/kagritech/Desktop/KagriAI/KagriAI/app/core/config.py)
- MAX_TURNS = 5 đảm bảo bối cảnh ngắn gọn và ổn định.

### Tham Số LLM
- File tham chiếu: [llm_engine.py](file:///Users/kagritech/Desktop/KagriAI/KagriAI/app/services/llm_engine.py)
- Model mặc định: đọc từ `settings.MODEL_NAME` (Ollama), cấu hình trong [config.py](file:///Users/kagritech/Desktop/KagriAI/KagriAI/app/core/config.py)
- Tham số điều chỉnh:
  - `settings.N_CTX` (mặc định 4096): ngữ cảnh tối đa
  - `settings.TEMPERATURE` (mặc định 0.1): độ ngẫu nhiên
  - `TOP_K`, `TOP_P`: điều khiển sampling
  - `num_predict` khi gọi generate_stream: giới hạn token phản hồi
- Các tham số trên đọc từ biến môi trường (khi có), giá trị mặc định nằm trong [config.py](file:///Users/kagritech/Desktop/KagriAI/KagriAI/app/core/config.py)

#### Cấu hình qua biến môi trường
Ví dụ trên macOS/zsh:

```bash
export N_CTX=8192
export TEMPERATURE=0.2
export TOP_K=40
export TOP_P=0.9
```

Khởi động lại server sau khi thiết lập.

#### Đổi model Ollama
- Đặt biến môi trường `MODEL_NAME`, ví dụ:
  ```bash
  export MODEL_NAME="llama3.2:3b"
  ```
  hoặc chỉnh trong [config.py](file:///Users/kagritech/Desktop/KagriAI/KagriAI/app/core/config.py).
- Đảm bảo model đã được `ollama pull` trên máy.

## Ghi Chú Vận Hành
- Nếu WS không nhận JSON hoặc thiếu `id`, server sẽ đóng kết nối với mã WS_1008_POLICY_VIOLATION.
- Khi tải ảnh để chẩn đoán, đảm bảo ảnh rõ nét, tập trung vết bệnh, ánh sáng tốt, khoảng cách 30–50 cm.
- TTS server sử dụng Edge-TTS, nếu không chạy TTS local, WebClient có thể fallback dùng TTS của trình duyệt (chất lượng thấp hơn).

## Hướng Dẫn Chi Tiết WS Clients Test
### Dùng WebClient
- Mặc định kết nối WS: `ws://127.0.0.1:8001/ws/kagri-ai`
- Có thể override qua query:
  - `http://localhost:8000/?ws=ws://127.0.0.1:8001/ws/kagri-ai`
  - `http://localhost:8000/?tts=http://127.0.0.1:5500`
- Cấu hình id tại: [id_config.json](file:///Users/kagritech/Desktop/KagriAI/Test/WebClient/id_config.json)

### Dùng Python (thư viện websockets)
Ví dụ script kiểm tra gửi text:

```python
import asyncio
import json
import websockets

WS_URL = "ws://127.0.0.1:8001/ws/kagri-ai"
CLIENT_ID = "test-client-001"

async def main():
    async with websockets.connect(WS_URL) as ws:
        payload = {"id": CLIENT_ID, "type": "text", "text": "Xin chào, giá cà phê hôm nay?"}
        await ws.send(json.dumps(payload))
        while True:
            msg = await ws.recv()
            print("<<", msg)

asyncio.run(main())
```

Ví dụ kiểm tra gửi ảnh:

```python
import asyncio, json, websockets, base64

WS_URL = "ws://127.0.0.1:8001/ws/kagri-ai"
CLIENT_ID = "test-client-002"

async def main():
    with open("sample.jpg", "rb") as f:
        b64 = "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()
    async with websockets.connect(WS_URL) as ws:
        payload = {"id": CLIENT_ID, "type": "image_query", "text": "Chẩn đoán bệnh", "image_base64": b64}
        await ws.send(json.dumps(payload))
        while True:
            print("<<", await ws.recv())

asyncio.run(main())
```

### Kiểm Tra Giới Hạn Đồng Thời/Hàng Đợi
Ví dụ tạo 12 yêu cầu song song để quan sát giới hạn 5 đồng thời và hàng đợi tối đa 10:

```python
import asyncio, json, websockets, random
WS_URL = "ws://127.0.0.1:8001/ws/kagri-ai"

async def send_one(i):
    cid = f"loadtest-{i}"
    try:
        async with websockets.connect(WS_URL) as ws:
            payload = {"id": cid, "type": "text", "text": f"Yêu cầu số {i}"}
            await ws.send(json.dumps(payload))
            while True:
                print(i, ">>", await ws.recv())
    except Exception as e:
        print(i, "error", e)

async def main():
    tasks = [asyncio.create_task(send_one(i)) for i in range(12)]
    await asyncio.gather(*tasks)

asyncio.run(main())
```

Một số yêu cầu có thể bị từ chối khi hàng đợi vượt ngưỡng 10 (server trả thông điệp lỗi và đóng kết nối).

## Tham Số TTS
- TTS voice có thể đặt qua biến môi trường `TTS_VOICE` trong TTS server:
  - File: [tts_server.py](file:///Users/kagritech/Desktop/KagriAI/Test/WebClient/tts_server.py)
  - Ví dụ:
    ```bash
    export TTS_VOICE="vi-VN-HoaiMyNeural"
    ```
## Khắc Phục Sự Cố
- WS không phản hồi:
  - Kiểm tra backend đã chạy tại http://127.0.0.1:8001
  - Kiểm tra payload gửi lên có `id` và đúng JSON
  - Kiểm tra hàng đợi có vượt quá 10 yêu cầu
- TTS không phát:
  - Chạy `python3 tts_server.py` và mở lại WebClient
  - Kiểm tra quyền autoplay âm thanh của trình duyệt

## Giấy Phép
- Mã nguồn nội bộ KagriAI. Vui lòng liên hệ quản trị dự án để biết thêm chi tiết sử dụng/triển khai.
