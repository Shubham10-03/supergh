"""sgh pr — pull request commands."""

import json
import subprocess

import click
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax

from supergh.api.client import GitHubClient
from supergh.config import get_config

console = Console()


def _client(ctx) -> GitHubClient:
    return GitHubClient(debug=ctx.obj.get("debug", False))


def _resolve_repo(org, repo_name):
    """Resolve full repo name, auto-detect from git remote if not provided."""
    if repo_name:
        cfg = get_config()
        o = org or cfg.org
        return f"{o}/{repo_name}" if o and "/" not in repo_name else repo_name
    # Auto-detect from current git repo
    try:
        result = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True, check=True)
        url = result.stdout.strip()
        # Handle https://github.com/org/repo.git or git@github.com:org/repo.git
        if "github.com" in url:
            parts = url.replace(".git", "").split("github.com")[-1]
            return parts.lstrip(":/").strip()
    except Exception:
        pass
    raise click.UsageError("Could not detect repo. Use --repo or run from inside a git repo.")


@click.group("pr")
@click.pass_context
def pr(ctx):
    """Manage pull requests."""


@pr.command("list")
@click.option("--repo", "-r", "repo_name", default=None, help="Repo name or owner/repo.")
@click.option("--org", "-o", default=None)
@click.option("--state", type=click.Choice(["open", "closed", "all"]), default="open")
@click.option("--author", default=None)
@click.option("--label", default=None)
@click.option("--base", default=None, help="Filter by base branch.")
@click.option("--limit", "-l", default=30)
@click.option("--output", "output_fmt", type=click.Choice(["table", "json", "csv"]), default="table", help="Output format.")
@click.option("--export", "export_path", default=None, help="Export to file (.csv, .json, .xlsx, .md).")
@click.pass_context
def pr_list(ctx, repo_name, org, state, author, label, base, limit, output_fmt, export_path):
    """List pull requests."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)

    params = {"state": state, "per_page": min(limit, 100)}
    if base:
        params["base"] = base

    prs = []
    for p in client.paginate(f"/repos/{full_name}/pulls", params=params):
        if author and p["user"]["login"] != author:
            continue
        if label and not any(l["name"] == label for l in p.get("labels", [])):
            continue
        prs.append(p)
        if len(prs) >= limit:
            break

    rows = [{"number": p["number"], "title": p["title"], "author": p["user"]["login"], "state": p["state"], "branch": p["head"]["ref"], "base": p["base"]["ref"], "updated": p["updated_at"][:10], "url": p["html_url"]} for p in prs]

    if export_path:
        from supergh.export import export_data
        export_data(rows, export_path)
        return

    if output_fmt != "table":
        from supergh.export import format_for_output
        click.echo(format_for_output(rows, output_fmt))
        return

    table = Table(title=f"Pull Requests — {full_name} ({state})")
    table.add_column("#", style="bold", justify="right")
    table.add_column("Title", style="cyan", max_width=60)
    table.add_column("Author", style="yellow")
    table.add_column("Branch", style="dim")
    table.add_column("Updated", style="dim")

    for p in prs:
        table.add_row(
            str(p["number"]),
            p["title"],
            p["user"]["login"],
            p["head"]["ref"],
            p["updated_at"][:10],
        )
    console.print(table)


@pr.command("view")
@click.argument("number", type=int, metavar="PR_NUMBER")
@click.option("--repo", "-r", "repo_name", default=None, help="Repo name (or owner/repo).")
@click.option("--org", "-o", default=None, help="Organization name.")
@click.pass_context
def pr_view(ctx, number, repo_name, org):
    """View pull request details.

    \b
    Example:
      sgh pr view 42 -r ci-cd.automation
    """
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    p = client.get(f"/repos/{full_name}/pulls/{number}")

    console.print(f"\n[bold cyan]#{p['number']} {p['title']}[/bold cyan]")
    console.print(f"  State:      {p['state']} {'(merged)' if p.get('merged') else ''}")
    console.print(f"  Author:     {p['user']['login']}")
    console.print(f"  Branch:     {p['head']['ref']} -> {p['base']['ref']}")
    console.print(f"  Reviewers:  {', '.join(r['login'] for r in p.get('requested_reviewers', [])) or 'None'}")
    console.print(f"  Labels:     {', '.join(l['name'] for l in p.get('labels', [])) or 'None'}")
    console.print(f"  Created:    {p['created_at'][:10]}")
    console.print(f"  Updated:    {p['updated_at'][:10]}")
    console.print(f"  Commits:    {p.get('commits', 'N/A')}")
    console.print(f"  Changed:    +{p.get('additions', 0)} -{p.get('deletions', 0)} in {p.get('changed_files', 0)} files")
    console.print(f"  URL:        {p['html_url']}")
    if p.get("body"):
        console.print(f"\n[dim]--- Body ---[/dim]")
        console.print(p["body"][:500])


@pr.command("create")
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.option("--title", "-t", required=True)
@click.option("--body", "-b", default="")
@click.option("--base", default=None, help="Base branch (default: repo default).")
@click.option("--head", required=True, help="Head branch.")
@click.option("--draft", is_flag=True)
@click.option("--reviewer", multiple=True, help="Reviewers to request.")
@click.option("--label", multiple=True)
@click.pass_context
def pr_create(ctx, repo_name, org, title, body, base, head, draft, reviewer, label):
    """Create a pull request."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)

    if not base:
        repo_data = client.get(f"/repos/{full_name}")
        base = repo_data["default_branch"]

    payload = {"title": title, "body": body, "head": head, "base": base, "draft": draft}
    p = client.post(f"/repos/{full_name}/pulls", json=payload)

    if reviewer:
        client.post(f"/repos/{full_name}/pulls/{p['number']}/requested_reviewers", json={"reviewers": list(reviewer)})
    if label:
        client.post(f"/repos/{full_name}/issues/{p['number']}/labels", json={"labels": list(label)})

    console.print(f"[green]Created PR #{p['number']}: {p['title']}[/green]")
    console.print(f"  {p['html_url']}")


@pr.command("merge")
@click.argument("number", type=int, metavar="PR_NUMBER")
@click.option("--repo", "-r", "repo_name", default=None, help="Repo name (or owner/repo).")
@click.option("--org", "-o", default=None, help="Organization name.")
@click.option("--method", type=click.Choice(["merge", "squash", "rebase"]), default="squash")
@click.option("--delete-branch", is_flag=True, help="Delete head branch after merge.")
@click.pass_context
def pr_merge(ctx, number, repo_name, org, method, delete_branch):
    """Merge a pull request."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    client.put(f"/repos/{full_name}/pulls/{number}/merge", json={"merge_method": method})
    console.print(f"[green]Merged PR #{number} ({method})[/green]")

    if delete_branch:
        p = client.get(f"/repos/{full_name}/pulls/{number}")
        branch = p["head"]["ref"]
        try:
            client.delete(f"/repos/{full_name}/git/refs/heads/{branch}")
            console.print(f"[dim]Deleted branch {branch}[/dim]")
        except Exception:
            pass


@pr.command("close")
@click.argument("number", type=int, metavar="PR_NUMBER")
@click.option("--repo", "-r", "repo_name", default=None, help="Repo name (or owner/repo).")
@click.option("--org", "-o", default=None, help="Organization name.")
@click.pass_context
def pr_close(ctx, number, repo_name, org):
    """Close a pull request."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    client.patch(f"/repos/{full_name}/pulls/{number}", json={"state": "closed"})
    console.print(f"[green]Closed PR #{number}[/green]")


@pr.command("reopen")
@click.argument("number", type=int, metavar="PR_NUMBER")
@click.option("--repo", "-r", "repo_name", default=None, help="Repo name (or owner/repo).")
@click.option("--org", "-o", default=None, help="Organization name.")
@click.pass_context
def pr_reopen(ctx, number, repo_name, org):
    """Reopen a pull request."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    client.patch(f"/repos/{full_name}/pulls/{number}", json={"state": "open"})
    console.print(f"[green]Reopened PR #{number}[/green]")


@pr.command("checkout")
@click.argument("number", type=int, metavar="PR_NUMBER")
@click.option("--repo", "-r", "repo_name", default=None, help="Repo name (or owner/repo).")
@click.option("--org", "-o", default=None, help="Organization name.")
@click.pass_context
def pr_checkout(ctx, number, repo_name, org):
    """Checkout a PR branch locally."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    p = client.get(f"/repos/{full_name}/pulls/{number}")
    branch = p["head"]["ref"]
    subprocess.run(["git", "fetch", "origin", f"pull/{number}/head:{branch}"], check=True)
    subprocess.run(["git", "checkout", branch], check=True)
    console.print(f"[green]Checked out PR #{number} on branch {branch}[/green]")


@pr.command("diff")
@click.argument("number", type=int, metavar="PR_NUMBER")
@click.option("--repo", "-r", "repo_name", default=None, help="Repo name (or owner/repo).")
@click.option("--org", "-o", default=None, help="Organization name.")
@click.pass_context
def pr_diff(ctx, number, repo_name, org):
    """View PR diff."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    resp = client._session
    # Need raw diff
    from supergh.auth.middleware import get_auth_provider
    token = get_auth_provider().get_token()
    import requests
    r = requests.get(
        f"https://api.github.com/repos/{full_name}/pulls/{number}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.diff"},
        timeout=30,
    )
    r.raise_for_status()
    syntax = Syntax(r.text[:5000], "diff", theme="monokai")
    console.print(syntax)
    if len(r.text) > 5000:
        console.print(f"[dim]... truncated ({len(r.text)} chars total)[/dim]")


@pr.command("review")
@click.argument("number", type=int, metavar="PR_NUMBER")
@click.option("--repo", "-r", "repo_name", default=None, help="Repo name (or owner/repo).")
@click.option("--org", "-o", default=None, help="Organization name.")
@click.option("--approve", is_flag=True)
@click.option("--request-changes", is_flag=True)
@click.option("--comment", "-c", is_flag=True)
@click.option("--body", "-b", default="")
@click.pass_context
def pr_review(ctx, number, repo_name, org, approve, request_changes, comment, body):
    """Submit a PR review."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)

    if approve:
        event = "APPROVE"
    elif request_changes:
        event = "REQUEST_CHANGES"
    else:
        event = "COMMENT"

    payload = {"event": event}
    if body:
        payload["body"] = body
    client.post(f"/repos/{full_name}/pulls/{number}/reviews", json=payload)
    console.print(f"[green]Submitted {event} review on PR #{number}[/green]")


@pr.command("comment")
@click.argument("number", type=int, metavar="PR_NUMBER")
@click.argument("body", metavar="COMMENT_TEXT")
@click.option("--repo", "-r", "repo_name", default=None, help="Repo name (or owner/repo).")
@click.option("--org", "-o", default=None, help="Organization name.")
@click.pass_context
def pr_comment(ctx, number, body, repo_name, org):
    """Comment on a pull request."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    client.post(f"/repos/{full_name}/issues/{number}/comments", json={"body": body})
    console.print(f"[green]Commented on PR #{number}[/green]")


@pr.command("checks")
@click.argument("number", type=int, metavar="PR_NUMBER")
@click.option("--repo", "-r", "repo_name", default=None, help="Repo name (or owner/repo).")
@click.option("--org", "-o", default=None, help="Organization name.")
@click.pass_context
def pr_checks(ctx, number, repo_name, org):
    """View PR check statuses."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    p = client.get(f"/repos/{full_name}/pulls/{number}")
    sha = p["head"]["sha"]

    checks = client.get(f"/repos/{full_name}/commits/{sha}/check-runs")
    table = Table(title=f"Checks for PR #{number}")
    table.add_column("Name", style="cyan")
    table.add_column("Status")
    table.add_column("Conclusion")
    table.add_column("Duration", style="dim")

    for check in checks.get("check_runs", []):
        conclusion = check.get("conclusion") or ""
        style = "green" if conclusion == "success" else "red" if conclusion == "failure" else "yellow"
        table.add_row(
            check["name"],
            check["status"],
            f"[{style}]{conclusion}[/{style}]",
            check.get("completed_at", "")[:19] if check.get("completed_at") else "running...",
        )
    console.print(table)


@pr.command("ready")
@click.argument("number", type=int, metavar="PR_NUMBER")
@click.option("--repo", "-r", "repo_name", default=None, help="Repo name (or owner/repo).")
@click.option("--org", "-o", default=None, help="Organization name.")
@click.pass_context
def pr_ready(ctx, number, repo_name, org):
    """Mark a draft PR as ready for review."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    # GraphQL needed for this
    query = """
    mutation($id: ID!) {
      markPullRequestReadyForReview(input: {pullRequestId: $id}) {
        pullRequest { number }
      }
    }
    """
    p = client.get(f"/repos/{full_name}/pulls/{number}")
    client.graphql(query, variables={"id": p["node_id"]})
    console.print(f"[green]PR #{number} marked as ready for review[/green]")


@pr.command("edit")
@click.argument("number", type=int, metavar="PR_NUMBER")
@click.option("--repo", "-r", "repo_name", default=None, help="Repo name (or owner/repo).")
@click.option("--org", "-o", default=None, help="Organization name.")
@click.option("--title", "-t", default=None)
@click.option("--body", "-b", default=None)
@click.option("--base", default=None)
@click.pass_context
def pr_edit(ctx, number, repo_name, org, title, body, base):
    """Edit a pull request."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    payload = {}
    if title:
        payload["title"] = title
    if body:
        payload["body"] = body
    if base:
        payload["base"] = base
    if payload:
        client.patch(f"/repos/{full_name}/pulls/{number}", json=payload)
        console.print(f"[green]Updated PR #{number}[/green]")


@pr.command("lock")
@click.argument("number", type=int, metavar="PR_NUMBER")
@click.option("--repo", "-r", "repo_name", default=None, help="Repo name (or owner/repo).")
@click.option("--org", "-o", default=None, help="Organization name.")
@click.option("--reason", type=click.Choice(["off-topic", "too heated", "resolved", "spam"]), default=None)
@click.pass_context
def pr_lock(ctx, number, repo_name, org, reason):
    """Lock a pull request conversation."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    payload = {}
    if reason:
        payload["lock_reason"] = reason
    client.put(f"/repos/{full_name}/issues/{number}/lock", json=payload)
    console.print(f"[green]Locked PR #{number}[/green]")
