import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class Settings:
    PROJECT_NAME: str = "Kagri AI Server"
    API_KEY: str = os.getenv("API_KEY", "kagri-secret-key-123")
    MODEL_NAME: str = os.getenv("MODEL_NAME", "qwen2.5:7b")
    MODEL_PATH: str = os.getenv("MODEL_PATH", os.path.join(BASE_DIR, "models/vistral-7b-chat-quantized.gguf"))
    N_CTX: int = int(os.getenv("N_CTX", "4096"))
    DOCS_PATH: str = os.path.join(BASE_DIR, "data", "docs")
    VECTOR_STORE_PATH: str = os.path.join(BASE_DIR, "data", "vector_store")
    EMBEDDING_MODEL: str = "keepitreal/vietnamese-sbert"
    MAX_TURNS: int = 5
    TOP_K: int = int(os.getenv("TOP_K", "40"))
    TOP_P: float = float(os.getenv("TOP_P", "0.85"))
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.1"))
    WS_DISCONNECT_TTL_SECONDS: int = int(os.getenv("WS_DISCONNECT_TTL_SECONDS", "300"))

settings = Settings()
