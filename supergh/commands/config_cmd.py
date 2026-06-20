"""sgh config — manage configuration."""

import click
from rich.console import Console
from rich.tree import Tree

from supergh.config import get_config

console = Console()


@click.group("config")
def config():
    """Manage supergh configuration."""


@config.command("get")
@click.argument("key")
def config_get(key):
    """Get a config value."""
    cfg = get_config()
    value = cfg.get(key)
    if value is None:
        console.print(f"[yellow]Key '{key}' not found.[/yellow]")
        raise SystemExit(1)
    console.print(f"{key} = {value!r}")


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key, value):
    """Set a config value."""
    # Coerce booleans and ints
    if value.lower() in ("true", "false"):
        value = value.lower() == "true"
    elif value.isdigit():
        value = int(value)

    cfg = get_config()
    cfg.set(key, value)
    console.print(f"[green]Set {key} = {value!r}[/green]")


@config.command("list")
def config_list():
    """List all config values."""
    cfg = get_config()
    data = cfg.list_all()

    def build_tree(tree, d, prefix=""):
        for k, v in d.items():
            if isinstance(v, dict):
                branch = tree.add(f"[bold]{k}[/bold]")
                build_tree(branch, v, f"{prefix}{k}.")
            else:
                tree.add(f"{k} = {v!r}")

    tree = Tree("[bold cyan]~/.supergh/config.toml[/bold cyan]")
    build_tree(tree, data)
    console.print(tree)


@config.command("log-level")
@click.argument("level", required=False, type=click.Choice(["debug", "info", "warning", "error", "off"]))
def config_log_level(level):
    """Get or set the log level.

    \b
    Levels: debug, info, warning, error, off

    Examples:
      sgh config log-level          # show current level
      sgh config log-level debug    # enable debug logging
      sgh config log-level off      # disable logging
    """
    from supergh.utils.logger import get_current_level, set_log_level

    if not level:
        console.print(f"Log level: [cyan]{get_current_level()}[/cyan]")
        console.print(f"Log file:  ~/.supergh/logs/sgh.log")
        return

    set_log_level(level)
    console.print(f"[green]Log level set to: {level}[/green]")
