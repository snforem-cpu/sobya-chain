#!/usr/bin/env python3
"""Expose a local TCP port through an authenticated Cloudflare WebSocket relay."""

import argparse
import asyncio
import os
from urllib.parse import urlencode

import websockets


async def tunnel(reader, writer, args):
    token = os.environ.get("SOBYA_RELAY_TOKEN", "")
    if not token:
        raise RuntimeError("SOBYA_RELAY_TOKEN environment variable is required")

    query = urlencode({"room": args.room, "role": args.role})
    base = args.url.rstrip("/")
    if base.startswith("https://"):
        base = "wss://" + base[len("https://"):]
    elif base.startswith("http://"):
        base = "ws://" + base[len("http://"):]
    uri = f"{base}/bridge?{query}"

    try:
        async with websockets.connect(
            uri,
            additional_headers={"Authorization": f"Bearer {token}"},
            max_size=None,
            ping_interval=20,
            ping_timeout=20,
            open_timeout=30,
            close_timeout=5,
        ) as ws:
            ready = await asyncio.wait_for(ws.recv(), timeout=120)
            if ready != "READY":
                raise RuntimeError(f"Relay did not become ready: {ready!r}")

            async def tcp_to_relay():
                while True:
                    chunk = await reader.read(65536)
                    if not chunk:
                        break
                    await ws.send(chunk)

            async def relay_to_tcp():
                async for message in ws:
                    if not isinstance(message, bytes):
                        raise RuntimeError(f"Unexpected relay control message: {message!r}")
                    writer.write(message)
                    await writer.drain()

            tasks = [
                asyncio.create_task(tcp_to_relay()),
                asyncio.create_task(relay_to_tcp()),
            ]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            for task in done:
                exception = task.exception()
                if exception:
                    raise exception
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Cloudflare Worker base URL, e.g. https://sobya-relay.example.workers.dev")
    parser.add_argument("--room", required=True, help="Private relay room identifier")
    parser.add_argument("--role", required=True, choices=("a", "b"))
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--listen-port", type=int, default=27656)
    args = parser.parse_args()

    server = await asyncio.start_server(
        lambda r, w: tunnel(r, w, args),
        args.listen_host,
        args.listen_port,
    )
    sockets = ", ".join(str(sock.getsockname()) for sock in (server.sockets or []))
    print(f"SOBYA Cloudflare bridge listening on {sockets}; role={args.role}; room={args.room}", flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
