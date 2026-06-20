"""Global error handler — translates exceptions into user-friendly messages."""

import sys

from rich.console import Console

console = Console(stderr=True)


def handle_error(e: Exception, debug: bool = False):
    """Convert any exception into a clean, actionable CLI message."""
    # Show full traceback only in debug mode
    if debug:
        console.print_exception()
        return

    error_type = type(e).__name__
    msg = str(e)

    # --- HTTP errors ---
    if error_type == "HTTPError":
        resp = getattr(e, "response", None)
        if resp is not None:
            status = resp.status_code
            url = resp.url or ""
            body = ""
            try:
                body = resp.json().get("message", "")
            except Exception:
                pass

            if status == 401:
                _print_error("Authentication failed. Token may be expired.", hint="Run: sgh auth login")
            elif status == 403:
                _print_error(f"Access denied: {body or 'insufficient permissions'}.", hint="Check your token scopes or ask org admin for access.")
            elif status == 404:
                # Extract useful path from URL
                path = url.replace("https://api.github.com", "")
                _print_error(f"Not found: {path}", hint=body or "Check the resource name and try again.")
            elif status == 422:
                _print_error(f"Validation error: {body or msg}")
            elif status == 409:
                _print_error(f"Conflict: {body or 'resource already exists'}")
            elif status >= 500:
                _print_error(f"GitHub server error ({status}). Try again in a moment.")
            else:
                _print_error(f"HTTP {status}: {body or msg}")
        else:
            _print_error(msg)

    # --- URL/connection errors ---
    elif error_type == "MissingSchema":
        _print_error("Invalid API path. Prefix with / for relative paths.", hint="Example: sgh api /repos/owner/name")
    elif error_type == "ConnectionError":
        _print_error("Cannot connect to GitHub. Check your internet connection.")
    elif error_type == "Timeout":
        _print_error("Request timed out. GitHub may be slow — try again.")

    # --- Auth errors ---
    elif error_type == "RuntimeError" and "Not authenticated" in msg:
        _print_error("Not authenticated.", hint="Run: sgh auth login")
    elif error_type == "RuntimeError" and "refresh failed" in msg:
        _print_error("Token refresh failed.", hint="Run: sgh auth login")

    # --- File errors ---
    elif error_type == "FileNotFoundError":
        _print_error(f"File not found: {msg}")
    elif error_type == "PermissionError":
        _print_error(f"Permission denied: {msg}")

    # --- JSON errors ---
    elif error_type == "JSONDecodeError":
        _print_error("Invalid JSON input.", hint="Check your --body argument.")

    # --- Click errors (UsageError etc.) ---
    elif "UsageError" in error_type:
        _print_error(msg)

    # --- Catch-all ---
    else:
        _print_error(msg, hint="Use --debug for full details.")


def _print_error(message: str, hint: str = ""):
    """Print a formatted error message."""
    console.print(f"[red]Error:[/red] {message}")
    if hint:
        console.print(f"[dim]  Hint: {hint}[/dim]")
