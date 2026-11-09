"""Start the local development server.

    python -m MySolution [--host 127.0.0.1] [--port 8000]

Run from assigns/07/. The endpoint is then http://HOST:PORT/rpc.
"""
from __future__ import annotations

import argparse
import logging

from . import create_app


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m MySolution",
        description="Serve the LAMBDA3 JSON-RPC service at POST /rpc.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="interface to bind (default: %(default)s)")
    parser.add_argument("--port", type=int, default=8000, help="TCP port (default: %(default)s)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    create_app().run(host=args.host, port=args.port, threaded=True, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
