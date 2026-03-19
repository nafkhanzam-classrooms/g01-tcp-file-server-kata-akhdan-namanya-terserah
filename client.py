import socket
import struct
import os

def send_msg(sock, data_str):
    data = data_str.encode()
    header = struct.pack(">I", len(data))
    sock.sendall(header + data)

def recv_msg(sock):
    header = sock.recv(4)
    if not header: 
        return None
    length = struct.unpack(">I", header)[0]
    buf = b""
    while len(buf) < length:
        chunk = sock.recv(length - len(buf))
        if not chunk: break
        buf += chunk
    return buf.decode()

def send_file_chunked(sock, filepath):
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk: break
            sock.sendall(struct.pack(">I", len(chunk)) + chunk)
    sock.sendall(struct.pack(">I", 0))
  
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
                buf += chunk
            f.write(buf)
          
def start_client(host='localhost', port=5000):
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if not os.path.isdir("client_storage"):
        os.mkdir("client_storage")
    try:
        client.connect((host, port))
        print(f"Server: {recv_msg(client)}")
        print("--- File Transfer---\n")
        print("Commands: /list, /upload <filepath>, /download <filename>, /exit\n")
        while True:
            cmd = input("client> ")
            if not cmd.strip(): 
                continue
            if cmd in ["/quit", "/exit"]:
                print("Disconnecting...")
                break
            parts = cmd.split()
            command = parts[0]
            if command == "/list":
                send_msg(client, cmd)
                response = recv_msg(client)
                print(f"\nFiles on server:\n{response}\n")
            elif command == "/download" and len(parts) > 1:
                filename = parts[1]
                send_msg(client, cmd)
                response = recv_msg(client)
                if response == "OK":
                    save_path = os.path.join("client_storage", os.path.basename(filename))
                    print(f"Downloading {filename}...")
                    recv_file_chunked(client, save_path)
                    print(f"Success! Saved to {save_path}\n")
                else:
                    print(f"Server: {response}\n")
            elif command == "/upload" and len(parts) > 1:
                filepath = parts[1]
                if not os.path.isfile(filepath):
                    print(f"Local file not found: {filepath}\n")
                    continue
                send_msg(client, cmd)
                print(f"Uploading {filepath}...")
                send_file_chunked(client, filepath)
                response = recv_msg(client)
                print(f"Server: {response}\n")
            else:
                print("Invalid command syntax.")
                print("Usage: /list | /upload <path> | /download <name>\n")
    except ConnectionRefusedError:
        print(f"Could not connect to server at {host}:{port}. Is it running?")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        client.close()
if __name__ == "__main__":
    start_client()
