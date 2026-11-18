"""Start the local server.

    python -m MySolution [--host 127.0.0.1] [--port 8000] [--stream-ttl 300]

Run from assigns/08/. The client is then at http://HOST:PORT/ and the
JSON-RPC endpoint at http://HOST:PORT/rpc.
"""
from __future__ import annotations

import argparse
import logging
import math

from .app import create_app
from .streams import DEFAULT_TTL_SECONDS


def positive_float(text: str) -> float:
    value = float(text)
    if not (math.isfinite(value) and value > 0):
        raise argparse.ArgumentTypeError(f"must be a finite number greater than 0: {text}")
    return value


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m MySolution",
        description="Serve the animated N-Queens client and its JSON-RPC endpoint.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="interface to bind (default: %(default)s)")
    parser.add_argument("--port", type=int, default=8000, help="TCP port (default: %(default)s)")
    parser.add_argument("--stream-ttl", type=positive_float, default=DEFAULT_TTL_SECONDS,
                        help="seconds an unused stream stays open (default: %(default)s)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = create_app({"STREAM_TTL_SECONDS": args.stream_ttl})
    app.run(host=args.host, port=args.port, threaded=True, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
