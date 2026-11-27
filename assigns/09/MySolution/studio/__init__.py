"""The studio host: serves the LAMBDA-studio page and forwards its LAMBDA3 calls.

It is a separate process from the database service and imports nothing from
it. The page talks to the database service directly (REST, with CORS), and
to LAMBDA3 through this host's POST /lambda/rpc, because the Assign07
service sends no CORS headers.
"""
