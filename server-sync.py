import socket
import logging
import struct
import os

logging.basicConfig(level=logging.INFO)

def send_msg(sock, data_str):
    data = data_str.encode()
    header = struct.pack(">I", len(data))
    sock.sendall(header + data)

def recv_msg(sock):
    header = sock.recv(4)
    if not header: return None
    length = struct.unpack(">I", header)[0]
    buf = b""
    while len(buf) < length:
        buf += sock.recv(length - len(buf))
    return buf.decode()

def recv_file_chunked(sock, save_path):
    with open(save_path, "wb") as f:
        while True:
            # Read the 4-byte length prefix
            header = sock.recv(4)
            if not header: break
            
            length = struct.unpack(">I", header)[0]
            
            if length == 0: # Sentinel value detected
                break
                
            # Read exactly 'length' bytes for this chunk
            buf = b""
            while len(buf) < length:
                chunk = sock.recv(length - len(buf))
                if not chunk: break
                buf += chunk
            f.write(buf)

def send_file_chunked(sock, path):
    with open(path, "rb") as f:
        while True:
            chunk = f.read(4096)
            if not chunk: break
            sock.sendall(struct.pack(">I", len(chunk)) + chunk)
    sock.sendall(struct.pack(">I", 0)) # Sentinel value

def start_sync_server(host='127.0.0.1', port=5000):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(5)

    logging.info(f"Server is listening at address {host} on port {port}")

    try:
        while True:
            logging.info("waiting for connection")
            connection, client_address = server.accept()
            logging.info(f"connection from {client_address}")

            while True:
                cmd_data = recv_msg(connection)
                if not cmd_data:
                    break

                if cmd_data.startswith("/list"):
                    files_str = ", ".join(os.listdir('storage'))
                    send_msg(connection, files_str)

                elif cmd_data.startswith("/download"):
                    filename = cmd_data.split()[1]
                    send_file_chunked(connection, f"storage/{filename}")

                elif cmd_data.startswith("/upload"):
                    parts = cmd_data.split()
                    if len(parts) > 1:
                        filename = parts[1]
                        logging.info(f"Receiving file: {filename}")
                        recv_file_chunked(connection, f"storage/{filename}")
                        send_msg(connection, f"Successfully uploaded file: {filename}")
                    

    except Exception as ee:
        logging.info(f"ERROR: {str(ee)}")
    finally:
        logging.info("closing")
        server.close()

if __name__ == '__main__':
    start_sync_server()
