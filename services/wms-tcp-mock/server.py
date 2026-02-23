import socket
import threading
from datetime import datetime, timezone
from fastapi import FastAPI
import uvicorn

HOST = "0.0.0.0"
TCP_PORT = 9200
HTTP_PORT = 9201

LAST = {
    "seen_at": None,
    "message": None,
    "reply": None,
}

app = FastAPI(title="WMS Mock (TCP + HTTP)")

@app.get("/last")
def last():
    return LAST


def tcp_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, TCP_PORT))
        s.listen(5)
        print(f"[WMS][TCP] listening on {HOST}:{TCP_PORT}")

        while True:
            conn, addr = s.accept()
            with conn:
                data = conn.recv(1024).decode("utf-8", errors="ignore").strip()

                # Expect: ADD_PACKAGE|ORD-...
                if data.startswith("ADD_PACKAGE|"):
                    reply = "OK|WMS_OK\n"
                else:
                    reply = "NACK\n"

                LAST.update({
                    "seen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "message": data,
                    "reply": reply.strip(),
                })

                conn.sendall(reply.encode("utf-8"))


def main():
    # run TCP server in background thread
    t = threading.Thread(target=tcp_server, daemon=True)
    t.start()

    # run HTTP server
    print(f"[WMS][HTTP] listening on {HOST}:{HTTP_PORT}")
    uvicorn.run(app, host=HOST, port=HTTP_PORT)


if __name__ == "__main__":
    main()