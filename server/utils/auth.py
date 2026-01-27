"""
Authentication Utilities
========================

HTTP Basic Authentication utilities for the Autocoder server.
Provides both HTTP middleware and WebSocket authentication support.

Configuration:
    Set both BASIC_AUTH_USERNAME and BASIC_AUTH_PASSWORD environment
    variables to enable authentication. If either is not set, auth is disabled.

Example:
    # In .env file:
    BASIC_AUTH_USERNAME=admin
    BASIC_AUTH_PASSWORD=your-secure-password

For WebSocket connections:
    - Clients that support custom headers can use Authorization header
    - Browser WebSockets can pass token via query param: ?token=base64(user:pass)
"""

import base64
import os
import secrets
from typing import Optional

from fastapi import WebSocket


def is_basic_auth_enabled() -> bool:
    """Check if Basic Auth is enabled via environment variables."""
    username = os.environ.get("BASIC_AUTH_USERNAME", "").strip()
    password = os.environ.get("BASIC_AUTH_PASSWORD", "").strip()
    return bool(username and password)


def get_basic_auth_credentials() -> tuple[str, str]:
    """Get configured Basic Auth credentials."""
    username = os.environ.get("BASIC_AUTH_USERNAME", "").strip()
    password = os.environ.get("BASIC_AUTH_PASSWORD", "").strip()
    return username, password


def verify_basic_auth(username: str, password: str) -> bool:
    """
    Verify Basic Auth credentials using constant-time comparison.

    Args:
        username: Provided username
        password: Provided password

    Returns:
        True if credentials match configured values, False otherwise.
    """
    expected_user, expected_pass = get_basic_auth_credentials()
    if not expected_user or not expected_pass:
        return True  # Auth not configured, allow all

    user_valid = secrets.compare_digest(username, expected_user)
    pass_valid = secrets.compare_digest(password, expected_pass)
    return user_valid and pass_valid


def check_websocket_auth(websocket: WebSocket) -> bool:
    """
    Check WebSocket authentication using Basic Auth credentials.

    For WebSockets, auth can be passed via:
    1. Authorization header (for clients that support it)
    2. Query parameter ?token=base64(user:pass) (for browser WebSockets)

    Args:
        websocket: The WebSocket connection to check

    Returns:
        True if auth is valid or not required, False otherwise.
    """
    # If Basic Auth not configured, allow all connections
    if not is_basic_auth_enabled():
        return True

    # Try Authorization header first
    auth_header = websocket.headers.get("authorization", "")
    if auth_header.startswith("Basic "):
        try:
            encoded = auth_header[6:]
            decoded = base64.b64decode(encoded).decode("utf-8")
            user, passwd = decoded.split(":", 1)
            if verify_basic_auth(user, passwd):
                return True
        except (ValueError, UnicodeDecodeError):
            pass

    # Try query parameter (for browser WebSockets)
    # URL would be: ws://host/ws/projects/name?token=base64(user:pass)
    token = websocket.query_params.get("token", "")
    if token:
        try:
            decoded = base64.b64decode(token).decode("utf-8")
            user, passwd = decoded.split(":", 1)
            if verify_basic_auth(user, passwd):
                return True
        except (ValueError, UnicodeDecodeError):
            pass

    return False


async def reject_unauthenticated_websocket(websocket: WebSocket) -> bool:
    """
    Check WebSocket auth and close connection if unauthorized.

    Args:
        websocket: The WebSocket connection

    Returns:
        True if connection should proceed, False if it was closed due to auth failure.
    """
    if not check_websocket_auth(websocket):
        await websocket.close(code=4001, reason="Authentication required")
        return False
    return True
