"""sgh app — manage registered GitHub Apps (the ~/.supergh/apps/ registry)."""

import click
from rich.console import Console
from rich.table import Table

from supergh.auth.app_registry import get_registry

console = Console()


@click.group("app")
def app_cmd():
    """Manage registered GitHub Apps.

    \b
    Apps are registered on first login via `sgh auth app` (the PEM key is
    copied into ~/.supergh/apps/ and recorded in registry.json). These commands
    let you see and remove them.
    """


@app_cmd.command("list")
def app_list():
    """List registered GitHub Apps."""
    registry = get_registry()
    apps = registry.list_apps()

    if not apps:
        console.print("[yellow]No apps registered.[/yellow]")
        console.print("  Register one with: [cyan]sgh auth app --name <name> --app-id <id> --pem <path>[/cyan]")
        return

    table = Table(title="Registered GitHub Apps")
    table.add_column("Name", style="cyan")
    table.add_column("App ID")
    table.add_column("Org")
    table.add_column("PEM file", style="dim")
    table.add_column("Key present")

    for name, entry in sorted(apps.items()):
        present = "[green]✓[/green]" if registry.pem_present(entry) else "[red]✕ missing[/red]"
        table.add_row(name, entry.app_id or "-", entry.org or "-", entry.pem_file or "-", present)

    console.print(table)
    console.print(f"[dim]Registry: {registry.registry_file}[/dim]")


@app_cmd.command("remove")
@click.argument("name")
@click.option("--keep-pem", is_flag=True, help="Keep the copied PEM file on disk.")
@click.confirmation_option(prompt="Remove this app from the registry?")
def app_remove(name, keep_pem):
    """Remove a registered app (and delete its stored PEM unless --keep-pem)."""
    registry = get_registry()
    if not registry.exists(name):
        console.print(f"[red]App '{name}' is not registered.[/red]")
        available = ", ".join(sorted(registry.list_apps().keys())) or "(none)"
        console.print(f"  Available: {available}")
        raise SystemExit(1)

    registry.remove(name, delete_pem=not keep_pem)
    extra = " (PEM kept)" if keep_pem else " and deleted its PEM"
    console.print(f"[green]Removed app '{name}'{extra}.[/green]")
