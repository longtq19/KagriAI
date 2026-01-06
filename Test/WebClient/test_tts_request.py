import requests
import json

url = "http://localhost:5050/tts"
payload = {"text": "Xin chào, đây là kiểm tra âm thanh."}
headers = {"Content-Type": "application/json"}

try:
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        with open("test_output.mp3", "wb") as f:
            f.write(response.content)
        print(f"Success! Saved test_output.mp3 ({len(response.content)} bytes)")
    else:
        print(f"Error: {response.status_code} - {response.text}")
except Exception as e:
    print(f"Exception: {e}")
