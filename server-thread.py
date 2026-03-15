from genericpath import isfile
import socket, threading
import os
import logging
import struct

logging.basicConfig(level=logging.INFO)

all_clients = []
clients_lock = threading.Lock()

class Server:
    def __init__(self):
        self.host = 'localhost'
        self.port = 5000
        self.server = None

    def open_socket(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.host, self.port))
        self.server.listen(5)

        logging.info(f"Threaded Server running at {self.host} on port {self.port}")

    def run(self):
        self.open_socket()
        try:
            while True:
                client_sock, client_addr = self.server.accept()
                c = Client(client_sock, client_addr)

                with clients_lock:
                    all_clients.append(c)

                c.start()

                logging.info(f"Client connected {client_addr}")
                self.broadcast(f"Client connected: {client_addr}", c)
        except KeyboardInterrupt:
            logging.info("Server shutting down")
        finally:
            self.server.close()

    def broadcast(self, message, sender):
        with clients_lock:
            for client in all_clients:
                if client is not sender:
                    try:
                        client.send_msg(f"[BROADCAST] {message}")
                    except:
                        pass


class Client(threading.Thread):
    def __init__(self, client, address):
        threading.Thread.__init__(self)
        self.client = client
        self.address = address
        self.size = 8192
        self.running = True

    def send_msg(self, data_str):
        data = data_str.encode()
        header = struct.pack(">I", len(data))
        self.client.sendall(header + data)

    def recv_msg(self):
        header = self.client.recv(4)
        if not header:
            return None
        
        length = struct.unpack(">I", header)[0]
        buf = b""
        while len(buf) < length:
            chunk = self.client.recv(length - len(buf))
            if not chunk: break
            buf += chunk
        return buf.decode()

    def send_file_chunked(self, filepath):
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(self.size)
                if not chunk: break
                self.client.sendall(struct.pack(">I", len(chunk)) + chunk)
        self.client.sendall(struct.pack(">I", 0))

    def recv_file_chunked(self, save_path):
        with open(save_path, "rb") as f:
            while True:
                header = self.client.recv(4)
                if not header: break
                length = struct.unpack(">I", header)[0]
                if length == 0: break
                buf = b""
                while len(buf) < length:
                    chunk = self.client.recv(length - len(buf))
                    buf += chunk

                f.write(buf)

    def run(self):
        try:
            while self.running:
                cmd_data = self.recv_msg()
                if not cmd_data:
                    break

                self.handle_command(cmd_data)
        except Exception as e:
            logging.error(f"Error with {self.address}: {e}")
        finally:
            self.cleanup()

    def handle_command(self, cmd_data):
        parts = cmd_data.split()


        if not os.path.isdir("storage"): os.mkdir("storage")

        if cmd_data.startswith("/list"):
            files = os.listdir("storage") if os.path.isdir("storage") else []
            self.send_msg("\n".join(files) if files else "Empty")
            logging.info(f"Client {self.address} uses /list")

        elif cmd_data.startswith("/download") and len(parts) > 1:
            filepath = os.path.join("storage", os.path.basename(parts[1]))
            if os.path.isfile(filepath):
                self.send_msg("OK")
                self.send_file_chunked(filepath)
            else:
                self.send_msg("Requested file not found")

        elif cmd_data.startswith("/upload") and len(parts) > 1:
            filepath = os.path.join("storage", os.path.basename(parts[1]))
            self.recv_file_chunked(filepath)
            self.send_msg("Upload finished")

    def cleanup(self):
        logging.info(f"Client {self.address} disconnected")
        self.client.close()
        self.running = False
        with clients_lock:
            if self in all_clients:
                all_clients.remove(self)

if __name__ == '__main__':
    server = Server()
    server.run()
