"""sgh search / browse / status / ssh-key / gpg-key / cache / api / completion."""

import json
import subprocess
import sys
import webbrowser

import click
from rich.console import Console
from rich.table import Table

from supergh.api.client import GitHubClient
from supergh.commands.pr import _resolve_repo
from supergh.config import get_config

console = Console()


def _client(ctx) -> GitHubClient:
    return GitHubClient(debug=ctx.obj.get("debug", False))


# --- Search ---

@click.group("search")
@click.pass_context
def search(ctx):
    """Search GitHub."""


@search.command("repos")
@click.argument("query")
@click.option("--limit", "-l", default=10)
@click.pass_context
def search_repos(ctx, query, limit):
    """Search repositories."""
    client = _client(ctx)
    data = client.get("/search/repositories", params={"q": query, "per_page": limit})

    table = Table(title=f"Repo search: {query}")
    table.add_column("Name", style="cyan")
    table.add_column("Stars", justify="right")
    table.add_column("Language", style="green")
    table.add_column("Description", style="dim", max_width=40)

    for r in data["items"][:limit]:
        table.add_row(r["full_name"], str(r["stargazers_count"]), r.get("language") or "-", (r.get("description") or "")[:40])
    console.print(table)


@search.command("code")
@click.argument("query")
@click.option("--org", "-o", default=None)
@click.option("--limit", "-l", default=10)
@click.pass_context
def search_code(ctx, query, org, limit):
    """Search code."""
    client = _client(ctx)
    cfg = get_config()
    o = org or cfg.org
    q = f"{query} org:{o}" if o else query
    data = client.get("/search/code", params={"q": q, "per_page": limit})

    table = Table(title=f"Code search: {query}")
    table.add_column("File", style="cyan")
    table.add_column("Repo", style="yellow")
    table.add_column("Path", style="dim")

    for item in data["items"][:limit]:
        table.add_row(item["name"], item["repository"]["full_name"], item["path"])
    console.print(table)


@search.command("issues")
@click.argument("query")
@click.option("--org", "-o", default=None)
@click.option("--limit", "-l", default=10)
@click.pass_context
def search_issues(ctx, query, org, limit):
    """Search issues."""
    client = _client(ctx)
    cfg = get_config()
    o = org or cfg.org
    q = f"{query} org:{o}" if o else query
    data = client.get("/search/issues", params={"q": q + " is:issue", "per_page": limit})

    table = Table(title=f"Issue search: {query}")
    table.add_column("#", justify="right")
    table.add_column("Title", style="cyan", max_width=50)
    table.add_column("Repo", style="yellow")
    table.add_column("State")

    for i in data["items"][:limit]:
        table.add_row(str(i["number"]), i["title"], i["repository_url"].split("/repos/")[-1], i["state"])
    console.print(table)


@search.command("prs")
@click.argument("query")
@click.option("--org", "-o", default=None)
@click.option("--limit", "-l", default=10)
@click.pass_context
def search_prs(ctx, query, org, limit):
    """Search pull requests."""
    client = _client(ctx)
    cfg = get_config()
    o = org or cfg.org
    q = f"{query} org:{o}" if o else query
    data = client.get("/search/issues", params={"q": q + " is:pr", "per_page": limit})

    table = Table(title=f"PR search: {query}")
    table.add_column("#", justify="right")
    table.add_column("Title", style="cyan", max_width=50)
    table.add_column("Repo", style="yellow")
    table.add_column("State")

    for i in data["items"][:limit]:
        table.add_row(str(i["number"]), i["title"], i["repository_url"].split("/repos/")[-1], i["state"])
    console.print(table)


@search.command("commits")
@click.argument("query")
@click.option("--org", "-o", default=None)
@click.option("--limit", "-l", default=10)
@click.pass_context
def search_commits(ctx, query, org, limit):
    """Search commits."""
    client = _client(ctx)
    cfg = get_config()
    o = org or cfg.org
    q = f"{query} org:{o}" if o else query
    data = client.get("/search/commits", params={"q": q, "per_page": limit})

    table = Table(title=f"Commit search: {query}")
    table.add_column("SHA", style="dim")
    table.add_column("Message", style="cyan", max_width=50)
    table.add_column("Author", style="yellow")
    table.add_column("Repo")

    for c in data["items"][:limit]:
        table.add_row(c["sha"][:8], c["commit"]["message"].split("\n")[0][:50], c["commit"]["author"]["name"], c["repository"]["full_name"])
    console.print(table)


# --- Browse ---

@click.command("browse")
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.pass_context
def browse(ctx, repo_name, org):
    """Open repo in browser."""
    full_name = _resolve_repo(org, repo_name)
    url = f"https://github.com/{full_name}"
    webbrowser.open(url)
    console.print(f"[dim]Opened {url}[/dim]")


# --- Status ---

@click.command("status")
@click.pass_context
def status(ctx):
    """Show your cross-repo activity."""
    client = _client(ctx)
    events = client.get("/notifications", params={"per_page": 15})

    table = Table(title="Recent Notifications")
    table.add_column("Repo", style="cyan")
    table.add_column("Type", style="yellow")
    table.add_column("Title", max_width=50)
    table.add_column("Updated", style="dim")

    for e in events[:15]:
        table.add_row(
            e["repository"]["full_name"],
            e["subject"]["type"],
            e["subject"]["title"][:50],
            e["updated_at"][:10],
        )
    console.print(table)


# --- SSH Key ---

@click.group("ssh-key")
@click.pass_context
def ssh_key(ctx):
    """Manage SSH keys."""


@ssh_key.command("list")
@click.pass_context
def ssh_key_list(ctx):
    """List SSH keys."""
    client = _client(ctx)
    keys = client.get("/user/keys")

    table = Table(title="SSH Keys")
    table.add_column("ID", justify="right")
    table.add_column("Title", style="cyan")
    table.add_column("Key", style="dim", max_width=40)
    table.add_column("Added", style="dim")

    for k in keys:
        table.add_row(str(k["id"]), k["title"], k["key"][:40] + "...", k["created_at"][:10])
    console.print(table)


@ssh_key.command("add")
@click.argument("key_file", type=click.Path(exists=True))
@click.option("--title", "-t", required=True)
@click.pass_context
def ssh_key_add(ctx, key_file, title):
    """Add an SSH key."""
    from pathlib import Path
    key_content = Path(key_file).read_text().strip()
    client = _client(ctx)
    client.post("/user/keys", json={"title": title, "key": key_content})
    console.print(f"[green]Added SSH key: {title}[/green]")


@ssh_key.command("delete")
@click.argument("key_id", type=int)
@click.pass_context
def ssh_key_delete(ctx, key_id):
    """Delete an SSH key."""
    client = _client(ctx)
    client.delete(f"/user/keys/{key_id}")
    console.print(f"[green]Deleted SSH key {key_id}[/green]")


# --- GPG Key ---

@click.group("gpg-key")
@click.pass_context
def gpg_key(ctx):
    """Manage GPG keys."""


@gpg_key.command("list")
@click.pass_context
def gpg_key_list(ctx):
    """List GPG keys."""
    client = _client(ctx)
    keys = client.get("/user/gpg_keys")

    table = Table(title="GPG Keys")
    table.add_column("ID", justify="right")
    table.add_column("Key ID", style="cyan")
    table.add_column("Emails", style="dim")
    table.add_column("Added", style="dim")

    for k in keys:
        emails = ", ".join(e["email"] for e in k.get("emails", []))
        table.add_row(str(k["id"]), k.get("key_id", ""), emails, k["created_at"][:10])
    console.print(table)


@gpg_key.command("add")
@click.argument("key_file", type=click.Path(exists=True))
@click.pass_context
def gpg_key_add(ctx, key_file):
    """Add a GPG key."""
    from pathlib import Path
    key_content = Path(key_file).read_text().strip()
    client = _client(ctx)
    client.post("/user/gpg_keys", json={"armored_public_key": key_content})
    console.print(f"[green]Added GPG key[/green]")


@gpg_key.command("delete")
@click.argument("key_id", type=int)
@click.pass_context
def gpg_key_delete(ctx, key_id):
    """Delete a GPG key."""
    client = _client(ctx)
    client.delete(f"/user/gpg_keys/{key_id}")
    console.print(f"[green]Deleted GPG key {key_id}[/green]")


# --- Cache ---

@click.group("cache")
@click.pass_context
def cache_cmd(ctx):
    """Manage Actions cache."""


@cache_cmd.command("list")
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.pass_context
def cache_list(ctx, repo_name, org):
    """List Actions caches."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    data = client.get(f"/repos/{full_name}/actions/caches")

    table = Table(title=f"Actions Caches — {full_name}")
    table.add_column("ID", justify="right")
    table.add_column("Key", style="cyan", max_width=50)
    table.add_column("Size (MB)", justify="right")
    table.add_column("Created", style="dim")

    for c in data.get("actions_caches", []):
        size_mb = round(c.get("size_in_bytes", 0) / 1024 / 1024, 1)
        table.add_row(str(c["id"]), c["key"][:50], str(size_mb), c.get("created_at", "")[:10])
    console.print(table)


@cache_cmd.command("delete")
@click.argument("cache_id", type=int)
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.pass_context
def cache_delete(ctx, cache_id, repo_name, org):
    """Delete an Actions cache."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    client.delete(f"/repos/{full_name}/actions/caches/{cache_id}")
    console.print(f"[green]Deleted cache {cache_id}[/green]")


# --- API (raw passthrough) ---

@click.command("api")
@click.argument("endpoint")
@click.option("--method", "-X", default="GET", type=click.Choice(["GET", "POST", "PUT", "PATCH", "DELETE"]))
@click.option("--body", "-b", default=None, help="JSON body.")
@click.option("--jq", "jq_filter", default=None, help="JQ-style key to extract (simple dot notation).")
@click.pass_context
def api(ctx, endpoint, method, body, jq_filter):
    """Make a raw GitHub API call."""
    client = _client(ctx)
    kwargs = {}
    if body:
        kwargs["json"] = json.loads(body)

    resp = client.request(method, endpoint, **kwargs)
    data = resp.json() if resp.content else {}

    if jq_filter:
        for key in jq_filter.strip(".").split("."):
            if isinstance(data, list):
                data = [item.get(key) for item in data]
            else:
                data = data.get(key)

    click.echo(json.dumps(data, indent=2))


# --- Completion ---

@click.command("completion")
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish", "powershell"]))
def completion(shell):
    """Generate shell completion script."""
    import importlib
    if shell == "bash":
        click.echo('eval "$(_SGH_COMPLETE=bash_source sgh)"')
    elif shell == "zsh":
        click.echo('eval "$(_SGH_COMPLETE=zsh_source sgh)"')
    elif shell == "fish":
        click.echo('eval (env _SGH_COMPLETE=fish_source sgh)')
    elif shell == "powershell":
        click.echo('Register-ArgumentCompleter -Native -CommandName sgh -ScriptBlock { param($wordToComplete, $commandAst, $cursorPosition) _SGH_COMPLETE=powershell_source sgh | ForEach-Object { [System.Management.Automation.CompletionResult]::new($_, $_, "ParameterValue", $_) } }')
