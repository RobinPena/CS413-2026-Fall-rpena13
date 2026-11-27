"""Start the studio host.

    python -m MySolution.studio [--host 127.0.0.1] [--port 8010]
                                [--database-url http://127.0.0.1:8009/api/v1]
                                [--lambda-url http://127.0.0.1:8000/rpc]
                                [--lambda-timeout 10]

Run from assigns/09/, then open http://HOST:PORT/ in a browser. The database
service (python -m MySolution) and the Assign07 LAMBDA3 service must be
running at the given URLs. If you change --port, start the database service
with a matching --studio-origin so that the page may call it.
"""
from __future__ import annotations

import argparse
import logging
import math

from .host import create_studio_app


def positive_seconds(text: str) -> float:
    value = float(text)
    if not (math.isfinite(value) and value > 0):
        raise argparse.ArgumentTypeError(f"must be a number of seconds greater than 0: {text}")
    return value


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m MySolution.studio",
                                     description="Serve the LAMBDA-studio page and forward its LAMBDA3 calls.")
    parser.add_argument("--host", default="127.0.0.1", help="interface to bind (default: %(default)s)")
    parser.add_argument("--port", type=int, default=8010, help="TCP port (default: %(default)s)")
    parser.add_argument("--database-url", default="http://127.0.0.1:8009/api/v1",
                        help="base URL of the database API, as the browser reaches it (default: %(default)s)")
    parser.add_argument("--lambda-url", default="http://127.0.0.1:8000/rpc",
                        help="the Assign07 LAMBDA3 JSON-RPC endpoint (default: %(default)s)")
    parser.add_argument("--lambda-timeout", type=positive_seconds, default=10.0,
                        help="seconds to wait for each LAMBDA3 answer (default: %(default)s)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("MySolution.studio").info(
        "Studio at http://%s:%d/ using the database at %s and LAMBDA3 at %s",
        args.host, args.port, args.database_url, args.lambda_url)
    app = create_studio_app(args.lambda_url, args.database_url, timeout=args.lambda_timeout)
    app.run(host=args.host, port=args.port, threaded=True, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
