#!/usr/bin/env python3
"""ipv6_bridge.py — makes AeroNode's IPv4-only web page (8000) and live MQTT websocket (9001) answer over IPv6 too,
so http://bb1.local:8000 works on networks where the name only resolves to BB1's IPv6 address.

Peter 2026-11-23: "make bb1.local work at the office too". Measured that day: on the office LAN the Mac receives only
BB1's mDNS AAAA record (fe80::…), never the A record avahi also registers, and aeronode-web (uvicorn, 0.0.0.0:8000)
and mosquitto (0.0.0.0:9001) listen on IPv4 only -> connection refused by name; by IP it works.

How: for each port, an IPV6_V6ONLY listening socket on [::]:port — it coexists with the IPv4 0.0.0.0:port listener of
the real service, so nothing of AeroNode's (ALFA's code and config) is changed — and every connection is piped to
127.0.0.1:port byte for byte (HTTP and websockets alike). Side effect: the real service sees IPv6 clients as
127.0.0.1. If a port's IPv6 bind fails (e.g. the service itself starts listening on IPv6), that port is skipped and
logged; the others keep running.
"""
import argparse
import asyncio
import signal
import socket
import sys


async def pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except (ConnectionError, OSError):
        pass
    finally:
        try:
            writer.close()
        except Exception:  # noqa: BLE001
            pass


def handler(port: int):
    async def handle(c_reader: asyncio.StreamReader, c_writer: asyncio.StreamWriter) -> None:
        try:
            u_reader, u_writer = await asyncio.wait_for(asyncio.open_connection("127.0.0.1", port), 5)
        except (OSError, asyncio.TimeoutError):
            c_writer.close()
            return
        for w in (c_writer, u_writer):
            s = w.get_extra_info("socket")
            if s is not None:
                s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)   # live telemetry: no Nagle delay
        await asyncio.gather(pipe(c_reader, u_writer), pipe(u_reader, c_writer))
    return handle


def v6_socket(port: int) -> socket.socket:
    s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)     # leave IPv4 to the real service
    s.bind(("::", port))
    s.listen(256)
    s.setblocking(False)
    return s


async def main(ports):
    servers = []
    for port in ports:
        try:
            servers.append(await asyncio.start_server(handler(port), sock=v6_socket(port)))
            print(f"ipv6-bridge: [::]:{port} -> 127.0.0.1:{port}", flush=True)
        except OSError as e:
            print(f"ipv6-bridge: port {port} skipped ({e})", flush=True)
    if not servers:
        sys.exit("ipv6-bridge: no port could be bridged")
    await asyncio.gather(*(s.serve_forever() for s in servers))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("ports", nargs="*", type=int, default=[8000, 9001],
                    help="ports to bridge (default 8000 web, 9001 MQTT websocket)")
    a = ap.parse_args()
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    asyncio.run(main(a.ports))
