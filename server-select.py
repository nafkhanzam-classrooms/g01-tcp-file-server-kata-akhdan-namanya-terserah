import socket
import logging
import struct
import select
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
            header = sock.recv(4)
            if not header: break
            
            length = struct.unpack(">I", header)[0]
            
            if length == 0:
                break
                
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

def handle_command(cmd_data, connection, all_socket, server_socket):
    if not os.path.isdir("storage"):
        os.mkdir("./storage")

    if cmd_data.startswith("/list"):
        logging.info(f"Client {connection.getpeername()} uses /list")

        files = os.listdir("storage") if os.path.isdir("storage") else []
        send_msg(connection, "\n".join(files) if files else "Empty")

    elif cmd_data.startswith("/download"):
        logging.info(f"Client {connection.getpeername()} uses /download")
        raw_filename = cmd_data.split()[1]
        filename = filter_filename(raw_filename, connection)

        if not filename:
            return

        filepath = os.path.join("storage", filename)

        if not os.path.isfile(filepath):
            logging.info(f"Requested file not found: {filename} for client {connection.getpeername()}")
            send_msg(connection, f"Requested file not found")
            return

        send_msg(connection, "OK")
        logging.info(f"Sending requested file {filename}.")
        send_file_chunked(connection, f"storage/{filename}")

    elif cmd_data.startswith("/upload"):
        logging.info(f"Client {connection.getpeername()} uses /upload")

        parts = cmd_data.split()
        if len(parts) > 1:
            raw_filename = parts[1]
            filename = filter_filename(raw_filename, connection)

            if not filename:
                return

            filepath = os.path.join("storage", filename)
            recv_file_chunked(connection, filepath)
            send_msg(connection, "Upload finished.")
            logging.info(f"Client {connection.getpeername()} uses /upload, uploaded file: {filename}")

def broadcast_message(message, sender_socket, all_socket, server_socket):
    for sock in all_socket:
        if sock is not server_socket and sock is not sender_socket:
            try:
                send_msg(sock, f"[BROADCAST] {message}")
            except:
                pass

def filter_filename(filename, sock):
    basename = os.path.basename(filename)
    if basename in [".", "..", ""]:
        logging.info(f"Error when using /upload or /download by {sock.getpeername()} - invalid filename")
        send_msg(sock, f"Invalid file name")
        return None
    return basename

def start_select_server(host='127.0.0.1', port=5000):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(5)
    server.setblocking(False)

    logging.info(f"Server is listening at address {host} on port {port}")

    client_sockets = [server]

    try:
        while True:
            socket_ready, _, _ = select.select(client_sockets, [], [])

            for s in socket_ready:
                if s is server:
                    connection, client_addr = server.accept()
                    connection.setblocking(False)
                    client_sockets.append(connection)
    
                    logging.info(f"Client connected: {client_addr}")
                    broadcast_message(f"Client connected: {client_addr} joined.", connection, client_sockets, server)
                else:
                    try:
                        cmd_data = recv_msg(s)
                        if cmd_data:
                            handle_command(cmd_data, s, client_sockets, server)
                        else:
                            try:
                                addr = s.getpeername()
                            except:
                                addr = "Unknown"

                            logging.info(f"Client {addr} disconnected")

                            if s in client_sockets:
                                client_sockets.remove(s)
                            s.close()

                            broadcast_message(f"User {addr} has left.", None, client_sockets, server)
                    except Exception as ee:
                        logging.info(f"ERROR: {str(ee)}")

    except Exception as ee:
        logging.info(f"ERROR: {str(ee)}")
    except KeyboardInterrupt:
        server.close()
        logging.info("closing")

if __name__ == '__main__':
    start_select_server()
