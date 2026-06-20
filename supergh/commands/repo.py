"""sgh repo — repository commands."""

import json
import subprocess

import click
from rich.console import Console
from rich.table import Table

from supergh.api.client import GitHubClient
from supergh.config import get_config

console = Console()


def _client(ctx) -> GitHubClient:
    return GitHubClient(debug=ctx.obj.get("debug", False))


@click.group("repo")
@click.pass_context
def repo(ctx):
    """Manage repositories."""


@repo.command("list")
@click.option("--org", "-o", default=None, help="Organization name.")
@click.option("--limit", "-l", default=30, help="Max repos to show.")
@click.option("--type", "repo_type", type=click.Choice(["all", "public", "private", "forks", "sources", "member"]), default="all")
@click.option("--sort", type=click.Choice(["created", "updated", "pushed", "full_name"]), default="pushed")
@click.option("--output", "output_fmt", type=click.Choice(["table", "json", "csv"]), default="table", help="Output format.")
@click.option("--export", "export_path", default=None, help="Export to file (.csv, .json, .xlsx, .md).")
@click.pass_context
def repo_list(ctx, org, limit, repo_type, sort, output_fmt, export_path):
    """List repositories."""
    cfg = get_config()
    org = org or cfg.org
    client = _client(ctx)

    if org:
        path = f"/orgs/{org}/repos"
    else:
        path = "/user/repos"

    params = {"type": repo_type, "sort": sort, "per_page": min(limit, 100)}
    repos = []
    for r in client.paginate(path, params=params):
        repos.append(r)
        if len(repos) >= limit:
            break

    rows = [{"name": r["name"], "visibility": r["visibility"], "language": r.get("language") or "", "stars": r["stargazers_count"], "updated": r["updated_at"][:10], "url": r["html_url"]} for r in repos]

    if export_path:
        from supergh.export import export_data
        export_data(rows, export_path)
        return

    if output_fmt != "table":
        from supergh.export import format_for_output
        click.echo(format_for_output(rows, output_fmt))
        return

    table = Table(title=f"Repositories ({org or 'personal'})")
    table.add_column("Name", style="cyan")
    table.add_column("Visibility", style="yellow")
    table.add_column("Language", style="green")
    table.add_column("Stars", justify="right")
    table.add_column("Updated", style="dim")

    for r in repos:
        table.add_row(
            r["name"],
            r["visibility"],
            r.get("language") or "-",
            str(r["stargazers_count"]),
            r["updated_at"][:10],
        )
    console.print(table)


@repo.command("view")
@click.argument("name")
@click.option("--org", "-o", default=None)
@click.pass_context
def repo_view(ctx, name, org):
    """View repository details."""
    cfg = get_config()
    org = org or cfg.org
    client = _client(ctx)
    full_name = f"{org}/{name}" if org and "/" not in name else name
    r = client.get(f"/repos/{full_name}")

    console.print(f"\n[bold cyan]{r['full_name']}[/bold cyan]")
    console.print(f"  {r.get('description') or 'No description'}\n")
    console.print(f"  Visibility:    {r['visibility']}")
    console.print(f"  Default branch:{r['default_branch']}")
    console.print(f"  Language:      {r.get('language') or 'N/A'}")
    console.print(f"  Stars:         {r['stargazers_count']}")
    console.print(f"  Forks:         {r['forks_count']}")
    console.print(f"  Open issues:   {r['open_issues_count']}")
    console.print(f"  Created:       {r['created_at'][:10]}")
    console.print(f"  Updated:       {r['updated_at'][:10]}")
    console.print(f"  URL:           {r['html_url']}")
    if r.get("topics"):
        console.print(f"  Topics:        {', '.join(r['topics'])}")


@repo.command("create")
@click.argument("name")
@click.option("--org", "-o", default=None)
@click.option("--private/--public", default=True)
@click.option("--description", "-d", default="")
@click.option("--template", default=None, help="Template repo (owner/name).")
@click.pass_context
def repo_create(ctx, name, org, private, description, template):
    """Create a new repository."""
    cfg = get_config()
    org = org or cfg.org
    client = _client(ctx)

    payload = {"name": name, "private": private, "description": description}
    if template:
        owner, tmpl = template.split("/")
        r = client.post(f"/repos/{owner}/{tmpl}/generate", json={"owner": org or None, "name": name, "private": private, "description": description})
    elif org:
        r = client.post(f"/orgs/{org}/repos", json=payload)
    else:
        r = client.post("/user/repos", json=payload)

    console.print(f"[green]Created {r['full_name']}[/green]")
    console.print(f"  {r['html_url']}")


@repo.command("clone")
@click.argument("name")
@click.option("--org", "-o", default=None)
@click.option("--dir", "directory", default=None, help="Target directory.")
@click.pass_context
def repo_clone(ctx, name, org, directory):
    """Clone a repository."""
    cfg = get_config()
    org = org or cfg.org
    full_name = f"{org}/{name}" if org and "/" not in name else name
    url = f"https://github.com/{full_name}.git"
    cmd = ["git", "clone", url]
    if directory:
        cmd.append(directory)
    console.print(f"[dim]Cloning {full_name}...[/dim]")
    subprocess.run(cmd, check=True)
    console.print(f"[green]Cloned {full_name}[/green]")


@repo.command("fork")
@click.argument("name")
@click.option("--org", "-o", default=None, help="Source org.")
@click.option("--fork-org", default=None, help="Org to fork into.")
@click.pass_context
def repo_fork(ctx, name, org, fork_org):
    """Fork a repository."""
    cfg = get_config()
    org = org or cfg.org
    client = _client(ctx)
    full_name = f"{org}/{name}" if org and "/" not in name else name
    payload = {}
    if fork_org:
        payload["organization"] = fork_org
    r = client.post(f"/repos/{full_name}/forks", json=payload)
    console.print(f"[green]Forked to {r['full_name']}[/green]")


@repo.command("delete")
@click.argument("name")
@click.option("--org", "-o", default=None)
@click.option("--yes", is_flag=True, help="Skip confirmation.")
@click.pass_context
def repo_delete(ctx, name, org, yes):
    """Delete a repository."""
    cfg = get_config()
    org = org or cfg.org
    full_name = f"{org}/{name}" if org and "/" not in name else name
    if not yes:
        click.confirm(f"Delete {full_name}? This cannot be undone", abort=True)
    client = _client(ctx)
    client.delete(f"/repos/{full_name}")
    console.print(f"[green]Deleted {full_name}[/green]")


@repo.command("archive")
@click.argument("name")
@click.option("--org", "-o", default=None)
@click.pass_context
def repo_archive(ctx, name, org):
    """Archive a repository."""
    cfg = get_config()
    org = org or cfg.org
    full_name = f"{org}/{name}" if org and "/" not in name else name
    client = _client(ctx)
    client.patch(f"/repos/{full_name}", json={"archived": True})
    console.print(f"[green]Archived {full_name}[/green]")


@repo.command("unarchive")
@click.argument("name")
@click.option("--org", "-o", default=None)
@click.pass_context
def repo_unarchive(ctx, name, org):
    """Unarchive a repository."""
    cfg = get_config()
    org = org or cfg.org
    full_name = f"{org}/{name}" if org and "/" not in name else name
    client = _client(ctx)
    client.patch(f"/repos/{full_name}", json={"archived": False})
    console.print(f"[green]Unarchived {full_name}[/green]")


@repo.command("rename")
@click.argument("name")
@click.argument("new_name")
@click.option("--org", "-o", default=None)
@click.pass_context
def repo_rename(ctx, name, new_name, org):
    """Rename a repository."""
    cfg = get_config()
    org = org or cfg.org
    full_name = f"{org}/{name}" if org and "/" not in name else name
    client = _client(ctx)
    r = client.patch(f"/repos/{full_name}", json={"name": new_name})
    console.print(f"[green]Renamed to {r['full_name']}[/green]")


@repo.command("edit")
@click.argument("name")
@click.option("--org", "-o", default=None)
@click.option("--description", "-d", default=None)
@click.option("--homepage", default=None)
@click.option("--default-branch", default=None)
@click.option("--private/--public", default=None)
@click.option("--topics", default=None, help="Comma-separated topics.")
@click.pass_context
def repo_edit(ctx, name, org, description, homepage, default_branch, private, topics):
    """Edit repository settings."""
    cfg = get_config()
    org = org or cfg.org
    full_name = f"{org}/{name}" if org and "/" not in name else name
    client = _client(ctx)

    payload = {}
    if description is not None:
        payload["description"] = description
    if homepage is not None:
        payload["homepage"] = homepage
    if default_branch is not None:
        payload["default_branch"] = default_branch
    if private is not None:
        payload["private"] = private

    if payload:
        client.patch(f"/repos/{full_name}", json=payload)

    if topics is not None:
        topic_list = [t.strip() for t in topics.split(",")]
        client.put(f"/repos/{full_name}/topics", json={"names": topic_list})

    console.print(f"[green]Updated {full_name}[/green]")
