import os
import uvicorn

def to_bool(x: str) -> bool:
    return str(x).lower() not in ["0", "false", "no"]

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload_flag = to_bool(os.getenv("RELOAD", "1"))
    uvicorn.run("app.main:app", host=host, port=port, reload=reload_flag)
