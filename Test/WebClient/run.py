import os
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    root = os.path.dirname(os.path.abspath(__file__))
    handler = partial(SimpleHTTPRequestHandler, directory=root)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Serving WebClient at http://{host}:{port}/")
    server.serve_forever()
