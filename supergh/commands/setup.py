"""sgh setup — first-run configuration wizard."""

import click
from rich.console import Console
from rich.panel import Panel

from supergh.config import get_config
from supergh.utils.logger import set_log_level, LEVELS

console = Console()


@click.command("setup")
@click.pass_context
def setup(ctx):
    """First-time setup wizard.

    Configures organization, logging, and authentication.
    Run this after installing sgh for the first time.
    """
    console.print(Panel("[bold]sgh — First-time Setup[/bold]\n\nThis will configure your default organization, log level, and authentication.", border_style="blue"))

    # 1. Organization
    console.print("\n[bold]1. Organization[/bold]")
    org = click.prompt("  Default GitHub org (leave empty for personal)", default="", show_default=False)
    cfg = get_config()
    if org:
        cfg.set("core.default_org", org)
        console.print(f"  [green]Set default org: {org}[/green]")
    else:
        console.print("  [dim]Skipped — using personal account.[/dim]")

    # 2. Logging
    console.print("\n[bold]2. Logging[/bold]")
    console.print("  Logs are written to ~/.supergh/logs/sgh.log")
    console.print("  Levels: debug (verbose), info (default), warning, error, off")
    level = click.prompt("  Log level", type=click.Choice(list(LEVELS.keys())), default="info", show_choices=False)
    set_log_level(level)
    console.print(f"  [green]Log level set: {level}[/green]")

    # 3. Authentication
    console.print("\n[bold]3. Authentication[/bold]")
    console.print("  Choose how to authenticate with GitHub:")
    console.print("    [cyan]pat[/cyan]   — Personal Access Token (quickest)")
    console.print("    [cyan]oauth[/cyan] — OAuth device flow")
    console.print("    [cyan]app[/cyan]   — GitHub App (for CI/automation)")
    console.print("    [cyan]skip[/cyan]  — Set up later")

    auth_choice = click.prompt("  Auth method", type=click.Choice(["pat", "oauth", "app", "skip"]), default="pat", show_choices=False)

    if auth_choice == "skip":
        console.print("  [dim]Skipped — run 'sgh auth pat' later.[/dim]")
    else:
        console.print(f"\n  Running: sgh auth {auth_choice}")
        ctx.invoke(ctx.parent.command.get_command(ctx, "auth").get_command(ctx, auth_choice))

    # Done
    console.print(Panel("[bold green]Setup complete![/bold green]\n\nTry: sgh repo list", border_style="green"))
