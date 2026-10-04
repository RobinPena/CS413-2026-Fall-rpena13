"""Start the local server on the loopback interface only."""
from lambda_web import create_app

HOST = "127.0.0.1"   # loopback only; public hosting is out of scope
PORT = 5050

if __name__ == "__main__":
    create_app().run(host=HOST, port=PORT, debug=False)
