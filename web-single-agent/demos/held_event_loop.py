"""Measure what a blocking turn does to every other request.

    uv run web-single-agent/demos/held_event_loop.py

This needs no API key. A three second sleep stands in for a turn, because the
lesson is about the event loop and not about the model.
"""

from __future__ import annotations

import asyncio
import socket
import threading
import time
import urllib.request

import uvicorn
from fastapi import FastAPI

TURN_SECONDS = 3.0
PING_INTERVAL_SECONDS = 0.2
BASELINE_SECONDS = 0.6

app = FastAPI()


@app.get("/api/ping")
def get_ping() -> dict:
    """Answer immediately."""
    return {"ok": True}


@app.get("/on-event-loop")
async def get_on_event_loop() -> dict:
    """Call a blocking function from an async route, holding the event loop."""
    time.sleep(TURN_SECONDS)
    return {"ok": True}


@app.get("/on-worker-thread")
async def get_on_worker_thread() -> dict:
    """Send the same blocking function to a worker thread."""
    await asyncio.to_thread(time.sleep, TURN_SECONDS)
    return {"ok": True}


def free_port() -> int:
    """Ask the operating system for an unused port."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def get(url: str) -> None:
    """Send one GET request and discard the body."""
    with urllib.request.urlopen(url, timeout=60.0) as response:
        response.read()


def ping_until(stop: threading.Event, base: str, times: list[float]) -> None:
    """Time GET /api/ping repeatedly until told to stop."""
    while not stop.is_set():
        start = time.perf_counter()
        get(f"{base}/api/ping")
        times.append((time.perf_counter() - start) * 1000)
        stop.wait(PING_INTERVAL_SECONDS)


def measure(base: str, path: str) -> tuple[list[float], float]:
    """Ping throughout one slow request and report ping times and its duration."""
    stop = threading.Event()
    times: list[float] = []
    pinger = threading.Thread(target=ping_until, args=(stop, base, times))
    pinger.start()
    time.sleep(BASELINE_SECONDS)

    start = time.perf_counter()
    get(f"{base}{path}")
    turn_seconds = time.perf_counter() - start

    time.sleep(BASELINE_SECONDS)
    stop.set()
    pinger.join()
    return times, turn_seconds


def report(label: str, route: str, times: list[float], turn_seconds: float) -> None:
    """Print every ping time and the slowest one."""
    print(f"\n{label}")
    print(f"  route  GET {route}")
    for milliseconds in times:
        marker = "   <- waited for the whole turn" if milliseconds > 500 else ""
        print(f"  ping   {milliseconds:8.1f} ms{marker}")
    print(f"  slowest ping {max(times):.1f} ms, turn took {turn_seconds:.1f} s")


def main() -> None:
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)

    print(f"Timing GET /api/ping while a {TURN_SECONDS:.1f} s turn runs.")
    try:
        times, turn_seconds = measure(base, "/on-event-loop")
        report("The turn runs on the event-loop thread.", "/on-event-loop", times, turn_seconds)

        times, turn_seconds = measure(base, "/on-worker-thread")
        report("The turn runs on a worker thread.", "/on-worker-thread", times, turn_seconds)
    finally:
        server.should_exit = True
        thread.join()

    print("\nBoth turns took the same time. Only one of them stopped serving requests.")
    print("\nThe real server has the same two routes behind one environment variable:")
    print("  uv run --env-file .env web-single-agent/server.py")
    print("  BLOCK_EVENT_LOOP=1 uv run --env-file .env web-single-agent/server.py")
    print("Send a message in the browser, then load http://127.0.0.1:8765/api/ping.")


if __name__ == "__main__":
    main()
