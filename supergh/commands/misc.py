"""sgh label / milestone / org / team / gist commands."""

import json

import click
from rich.console import Console
from rich.table import Table

from supergh.api.client import GitHubClient
from supergh.commands.pr import _resolve_repo
from supergh.config import get_config

console = Console()


def _client(ctx) -> GitHubClient:
    return GitHubClient(debug=ctx.obj.get("debug", False))


# --- Label ---

@click.group("label")
@click.pass_context
def label(ctx):
    """Manage labels."""


@label.command("list")
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.pass_context
def label_list(ctx, repo_name, org):
    """List labels."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    labels = list(client.paginate(f"/repos/{full_name}/labels"))

    table = Table(title=f"Labels — {full_name}")
    table.add_column("Name", style="cyan")
    table.add_column("Color")
    table.add_column("Description", style="dim")

    for l in labels:
        table.add_row(l["name"], f"#{l['color']}", l.get("description") or "")
    console.print(table)


@label.command("create")
@click.argument("name")
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.option("--color", "-c", default="ededed", help="Hex color without #.")
@click.option("--description", "-d", default="")
@click.pass_context
def label_create(ctx, name, repo_name, org, color, description):
    """Create a label."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    client.post(f"/repos/{full_name}/labels", json={"name": name, "color": color, "description": description})
    console.print(f"[green]Created label '{name}'[/green]")


@label.command("edit")
@click.argument("name")
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.option("--new-name", default=None)
@click.option("--color", "-c", default=None)
@click.option("--description", "-d", default=None)
@click.pass_context
def label_edit(ctx, name, repo_name, org, new_name, color, description):
    """Edit a label."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    payload = {}
    if new_name:
        payload["new_name"] = new_name
    if color:
        payload["color"] = color
    if description is not None:
        payload["description"] = description
    client.patch(f"/repos/{full_name}/labels/{name}", json=payload)
    console.print(f"[green]Updated label '{name}'[/green]")


@label.command("delete")
@click.argument("name")
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.pass_context
def label_delete(ctx, name, repo_name, org):
    """Delete a label."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    client.delete(f"/repos/{full_name}/labels/{name}")
    console.print(f"[green]Deleted label '{name}'[/green]")


@label.command("clone")
@click.argument("source_repo")
@click.argument("target_repo")
@click.option("--org", "-o", default=None)
@click.pass_context
def label_clone(ctx, source_repo, target_repo, org):
    """Clone labels from one repo to another."""
    cfg = get_config()
    o = org or cfg.org
    source = f"{o}/{source_repo}" if o and "/" not in source_repo else source_repo
    target = f"{o}/{target_repo}" if o and "/" not in target_repo else target_repo
    client = _client(ctx)

    labels = list(client.paginate(f"/repos/{source}/labels"))
    for l in labels:
        try:
            client.post(f"/repos/{target}/labels", json={"name": l["name"], "color": l["color"], "description": l.get("description", "")})
        except Exception:
            pass  # label may already exist
    console.print(f"[green]Cloned {len(labels)} labels from {source} to {target}[/green]")


# --- Milestone ---

@click.group("milestone")
@click.pass_context
def milestone(ctx):
    """Manage milestones."""


@milestone.command("list")
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.option("--state", type=click.Choice(["open", "closed", "all"]), default="open")
@click.pass_context
def milestone_list(ctx, repo_name, org, state):
    """List milestones."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    milestones = list(client.paginate(f"/repos/{full_name}/milestones", params={"state": state}))

    table = Table(title=f"Milestones — {full_name}")
    table.add_column("#", justify="right")
    table.add_column("Title", style="cyan")
    table.add_column("Open", justify="right")
    table.add_column("Closed", justify="right")
    table.add_column("Due", style="dim")

    for m in milestones:
        table.add_row(str(m["number"]), m["title"], str(m["open_issues"]), str(m["closed_issues"]), (m.get("due_on") or "")[:10])
    console.print(table)


@milestone.command("create")
@click.argument("title")
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.option("--description", "-d", default="")
@click.option("--due", default=None, help="Due date (YYYY-MM-DD).")
@click.pass_context
def milestone_create(ctx, title, repo_name, org, description, due):
    """Create a milestone."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    payload = {"title": title, "description": description}
    if due:
        payload["due_on"] = f"{due}T00:00:00Z"
    m = client.post(f"/repos/{full_name}/milestones", json=payload)
    console.print(f"[green]Created milestone #{m['number']}: {m['title']}[/green]")


@milestone.command("edit")
@click.argument("number", type=int)
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.option("--title", "-t", default=None)
@click.option("--state", type=click.Choice(["open", "closed"]), default=None)
@click.option("--description", "-d", default=None)
@click.pass_context
def milestone_edit(ctx, number, repo_name, org, title, state, description):
    """Edit a milestone."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    payload = {}
    if title:
        payload["title"] = title
    if state:
        payload["state"] = state
    if description is not None:
        payload["description"] = description
    client.patch(f"/repos/{full_name}/milestones/{number}", json=payload)
    console.print(f"[green]Updated milestone #{number}[/green]")


@milestone.command("delete")
@click.argument("number", type=int)
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.pass_context
def milestone_delete(ctx, number, repo_name, org):
    """Delete a milestone."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    client.delete(f"/repos/{full_name}/milestones/{number}")
    console.print(f"[green]Deleted milestone #{number}[/green]")


# --- Org ---

@click.group("org")
@click.pass_context
def org_cmd(ctx):
    """Manage organizations."""


@org_cmd.command("list")
@click.pass_context
def org_list(ctx):
    """List your organizations."""
    client = _client(ctx)
    orgs = list(client.paginate("/user/orgs"))

    table = Table(title="Organizations")
    table.add_column("Login", style="cyan")
    table.add_column("Description", style="dim")

    for o in orgs:
        table.add_row(o["login"], o.get("description") or "")
    console.print(table)


@org_cmd.command("view")
@click.argument("name", default=None, required=False)
@click.pass_context
def org_view(ctx, name):
    """View organization details."""
    cfg = get_config()
    name = name or cfg.org
    client = _client(ctx)
    o = client.get(f"/orgs/{name}")

    console.print(f"\n[bold cyan]{o['login']}[/bold cyan]")
    console.print(f"  Name:         {o.get('name') or 'N/A'}")
    console.print(f"  Description:  {o.get('description') or 'N/A'}")
    console.print(f"  Public repos: {o['public_repos']}")
    console.print(f"  Members:      {o.get('members', 'N/A')}")
    console.print(f"  URL:          {o['html_url']}")


# --- Team ---

@click.group("team")
@click.pass_context
def team(ctx):
    """Manage teams."""


@team.command("list")
@click.option("--org", "-o", default=None)
@click.pass_context
def team_list(ctx, org):
    """List teams in an org."""
    cfg = get_config()
    o = org or cfg.org
    client = _client(ctx)
    teams = list(client.paginate(f"/orgs/{o}/teams"))

    table = Table(title=f"Teams — {o}")
    table.add_column("Name", style="cyan")
    table.add_column("Slug", style="dim")
    table.add_column("Privacy")
    table.add_column("Members", justify="right")

    for t in teams:
        table.add_row(t["name"], t["slug"], t.get("privacy", ""), str(t.get("members_count", "?")))
    console.print(table)


@team.command("view")
@click.argument("slug")
@click.option("--org", "-o", default=None)
@click.pass_context
def team_view(ctx, slug, org):
    """View a team."""
    cfg = get_config()
    o = org or cfg.org
    client = _client(ctx)
    t = client.get(f"/orgs/{o}/teams/{slug}")
    console.print(f"\n[bold cyan]{t['name']}[/bold cyan]")
    console.print(f"  Slug:        {t['slug']}")
    console.print(f"  Description: {t.get('description') or 'N/A'}")
    console.print(f"  Privacy:     {t.get('privacy')}")
    console.print(f"  Members:     {t.get('members_count', '?')}")
    console.print(f"  Repos:       {t.get('repos_count', '?')}")


@team.command("add-member")
@click.argument("slug")
@click.argument("username")
@click.option("--org", "-o", default=None)
@click.option("--role", type=click.Choice(["member", "maintainer"]), default="member")
@click.pass_context
def team_add_member(ctx, slug, username, org, role):
    """Add a member to a team."""
    cfg = get_config()
    o = org or cfg.org
    client = _client(ctx)
    client.put(f"/orgs/{o}/teams/{slug}/memberships/{username}", json={"role": role})
    console.print(f"[green]Added {username} to {slug} as {role}[/green]")


@team.command("remove-member")
@click.argument("slug")
@click.argument("username")
@click.option("--org", "-o", default=None)
@click.pass_context
def team_remove_member(ctx, slug, username, org):
    """Remove a member from a team."""
    cfg = get_config()
    o = org or cfg.org
    client = _client(ctx)
    client.delete(f"/orgs/{o}/teams/{slug}/memberships/{username}")
    console.print(f"[green]Removed {username} from {slug}[/green]")


# --- Gist ---

@click.group("gist")
@click.pass_context
def gist(ctx):
    """Manage gists."""


@gist.command("list")
@click.option("--limit", "-l", default=10)
@click.option("--public/--private", default=None)
@click.pass_context
def gist_list(ctx, limit, public):
    """List your gists."""
    client = _client(ctx)
    gists = []
    for g in client.paginate("/gists"):
        if public is not None and g["public"] != public:
            continue
        gists.append(g)
        if len(gists) >= limit:
            break

    table = Table(title="Gists")
    table.add_column("ID", style="dim")
    table.add_column("Description", style="cyan")
    table.add_column("Files", justify="right")
    table.add_column("Public", style="yellow")
    table.add_column("Updated", style="dim")

    for g in gists:
        table.add_row(g["id"][:8], (g.get("description") or "No description")[:40], str(len(g["files"])), str(g["public"]), g["updated_at"][:10])
    console.print(table)


@gist.command("create")
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("--description", "-d", default="")
@click.option("--public", is_flag=True)
@click.pass_context
def gist_create(ctx, files, description, public):
    """Create a gist from files."""
    from pathlib import Path
    client = _client(ctx)
    file_data = {}
    for f in files:
        p = Path(f)
        file_data[p.name] = {"content": p.read_text(encoding="utf-8")}

    g = client.post("/gists", json={"description": description, "public": public, "files": file_data})
    console.print(f"[green]Created gist {g['id']}[/green]")
    console.print(f"  {g['html_url']}")


@gist.command("view")
@click.argument("gist_id")
@click.pass_context
def gist_view(ctx, gist_id):
    """View a gist."""
    client = _client(ctx)
    g = client.get(f"/gists/{gist_id}")
    console.print(f"\n[bold cyan]{g.get('description') or 'No description'}[/bold cyan]")
    console.print(f"  ID:      {g['id']}")
    console.print(f"  Public:  {g['public']}")
    console.print(f"  Files:   {', '.join(g['files'].keys())}")
    console.print(f"  URL:     {g['html_url']}")


@gist.command("delete")
@click.argument("gist_id")
@click.option("--yes", is_flag=True)
@click.pass_context
def gist_delete(ctx, gist_id, yes):
    """Delete a gist."""
    if not yes:
        click.confirm(f"Delete gist {gist_id}?", abort=True)
    client = _client(ctx)
    client.delete(f"/gists/{gist_id}")
    console.print(f"[green]Deleted gist {gist_id}[/green]")
