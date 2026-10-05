"""LAMBDA web front-end (Assign04)."""
from flask import Flask

from lambda_web.backend.contract import LanguageBackend
from lambda_web.model import MAX_SOURCE_BYTES, Session

# Room for multipart headers around a maximum-size upload; the model
# still enforces the exact source limit.
MAX_REQUEST_BYTES = MAX_SOURCE_BYTES + 16 * 1024


def create_app(backend: LanguageBackend | None = None,
               session: Session | None = None) -> Flask:
    """Build the app. This is the only place that chooses the concrete
    language backend; tests pass a substitute."""
    if backend is None:
        from lambda_web.backend.lambda_backend import LambdaBackend
        backend = LambdaBackend()
    app = Flask(__name__,
                template_folder="view/templates",
                static_folder="view/static")
    app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BYTES
    app.extensions["lambda_web"] = {
        "backend": backend,
        "session": session if session is not None else Session(),
    }

    from lambda_web.controller.routes import bp
    app.register_blueprint(bp)
    return app
