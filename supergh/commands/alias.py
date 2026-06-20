"""sgh alias — create command shortcuts."""

import click
from rich.console import Console
from rich.table import Table

from supergh.config import get_config

console = Console()


@click.group("alias")
@click.pass_context
def alias(ctx):
    """Create command shortcuts."""


@alias.command("set")
@click.argument("name")
@click.argument("expansion")
@click.pass_context
def alias_set(ctx, name, expansion):
    """Create a shortcut for a command.

    \b
    Examples:
      sgh alias set co "pr checkout"
      sgh alias set prl "pr list --state open"
      sgh alias set myrepos "repo list --limit 10"
    """
    cfg = get_config()
    cfg.set(f"aliases.{name}", expansion)
    console.print(f"[green]Added alias '{name}' → 'sgh {expansion}'[/green]")


@alias.command("list")
@click.pass_context
def alias_list(ctx):
    """List all aliases."""
    cfg = get_config()
    aliases = cfg.get("aliases", {})
    if not aliases:
        console.print("[dim]No aliases configured. Use 'sgh alias set <name> <command>' to create one.[/dim]")
        return

    table = Table(title="Aliases")
    table.add_column("Alias", style="cyan")
    table.add_column("Expands to", style="dim")
    for name, expansion in aliases.items():
        table.add_row(name, f"sgh {expansion}")
    console.print(table)


@alias.command("delete")
@click.argument("name")
@click.pass_context
def alias_delete(ctx, name):
    """Delete an alias."""
    cfg = get_config()
    aliases = cfg.get("aliases", {})
    if name not in aliases:
        console.print(f"[red]Alias '{name}' not found.[/red]")
        raise SystemExit(1)
    del aliases[name]
    cfg.set("aliases", aliases)
    console.print(f"[green]Deleted alias '{name}'[/green]")
