import socket

HOST = "0.0.0.0"
PORT = 9200

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen(5)
        print(f"WMS TCP Mock listening on {HOST}:{PORT}")
        while True:
            conn, addr = s.accept()
            with conn:
                data = conn.recv(1024).decode("utf-8", errors="ignore").strip()
                # Expect: ADD_PACKAGE|ORD-...
                if data.startswith("ADD_PACKAGE|"):
                    conn.sendall(b"ACK|WMS_OK\n")
                else:
                    conn.sendall(b"NACK\n")

if __name__ == "__main__":
    main()