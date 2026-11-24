"""In-memory database service for LAMBDA-studio (contract: API.md).

The service stores programs and test collections in process memory only. It
never parses or runs LAMBDA source; the studio does that through the
separate Assign07 LAMBDA3 service.
"""
