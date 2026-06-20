"""sgh codespace — manage GitHub Codespaces."""

import click
from rich.console import Console
from rich.table import Table

from supergh.api.client import GitHubClient
from supergh.config import get_config

console = Console()


def _client(ctx) -> GitHubClient:
    return GitHubClient(debug=ctx.obj.get("debug", False))


@click.group("codespace")
@click.pass_context
def codespace(ctx):
    """Connect to and manage codespaces."""


@codespace.command("list")
@click.option("--org", "-o", default=None)
@click.option("--repo", "-r", default=None, help="Filter by repo name.")
@click.option("--limit", "-l", default=30)
@click.pass_context
def codespace_list(ctx, org, repo, limit):
    """List codespaces."""
    client = _client(ctx)
    cfg = get_config()
    o = org or cfg.org

    if o:
        data = client.get(f"/orgs/{o}/codespaces", params={"per_page": limit})
    else:
        data = client.get("/user/codespaces", params={"per_page": limit})

    codespaces = data.get("codespaces", [])
    if repo:
        codespaces = [c for c in codespaces if repo in c.get("repository", {}).get("full_name", "")]

    table = Table(title="Codespaces")
    table.add_column("Name", style="cyan")
    table.add_column("Repo", style="dim")
    table.add_column("Branch", style="yellow")
    table.add_column("State")
    table.add_column("Machine", style="dim")
    table.add_column("Created", style="dim")

    for c in codespaces[:limit]:
        state = c.get("state", "")
        style = "green" if state == "Available" else "yellow" if state == "Queued" else "dim"
        table.add_row(
            c.get("name", ""),
            c.get("repository", {}).get("full_name", ""),
            c.get("git_status", {}).get("ref", ""),
            f"[{style}]{state}[/{style}]",
            c.get("machine", {}).get("display_name", ""),
            c.get("created_at", "")[:10],
        )
    console.print(table)


@codespace.command("create")
@click.argument("repo_name")
@click.option("--org", "-o", default=None)
@click.option("--branch", "-b", default=None, help="Branch to create from.")
@click.option("--machine", "-m", default=None, help="Machine type (e.g. basicLinux32gb).")
@click.option("--idle-timeout", default=None, type=int, help="Idle timeout in minutes.")
@click.pass_context
def codespace_create(ctx, repo_name, org, branch, machine, idle_timeout):
    """Create a codespace."""
    client = _client(ctx)
    cfg = get_config()
    o = org or cfg.org
    full_name = f"{o}/{repo_name}" if o and "/" not in repo_name else repo_name

    payload = {"repository_id": None}
    # Get repo ID
    repo_data = client.get(f"/repos/{full_name}")
    payload["repository_id"] = repo_data["id"]
    if branch:
        payload["ref"] = branch
    if machine:
        payload["machine"] = machine
    if idle_timeout:
        payload["idle_timeout_minutes"] = idle_timeout

    c = client.post("/user/codespaces", json=payload)
    console.print(f"[green]Created codespace: {c['name']}[/green]")
    console.print(f"  State: {c['state']}")
    console.print(f"  URL:   {c.get('web_url', '')}")


@codespace.command("delete")
@click.argument("name")
@click.option("--yes", is_flag=True, help="Skip confirmation.")
@click.pass_context
def codespace_delete(ctx, name, yes):
    """Delete a codespace."""
    if not yes:
        click.confirm(f"Delete codespace '{name}'?", abort=True)
    client = _client(ctx)
    client.delete(f"/user/codespaces/{name}")
    console.print(f"[green]Deleted codespace '{name}'[/green]")


@codespace.command("stop")
@click.argument("name")
@click.pass_context
def codespace_stop(ctx, name):
    """Stop a running codespace."""
    client = _client(ctx)
    client.post(f"/user/codespaces/{name}/stop")
    console.print(f"[green]Stopped codespace '{name}'[/green]")


@codespace.command("start")
@click.argument("name")
@click.pass_context
def codespace_start(ctx, name):
    """Start a stopped codespace."""
    client = _client(ctx)
    client.post(f"/user/codespaces/{name}/start")
    console.print(f"[green]Started codespace '{name}'[/green]")
