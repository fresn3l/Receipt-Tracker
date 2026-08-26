"""Launch Finance App: embedded uvicorn + optional pywebview window."""

from __future__ import annotations

import argparse
import logging
import socket
import sys
import threading
import time
import webbrowser
from typing import Optional

import uvicorn

logger = logging.getLogger(__name__)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _run_server(host: str, port: int) -> None:
    # Ensure packages are importable when running from source
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    packages = root / "packages"
    for path in (str(root), str(packages)):
        if path not in sys.path:
            sys.path.insert(0, path)

    uvicorn.run(
        "app.server:app",
        host=host,
        port=port,
        log_level="info",
        reload=False,
    )


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Finance App — banking + receipts")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0, help="0 = pick a free port")
    parser.add_argument(
        "--browser",
        action="store_true",
        help="Open the system browser instead of a native window (dev mode)",
    )
    parser.add_argument(
        "--no-window",
        action="store_true",
        help="Run API/UI server only (no window)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    root = __import__("pathlib").Path(__file__).resolve().parent.parent
    packages = root / "packages"
    for path in (str(root), str(packages)):
        if path not in sys.path:
            sys.path.insert(0, path)

    port = args.port or _free_port()
    url = f"http://{args.host}:{port}/"
    logger.info("Starting Finance App at %s", url)

    server_thread = threading.Thread(
        target=_run_server, args=(args.host, port), daemon=True
    )
    server_thread.start()

    # Wait until server accepts connections
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            with socket.create_connection((args.host, port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.1)
    else:
        logger.error("Server failed to start")
        sys.exit(1)

    if args.no_window:
        logger.info("Server-only mode. Open %s", url)
        server_thread.join()
        return

    if args.browser:
        webbrowser.open(url)
        server_thread.join()
        return

    try:
        import webview
    except ImportError:
        logger.warning("pywebview not installed; falling back to browser")
        webbrowser.open(url)
        server_thread.join()
        return

    window = webview.create_window(
        "Finance App",
        url,
        width=1280,
        height=860,
        min_size=(900, 600),
    )
    webview.start()
    logger.info("Window closed; shutting down")


if __name__ == "__main__":
    main()
