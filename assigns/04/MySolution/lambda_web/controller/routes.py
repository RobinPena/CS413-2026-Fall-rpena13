"""Controller: HTTP routes."""
from flask import Blueprint

bp = Blueprint("controller", __name__)


@bp.get("/")
def index():
    return ("LAMBDA web front-end: scaffold running.\n", 200,
            {"Content-Type": "text/plain; charset=utf-8"})
