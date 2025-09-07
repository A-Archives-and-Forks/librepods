import socket
import threading
import time
import sys
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect("./att.sock")

def listen():
    while True:
        try:
            res = sock.recv(1024)
            if not res:
                break
            print(f"Response: {res.hex()}")
        except OSError:
            break


threading.Thread(target=listen, daemon=True).start()
print("Connected.")


def send_line(line: str):
    line = line.strip()
    if not line:
        return
    try:
        if " " in line:
            byts = bytes(int(b, 16) for b in line.split())
        else:
            if len(line) % 2 != 0:
                line = "0" + line
            byts = bytes.fromhex(line)
        sock.send(byts)
    except Exception as e:
        print(f"Invalid line '{line}': {e}")


# Optional file argument
file_arg = sys.argv[1] if len(sys.argv) > 1 else None

if file_arg:
    try:
        with open(file_arg, "r") as f:
            for line in f:
                send_line(line)
                time.sleep(0.2)  # 200ms delay
    except FileNotFoundError:
        print(f"File not found: {file_arg}")

# Always enter interactive mode after file
print("Type hex bytes (Ctrl-L to clear, 'quit' to exit)...")
session = PromptSession()
with patch_stdout():
    while True:
        try:
            data = session.prompt("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not data:
            continue
        if data.lower() == "quit":
            break

        send_line(data)

sock.close()
print("Connection closed.")