#!/usr/bin/env python3
import socket
import sounddevice as sd
import struct

# Audio settings
SAMPLERATE = 48000
CHANNELS = 2
BLOCKSIZE = 1024
DTYPE = 'int16'

# Network settings
DEST_IP = "192.168.1.90"
DEST_PORT = 50007

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((DEST_IP, DEST_PORT))
    print(f"Connected to receiver at {DEST_IP}:{DEST_PORT}")

    def callback(indata, frames, time, status):
        if status:
            print("Status:", status)
        header = struct.pack("<I", frames)
        sock.sendall(header + indata.tobytes())

    # IMPORTANT: Select VB-Audio "CABLE Output" as input device
    device = None
    for i, dev in enumerate(sd.query_devices()):
        if "CABLE Output" in dev["name"]:
            device = i
            break

    if device is None:
        raise RuntimeError("VB-Audio Cable Output not found!")

    with sd.InputStream(samplerate=SAMPLERATE, channels=CHANNELS,
                        dtype=DTYPE, blocksize=BLOCKSIZE,
                        callback=callback, device=device):
        print("Streaming VB-Audio Cable...")
        try:
            while True:
                sd.sleep(1000)
        except KeyboardInterrupt:
            print("Stopping sender.")

    sock.close()

if __name__ == "__main__":
    main()
