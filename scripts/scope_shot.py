"""Grab a PNG screenshot from the office Rigol MHO984 over raw SCPI (port 5555).
Usage: python3 scripts/scope_shot.py <scope-ip> <out.png>   (office IP 2026-11-24: 192.168.10.229)"""
import socket, sys
host, out = sys.argv[1], sys.argv[2]
s = socket.create_connection((host, 5555), timeout=10)
s.sendall(b":DISP:DATA? PNG\n")
buf = b""
while len(buf) < 2:
    buf += s.recv(4096)
assert buf[0:1] == b"#", buf[:20]
nd = int(buf[1:2])
while len(buf) < 2 + nd:
    buf += s.recv(4096)
n = int(buf[2:2 + nd])
start = 2 + nd
while len(buf) < start + n:
    buf += s.recv(65536)
open(out, "wb").write(buf[start:start + n])
print(n, "bytes ->", out)
