"""sgh gui — start/stop the web dashboard."""

import os
import signal
import sys
from pathlib import Path

import click
from rich.console import Console

console = Console()

PID_FILE = Path.home() / ".supergh" / "gui.pid"


def _read_pid() -> int | None:
    """Read stored PID from file."""
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            # Check if process is alive
            os.kill(pid, 0)
            return pid
        except (ValueError, ProcessLookupError, PermissionError):
            PID_FILE.unlink(missing_ok=True)
    return None


def _write_pid(pid: int, port: int):
    """Store PID and port."""
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(f"{pid}\n{port}")


def _read_pid_and_port() -> tuple[int | None, int | None]:
    """Read PID and port from file."""
    if PID_FILE.exists():
        try:
            lines = PID_FILE.read_text().strip().split("\n")
            pid = int(lines[0])
            port = int(lines[1]) if len(lines) > 1 else 8787
            os.kill(pid, 0)
            return pid, port
        except (ValueError, ProcessLookupError, PermissionError, IndexError):
            PID_FILE.unlink(missing_ok=True)
    return None, None


@click.group("gui")
def gui():
    """Manage the web dashboard server.

    \b
    Examples:
      sgh gui start                  # attached mode (foreground)
      sgh gui start --detached       # background mode
      sgh gui start -p 9090          # custom port
      sgh gui stop                   # stop background server
      sgh gui status                 # check if running
    """


@gui.command("start")
@click.option("--port", "-p", default=8787, help="Port number.")
@click.option("--detached", "-d", is_flag=True, help="Run in background (detached mode).")
@click.option("--no-browser", is_flag=True, help="Don't open browser automatically.")
def gui_start(port, detached, no_browser):
    """Start the web dashboard.

    \b
    Modes:
      Attached (default): Runs in foreground. Ctrl+C to stop.
      Detached (-d):      Runs in background. Use 'sgh gui stop' to stop.
    """
    # Check if already running
    existing_pid, existing_port = _read_pid_and_port()
    if existing_pid:
        console.print(f"[yellow]Dashboard already running.[/yellow]")
        console.print(f"  PID:  {existing_pid}")
        console.print(f"  Port: {existing_port}")
        console.print(f"  URL:  http://127.0.0.1:{existing_port}")
        console.print(f"\n  Use 'sgh gui stop' to stop it first.")
        return

    if detached:
        _start_detached(port, no_browser)
    else:
        _start_attached(port, no_browser)


def _start_attached(port: int, no_browser: bool):
    """Run server in foreground."""
    from supergh.ui.web import start_server

    pid = os.getpid()
    _write_pid(pid, port)

    console.print(f"[green]Dashboard starting (attached mode)[/green]")
    console.print(f"  PID:  {pid}")
    console.print(f"  Port: {port}")
    console.print(f"  URL:  http://127.0.0.1:{port}")
    console.print(f"  Mode: attached (Ctrl+C to stop)\n")

    try:
        start_server(port=port, open_browser=not no_browser)
    finally:
        PID_FILE.unlink(missing_ok=True)


def _start_detached(port: int, no_browser: bool):
    """Fork and run server in background."""
    import subprocess
    import webbrowser
    import time

    # Launch as a subprocess
    cmd = [
        sys.executable, "-c",
        f"from supergh.ui.web import app; import uvicorn; uvicorn.run(app, host='127.0.0.1', port={port}, log_level='warning')"
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    # Wait a moment to confirm it started
    time.sleep(1)
    if proc.poll() is not None:
        console.print(f"[red]Failed to start dashboard. Port {port} may be in use.[/red]")
        return

    _write_pid(proc.pid, port)

    console.print(f"[green]Dashboard started (detached mode)[/green]")
    console.print(f"  PID:  {proc.pid}")
    console.print(f"  Port: {port}")
    console.print(f"  URL:  http://127.0.0.1:{port}")
    console.print(f"  Mode: detached (use 'sgh gui stop' to stop)")

    if not no_browser:
        time.sleep(0.5)
        webbrowser.open(f"http://127.0.0.1:{port}")


@gui.command("stop")
def gui_stop():
    """Stop the background dashboard server."""
    pid, port = _read_pid_and_port()
    if not pid:
        console.print("[yellow]No dashboard server running.[/yellow]")
        return

    try:
        os.kill(pid, signal.SIGTERM)
        console.print(f"[green]Dashboard stopped.[/green]")
        console.print(f"  PID:  {pid}")
        console.print(f"  Port: {port}")
    except ProcessLookupError:
        console.print("[yellow]Server process not found (already stopped).[/yellow]")
    except PermissionError:
        console.print(f"[red]Permission denied. Try: kill {pid}[/red]")
    finally:
        PID_FILE.unlink(missing_ok=True)


@gui.command("status")
def gui_status():
    """Check if the dashboard is running."""
    pid, port = _read_pid_and_port()
    if pid:
        console.print(f"[green]Dashboard is running.[/green]")
        console.print(f"  PID:  {pid}")
        console.print(f"  Port: {port}")
        console.print(f"  URL:  http://127.0.0.1:{port}")
    else:
        console.print("[dim]Dashboard is not running.[/dim]")
        console.print("  Start with: sgh gui start")


@gui.command("restart")
@click.option("--port", "-p", default=None, type=int, help="Port number (uses previous port if not specified).")
@click.option("--detached", "-d", is_flag=True, help="Run in background.")
@click.option("--no-browser", is_flag=True, help="Don't open browser.")
@click.pass_context
def gui_restart(ctx, port, detached, no_browser):
    """Restart the dashboard server."""
    pid, old_port = _read_pid_and_port()
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
        PID_FILE.unlink(missing_ok=True)
        import time
        time.sleep(1)

    use_port = port or old_port or 8787
    ctx.invoke(gui_start, port=use_port, detached=detached, no_browser=no_browser)
