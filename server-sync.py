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

def handle_command(cmd_data, connection):
    if cmd_data.startswith("/list"):
        if not os.path.isdir("storage"):
            send_msg(connection, "None")
            logging.info(f"Storage directory is not found, attempt to make")

            os.mkdir("./storage")
            return

        files_str = "\n".join(os.listdir('storage'))
        logging.info(f"Files: {files_str}")
        if len(files_str) <= 0:
            send_msg(connection, "Empty")
        else:
            send_msg(connection, files_str)

    elif cmd_data.startswith("/download"):
        raw_filename = cmd_data.split()[1]
        filename = filter_filename(raw_filename)

        if not filename:
            logging.info(f"Invalid Filename: {raw_filename}")
            send_msg(connection, f"ERR_INVALID_FILENAME: {raw_filename}")
            return

        filepath = os.path.join("storage", filename)

        if not os.path.isfile(filepath):
            send_msg(connection, "ERR_NOT_FOUND")
            logging.info(f"Requested file {filename} is not found.")
            send_msg(connection, f"{filename} does not exist.")
            return

        send_msg(connection, "OK")
        logging.info(f"Sending requested file {filename}.")
        send_file_chunked(connection, f"storage/{filename}")

    elif cmd_data.startswith("/upload"):
        if not os.path.isdir("storage"):
            os.mkdir("./storage")

        parts = cmd_data.split()
        if len(parts) > 1:
            raw_filename = parts[1]
            filename = filter_filename(raw_filename)

            if not filename:
                logging.info(f"Invalid Filename: {raw_filename}")
                send_msg(connection, f"ERR_INVALID_FILENAME: {raw_filename}")
                return

            filepath = os.path.join("storage", filename)
            logging.info(f"Receiving file: {filename}")
            recv_file_chunked(connection, filepath)
            send_msg(connection, f"Successfully uploaded file: {filename}")


def filter_filename(filename):
    basename = os.path.basename(filename)
    if basename in [".", "..", ""]:
        return None
    return basename

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
            logging.info(f"Client connection from {client_address}")

            while True:
                cmd_data = recv_msg(connection)
                if not cmd_data:
                    break

                handle_command(cmd_data, connection)

    except Exception as ee:
        logging.info(f"ERROR: {str(ee)}")
    except KeyboardInterrupt:
        server.close()
        logging.info("closing")
    finally:
        logging.info("closing")
        server.close()

if __name__ == '__main__':
    start_sync_server()
