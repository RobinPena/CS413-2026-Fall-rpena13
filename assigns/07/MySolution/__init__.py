"""A JSON-RPC 2.0 service for the LAMBDA3 language tools (contract: RPC.md)."""
from .app import create_app

__all__ = ["create_app"]
