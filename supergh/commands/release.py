"""sgh release — release management commands."""

import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from supergh.api.client import GitHubClient
from supergh.commands.pr import _resolve_repo

console = Console()


def _client(ctx) -> GitHubClient:
    return GitHubClient(debug=ctx.obj.get("debug", False))


@click.group("release")
@click.pass_context
def release(ctx):
    """Manage releases."""


@release.command("list")
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.option("--limit", "-l", default=10)
@click.pass_context
def release_list(ctx, repo_name, org, limit):
    """List releases."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)

    releases = []
    for r in client.paginate(f"/repos/{full_name}/releases", params={"per_page": min(limit, 100)}):
        releases.append(r)
        if len(releases) >= limit:
            break

    table = Table(title=f"Releases — {full_name}")
    table.add_column("Tag", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Pre-release", style="yellow")
    table.add_column("Published", style="dim")
    table.add_column("Assets", justify="right")

    for r in releases:
        table.add_row(r["tag_name"], r.get("name") or "-", str(r["prerelease"]), (r.get("published_at") or "")[:10], str(len(r.get("assets", []))))
    console.print(table)


@release.command("view")
@click.argument("tag")
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.pass_context
def release_view(ctx, tag, repo_name, org):
    """View a release."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    r = client.get(f"/repos/{full_name}/releases/tags/{tag}")

    console.print(f"\n[bold cyan]{r['tag_name']}[/bold cyan] — {r.get('name') or 'No title'}")
    console.print(f"  Published: {(r.get('published_at') or '')[:10]}")
    console.print(f"  Author:    {r['author']['login']}")
    console.print(f"  Draft:     {r['draft']}")
    console.print(f"  Pre-release: {r['prerelease']}")
    console.print(f"  URL:       {r['html_url']}")
    if r.get("body"):
        console.print(f"\n{r['body'][:500]}")
    if r.get("assets"):
        console.print(f"\n[bold]Assets:[/bold]")
        for a in r["assets"]:
            console.print(f"  {a['name']} ({a['size'] // 1024}KB, {a['download_count']} downloads)")


@release.command("create")
@click.argument("tag")
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.option("--title", "-t", default=None)
@click.option("--body", "-b", default="")
@click.option("--target", default="main", help="Target branch or commit.")
@click.option("--draft", is_flag=True)
@click.option("--prerelease", is_flag=True)
@click.option("--generate-notes", is_flag=True, help="Auto-generate release notes.")
@click.pass_context
def release_create(ctx, tag, repo_name, org, title, body, target, draft, prerelease, generate_notes):
    """Create a release."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    payload = {
        "tag_name": tag,
        "name": title or tag,
        "body": body,
        "target_commitish": target,
        "draft": draft,
        "prerelease": prerelease,
        "generate_release_notes": generate_notes,
    }
    r = client.post(f"/repos/{full_name}/releases", json=payload)
    console.print(f"[green]Created release {r['tag_name']}[/green]")
    console.print(f"  {r['html_url']}")


@release.command("delete")
@click.argument("tag")
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.option("--yes", is_flag=True)
@click.pass_context
def release_delete(ctx, tag, repo_name, org, yes):
    """Delete a release."""
    full_name = _resolve_repo(org, repo_name)
    if not yes:
        click.confirm(f"Delete release {tag}?", abort=True)
    client = _client(ctx)
    r = client.get(f"/repos/{full_name}/releases/tags/{tag}")
    client.delete(f"/repos/{full_name}/releases/{r['id']}")
    console.print(f"[green]Deleted release {tag}[/green]")


@release.command("upload")
@click.argument("tag")
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.pass_context
def release_upload(ctx, tag, file_path, repo_name, org):
    """Upload an asset to a release."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    r = client.get(f"/repos/{full_name}/releases/tags/{tag}")
    upload_url = r["upload_url"].split("{")[0]

    import requests as req
    from supergh.auth.middleware import get_auth_provider

    token = get_auth_provider().get_token()
    file_path = Path(file_path)

    with open(file_path, "rb") as f:
        resp = req.post(
            upload_url,
            params={"name": file_path.name},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
            data=f, timeout=120,
        )
    resp.raise_for_status()
    console.print(f"[green]Uploaded {file_path.name} to {tag}[/green]")
