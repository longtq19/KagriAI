import os
from dotenv import load_dotenv

load_dotenv()

# Determine Base Directory (KagriAI root)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class Settings:
    PROJECT_NAME: str = "Kagri AI Server"
    API_KEY: str = os.getenv("API_KEY", "kagri-secret-key-123")
    
    # Model Configuration
    MODEL_NAME: str = os.getenv("MODEL_NAME", "qwen2.5:7b")
    MODEL_PATH: str = os.getenv("MODEL_PATH", os.path.join(BASE_DIR, "models/vistral-7b-chat-quantized.gguf"))
    N_CTX: int = int(os.getenv("N_CTX", "4096"))
    N_THREADS: int = int(os.getenv("N_THREADS", "6")) # Uses 6 cores as requested
    
    # RAG Configuration
    DOCS_PATH: str = os.path.join(BASE_DIR, "data", "docs")
    VECTOR_STORE_PATH: str = os.path.join(BASE_DIR, "data", "vector_store")
    EMBEDDING_MODEL: str = "keepitreal/vietnamese-sbert" # Or any good multilingual model
    
    # Conversation
    MAX_TURNS: int = 5 # Giữ bối cảnh nhỏ, tạm thời
    TOP_K: int = int(os.getenv("TOP_K", "40"))
    TOP_P: float = float(os.getenv("TOP_P", "0.85"))
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.1"))

    # WebSocket concurrency
    WS_MAX_CONCURRENCY: int = int(os.getenv("WS_MAX_CONCURRENCY", "5"))
    WS_MAX_QUEUE: int = int(os.getenv("WS_MAX_QUEUE", "10"))

settings = Settings()
