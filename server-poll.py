import socket
import logging
import struct
import select
import os

logging.basicConfig(level=logging.INFO)

active_downloads = {}
active_uploads = {}

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

def handle_command(cmd_data, sock, poll_obj):
    fd = sock.fileno()

    if cmd_data.startswith("/list"):
        if not os.path.isdir("storage"):
            send_msg(sock, "None")
            logging.info(f"Storage directory is not found, attempt to make")

            os.mkdir("./storage")
            return

        files_str = "\n".join(os.listdir('storage'))
        logging.info(f"Files: {files_str}")
        if len(files_str) <= 0:
            send_msg(sock, "Empty")
        else:
            send_msg(sock, files_str)

    elif cmd_data.startswith("/download"):
        raw_filename = cmd_data.split()[1]
        filename = filter_filename(raw_filename)

        if not filename:
            logging.info(f"Invalid Filename: {raw_filename}")
            send_msg(sock, f"Invalid file name")
            return

        filepath = os.path.join("storage", filename)

        if not os.path.isfile(filepath):
            logging.info(f"Requested file {filename} is not found.")
            send_msg(sock, f"{filename} does not exist.")
            return

        send_msg(sock, "OK")
        logging.info(f"Sending requested file {filename}.")
        active_downloads[fd] = open(filepath, "rb")
        poll_obj.modify(fd, select.POLLIN | select.POLLOUT)

    elif cmd_data.startswith("/upload"):
        if not os.path.isdir("storage"):
            os.mkdir("./storage")

        parts = cmd_data.split()
        if len(parts) > 1:
            raw_filename = parts[1]
            filename = filter_filename(raw_filename)

            if not filename:
                logging.info(f"Invalid Filename: {raw_filename}")
                send_msg(sock, f"Invalid file name")
                return

            filepath = os.path.join("storage", filename)
            logging.info(f"Starting upload for file : {filename}")
            active_uploads[fd] = open(filepath, "rb")


def broadcast_message(message, sender_socket, all_socket, server_socket):
    for sock in all_socket:
        if sock is not server_socket and sock is not sender_socket:
            try:
                send_msg(sock, f"[BROADCAST] {message}")
            except:
                pass

def filter_filename(filename):
    basename = os.path.basename(filename)
    if basename in [".", "..", ""]:
        return None
    return basename

def handle_download_chunk(fd, sock, poll_obj):
    f = active_downloads[fd]
    chunk = f.read(8192)
    if chunk:
        sock.sendall(struct.pack(">I", len(chunk)) + chunk)
    else:
        sock.sendall(struct.pack(">I", 0))
        f.close()
        del active_downloads[fd]
        poll_obj.modify(fd, select.POLLIN)
        logging.info("Download finished.")

def handle_upload_chunk(fd, sock, poll_obj):
    f = active_uploads[fd]
    try:
        header = sock.recv(4)
        if not header:
            raise ConnectionError
        length = struct.unpack(">I", header)[0]

        if length == 0:
            f.close()
            del active_uploads[fd]
            send_msg(sock, "Upload Complete.")
            logging.info("Upload finished.")
        else:
            buf = b""
            while len(buf) < length:
                chunk = sock.recv(length - len(buf))
                buf += chunk
            f.write(buf)
    except:
        f.close()
        if fd in active_uploads:
            del active_uploads[fd]

def cleanup_socket(fd, fd_map, poll_obj, server):
    sock = fd_map.get(fd)
    if not sock:
        return

    try:
        addr = sock.getpeername()
    except:
        addr = "Unknown"

    logging.info(f"Client {addr} has left.")

    if fd in active_downloads: active_downloads[fd].close(); del active_downloads[fd]
    if fd in active_uploads: active_uploads[fd].close(); del active_uploads[fd]
    poll_obj.unregister(fd)
    fd_map[fd].close()
    del fd_map[fd]

    broadcast_message(f"Client {addr} has left.", None, fd_map.values(), server)

def start_poll_server(host='127.0.0.1', port=5000):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(5)
    server.setblocking(False)

    poll_obj = select.poll()
    poll_obj.register(server.fileno(), select.POLLIN)

    fd_map = {server.fileno(): server}
    logging.info(f"Server is listening at address {host} on port {port}")

    try:
        while True:
            for fd, event in poll_obj.poll():
                sock = fd_map[fd]

                if sock is server:
                    conn, addr = server.accept()
                    conn.setblocking(False)
                    fd_map[conn.fileno()] = conn
                    poll_obj.register(conn.fileno(), select.POLLIN)
                    logging.info(f"Connected: {addr}")
                    broadcast_message(f"User {addr} joined.", conn, fd_map.values(), server)

                    continue

                elif event & select.POLLIN:
                    if fd in active_uploads:
                        handle_upload_chunk(fd, sock, poll_obj)
                    else:
                        try:
                            cmd_data = recv_msg(sock)
                            if cmd_data:
                                handle_command(cmd_data, sock, poll_obj)
                            else:
                                raise ConnectionError
                        except:
                            cleanup_socket(fd, fd_map, poll_obj, server)

                elif event & select.POLLOUT:
                    if fd in active_downloads:
                        handle_download_chunk(fd, sock, poll_obj)

                if event & (select.POLLHUP | select.POLLERR):
                    cleanup_socket(fd, fd_map, poll_obj, server)

    except Exception as ee:
        logging.info(f"ERROR: {str(ee)}")
    except KeyboardInterrupt:
        server.close()
        logging.info("closing")

if __name__ == '__main__':
    start_poll_server()
