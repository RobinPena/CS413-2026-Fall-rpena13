"""Start the local development server.

    python -m MySolution [--host 127.0.0.1] [--port 8000]
                         [--deadline 2.0] [--max-source-bytes 65536]

Run from assigns/07/. The endpoint is then http://HOST:PORT/rpc.
"""
from __future__ import annotations

import argparse
import logging
import math

from .app import create_app
from .service import DEFAULT_MAX_SOURCE_BYTES
from .worker import DEFAULT_DEADLINE_SECONDS


def positive(convert):
    """An argparse type: convert the text, then require a finite value above zero."""
    def parse(text: str):
        value = convert(text)
        if not (math.isfinite(value) and value > 0):
            raise argparse.ArgumentTypeError(f"must be a finite number greater than 0: {text}")
        return value
    parse.__name__ = convert.__name__  # argparse names the type in its errors
    return parse


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m MySolution",
        description="Serve the LAMBDA3 JSON-RPC service at POST /rpc.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="interface to bind (default: %(default)s)")
    parser.add_argument("--port", type=int, default=8000, help="TCP port (default: %(default)s)")
    parser.add_argument("--deadline", type=positive(float), default=DEFAULT_DEADLINE_SECONDS,
                        help="seconds allowed for each lambda.* call (default: %(default)s)")
    parser.add_argument("--max-source-bytes", type=positive(int), default=DEFAULT_MAX_SOURCE_BYTES,
                        help="largest source param, in UTF-8 bytes (default: %(default)s)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = create_app({"DEADLINE_SECONDS": args.deadline, "MAX_SOURCE_BYTES": args.max_source_bytes})
    app.run(host=args.host, port=args.port, threaded=True, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
