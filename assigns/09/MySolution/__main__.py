"""Start the database service.

    python -m MySolution [--host 127.0.0.1] [--port 8009] [--studio-origin ORIGIN ...]

Run from assigns/09/. The API is then at http://HOST:PORT/api/v1. Every
record is kept in this process's memory and is lost when the process stops.
"""
from __future__ import annotations

import argparse
import logging
import re

from .app import API, DEFAULT_STUDIO_ORIGINS, create_app

_ORIGIN = re.compile(r"https?://[^/\s]+")


def origin(text: str) -> str:
    """An argparse type: a browser origin such as http://127.0.0.1:8010 (no path)."""
    if not _ORIGIN.fullmatch(text):
        raise argparse.ArgumentTypeError(
            f"must be scheme://host[:port] with no path or trailing slash: {text}")
    return text


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m MySolution",
        description=f"Serve the LAMBDA-studio in-memory database at {API}.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="interface to bind (default: %(default)s)")
    parser.add_argument("--port", type=int, default=8009, help="TCP port (default: %(default)s)")
    parser.add_argument("--studio-origin", type=origin, action="append", dest="studio_origins",
                        metavar="ORIGIN",
                        help="origin of the studio page that CORS allows; repeat for several "
                             f"(default: {' and '.join(DEFAULT_STUDIO_ORIGINS)})")
    args = parser.parse_args(argv)
    studio_origins = tuple(args.studio_origins or DEFAULT_STUDIO_ORIGINS)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    log = logging.getLogger("MySolution")
    log.info("API at http://%s:%d%s; CORS allowed for %s", args.host, args.port, API,
             ", ".join(studio_origins))
    log.warning("Records are kept in process memory only and are lost when this process stops.")

    app = create_app(studio_origins=studio_origins)
    app.run(host=args.host, port=args.port, threaded=True, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
