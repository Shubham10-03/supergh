"""sgh issue — issue commands."""

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


@click.group("issue")
@click.pass_context
def issue(ctx):
    """Manage issues."""


@issue.command("list")
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.option("--state", type=click.Choice(["open", "closed", "all"]), default="open")
@click.option("--assignee", default=None)
@click.option("--label", default=None)
@click.option("--milestone", default=None)
@click.option("--limit", "-l", default=30)
@click.option("--output", "output_fmt", type=click.Choice(["table", "json", "csv"]), default="table", help="Output format.")
@click.option("--export", "export_path", default=None, help="Export to file (.csv, .json, .xlsx, .md).")
@click.pass_context
def issue_list(ctx, repo_name, org, state, assignee, label, milestone, limit, output_fmt, export_path):
    """List issues."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)

    params = {"state": state, "per_page": min(limit, 100)}
    if assignee:
        params["assignee"] = assignee
    if label:
        params["labels"] = label
    if milestone:
        params["milestone"] = milestone

    issues = []
    for i in client.paginate(f"/repos/{full_name}/issues", params=params):
        if "pull_request" in i:
            continue
        issues.append(i)
        if len(issues) >= limit:
            break

    rows = [{"number": i["number"], "title": i["title"], "author": i["user"]["login"], "state": i["state"], "labels": ", ".join(l["name"] for l in i.get("labels", [])), "updated": i["updated_at"][:10], "url": i["html_url"]} for i in issues]

    if export_path:
        from supergh.export import export_data
        export_data(rows, export_path)
        return

    if output_fmt != "table":
        from supergh.export import format_for_output
        click.echo(format_for_output(rows, output_fmt))
        return

    table = Table(title=f"Issues — {full_name} ({state})")
    table.add_column("#", justify="right", style="bold")
    table.add_column("Title", style="cyan", max_width=60)
    table.add_column("Author", style="yellow")
    table.add_column("Labels", style="green")
    table.add_column("Updated", style="dim")

    for i in issues:
        labels = ", ".join(l["name"] for l in i.get("labels", []))
        table.add_row(str(i["number"]), i["title"], i["user"]["login"], labels or "-", i["updated_at"][:10])
    console.print(table)


@issue.command("view")
@click.argument("number", type=int, metavar="ISSUE_NUMBER")
@click.option("--repo", "-r", "repo_name", default=None, help="Repo name (or owner/repo).")
@click.option("--org", "-o", default=None, help="Organization name.")
@click.pass_context
def issue_view(ctx, number, repo_name, org):
    """View issue details."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    i = client.get(f"/repos/{full_name}/issues/{number}")

    console.print(f"\n[bold cyan]#{i['number']} {i['title']}[/bold cyan]")
    console.print(f"  State:      {i['state']}")
    console.print(f"  Author:     {i['user']['login']}")
    console.print(f"  Assignees:  {', '.join(a['login'] for a in i.get('assignees', [])) or 'None'}")
    console.print(f"  Labels:     {', '.join(l['name'] for l in i.get('labels', [])) or 'None'}")
    console.print(f"  Milestone:  {i['milestone']['title'] if i.get('milestone') else 'None'}")
    console.print(f"  Created:    {i['created_at'][:10]}")
    console.print(f"  Updated:    {i['updated_at'][:10]}")
    console.print(f"  Comments:   {i['comments']}")
    console.print(f"  URL:        {i['html_url']}")
    if i.get("body"):
        console.print(f"\n[dim]--- Body ---[/dim]")
        console.print(i["body"][:500])


@issue.command("create")
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.option("--title", "-t", required=True)
@click.option("--body", "-b", default="")
@click.option("--assignee", multiple=True)
@click.option("--label", multiple=True)
@click.option("--milestone", default=None, type=int)
@click.pass_context
def issue_create(ctx, repo_name, org, title, body, assignee, label, milestone):
    """Create an issue."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    payload = {"title": title, "body": body}
    if assignee:
        payload["assignees"] = list(assignee)
    if label:
        payload["labels"] = list(label)
    if milestone:
        payload["milestone"] = milestone

    i = client.post(f"/repos/{full_name}/issues", json=payload)
    console.print(f"[green]Created issue #{i['number']}: {i['title']}[/green]")
    console.print(f"  {i['html_url']}")


@issue.command("close")
@click.argument("number", type=int, metavar="ISSUE_NUMBER")
@click.option("--repo", "-r", "repo_name", default=None, help="Repo name (or owner/repo).")
@click.option("--org", "-o", default=None, help="Organization name.")
@click.option("--reason", type=click.Choice(["completed", "not_planned"]), default="completed")
@click.pass_context
def issue_close(ctx, number, repo_name, org, reason):
    """Close an issue.

    \b
    Example:
      sgh issue close 547 -r cap-automation
      sgh issue close 12 -r my-repo --reason not_planned
    """
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    client.patch(f"/repos/{full_name}/issues/{number}", json={"state": "closed", "state_reason": reason})
    console.print(f"[green]Closed issue #{number} ({reason})[/green]")


@issue.command("reopen")
@click.argument("number", type=int, metavar="ISSUE_NUMBER")
@click.option("--repo", "-r", "repo_name", default=None, help="Repo name (or owner/repo).")
@click.option("--org", "-o", default=None, help="Organization name.")
@click.pass_context
def issue_reopen(ctx, number, repo_name, org):
    """Reopen an issue."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    client.patch(f"/repos/{full_name}/issues/{number}", json={"state": "open"})
    console.print(f"[green]Reopened issue #{number}[/green]")


@issue.command("comment")
@click.argument("number", type=int, metavar="ISSUE_NUMBER")
@click.argument("body", metavar="COMMENT_TEXT")
@click.option("--repo", "-r", "repo_name", default=None, help="Repo name (or owner/repo).")
@click.option("--org", "-o", default=None, help="Organization name.")
@click.pass_context
def issue_comment(ctx, number, body, repo_name, org):
    """Comment on an issue.

    \b
    Example:
      sgh issue comment 547 "Fixed in latest release" -r cap-automation
    """
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    client.post(f"/repos/{full_name}/issues/{number}/comments", json={"body": body})
    console.print(f"[green]Commented on issue #{number}[/green]")


@issue.command("edit")
@click.argument("number", type=int, metavar="ISSUE_NUMBER")
@click.option("--repo", "-r", "repo_name", default=None, help="Repo name (or owner/repo).")
@click.option("--org", "-o", default=None, help="Organization name.")
@click.option("--title", "-t", default=None)
@click.option("--body", "-b", default=None)
@click.option("--assignee", multiple=True)
@click.option("--label", multiple=True)
@click.pass_context
def issue_edit(ctx, number, repo_name, org, title, body, assignee, label):
    """Edit an issue."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    payload = {}
    if title:
        payload["title"] = title
    if body:
        payload["body"] = body
    if assignee:
        payload["assignees"] = list(assignee)
    if label:
        payload["labels"] = list(label)
    if payload:
        client.patch(f"/repos/{full_name}/issues/{number}", json=payload)
        console.print(f"[green]Updated issue #{number}[/green]")


@issue.command("lock")
@click.argument("number", type=int, metavar="ISSUE_NUMBER")
@click.option("--repo", "-r", "repo_name", default=None, help="Repo name (or owner/repo).")
@click.option("--org", "-o", default=None, help="Organization name.")
@click.option("--reason", type=click.Choice(["off-topic", "too heated", "resolved", "spam"]), default=None)
@click.pass_context
def issue_lock(ctx, number, repo_name, org, reason):
    """Lock an issue."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    payload = {"lock_reason": reason} if reason else {}
    client.put(f"/repos/{full_name}/issues/{number}/lock", json=payload)
    console.print(f"[green]Locked issue #{number}[/green]")


@issue.command("pin")
@click.argument("number", type=int, metavar="ISSUE_NUMBER")
@click.option("--repo", "-r", "repo_name", default=None, help="Repo name (or owner/repo).")
@click.option("--org", "-o", default=None, help="Organization name.")
@click.pass_context
def issue_pin(ctx, number, repo_name, org):
    """Pin an issue (GraphQL)."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    i = client.get(f"/repos/{full_name}/issues/{number}")
    query = """
    mutation($id: ID!) {
      pinIssue(input: {issueId: $id}) { issue { number } }
    }
    """
    client.graphql(query, variables={"id": i["node_id"]})
    console.print(f"[green]Pinned issue #{number}[/green]")


@issue.command("transfer")
@click.argument("number", type=int, metavar="ISSUE_NUMBER")
@click.argument("target_repo", metavar="TARGET_REPO")
@click.option("--repo", "-r", "repo_name", default=None, help="Source repo name.")
@click.option("--org", "-o", default=None, help="Organization name.")
@click.pass_context
def issue_transfer(ctx, number, target_repo, repo_name, org):
    """Transfer an issue to another repo."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    i = client.get(f"/repos/{full_name}/issues/{number}")

    cfg = get_config()
    target_org = org or cfg.org
    target_full = f"{target_org}/{target_repo}" if "/" not in target_repo else target_repo
    target_data = client.get(f"/repos/{target_full}")

    query = """
    mutation($issueId: ID!, $repoId: ID!) {
      transferIssue(input: {issueId: $issueId, repositoryId: $repoId}) {
        issue { number url }
      }
    }
    """
    client.graphql(query, variables={"issueId": i["node_id"], "repoId": target_data["node_id"]})
    console.print(f"[green]Transferred issue #{number} to {target_full}[/green]")


@issue.command("delete")
@click.argument("number", type=int, metavar="ISSUE_NUMBER")
@click.option("--repo", "-r", "repo_name", default=None, help="Repo name (or owner/repo).")
@click.option("--org", "-o", default=None, help="Organization name.")
@click.option("--yes", is_flag=True, help="Skip confirmation.")
@click.pass_context
def issue_delete(ctx, number, repo_name, org, yes):
    """Delete an issue (GraphQL, admin only)."""
    full_name = _resolve_repo(org, repo_name)
    if not yes:
        click.confirm(f"Delete issue #{number} from {full_name}? Cannot be undone", abort=True)
    client = _client(ctx)
    i = client.get(f"/repos/{full_name}/issues/{number}")
    query = """
    mutation($id: ID!) {
      deleteIssue(input: {issueId: $id}) { repository { name } }
    }
    """
    client.graphql(query, variables={"id": i["node_id"]})
    console.print(f"[green]Deleted issue #{number}[/green]")
