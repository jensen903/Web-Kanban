from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import os


ROOT = Path(__file__).resolve().parent
PORT = 4173


def main() -> None:
    os.chdir(ROOT)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), SimpleHTTPRequestHandler)
    print(f"Preview server running at http://127.0.0.1:{PORT}")
    print(f"Serving: {ROOT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
