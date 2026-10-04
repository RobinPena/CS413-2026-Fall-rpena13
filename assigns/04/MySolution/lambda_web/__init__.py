"""LAMBDA web front-end (Assign04)."""
from flask import Flask


def create_app() -> Flask:
    """Build the Flask app and register the controller routes."""
    app = Flask(__name__,
                template_folder="view/templates",
                static_folder="view/static")

    from lambda_web.controller.routes import bp
    app.register_blueprint(bp)
    return app
