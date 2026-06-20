"""sgh report / audit / compliance / drift / sync / bulk commands."""

import csv
import json
import sys
from io import StringIO
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.progress import track

from supergh.api.client import GitHubClient
from supergh.config import get_config

console = Console()


def _client(ctx) -> GitHubClient:
    return GitHubClient(debug=ctx.obj.get("debug", False))


def _get_org_repos(client, org, limit=200):
    repos = []
    for r in client.paginate(f"/orgs/{org}/repos", params={"per_page": 100, "sort": "pushed"}):
        repos.append(r)
        if len(repos) >= limit:
            break
    return repos


# --- Report ---

@click.group("report")
@click.pass_context
def report(ctx):
    """Generate org-wide reports."""


@report.command("repos")
@click.option("--org", "-o", default=None)
@click.option("--export", "export_path", default=None, help="Export to CSV/JSON file.")
@click.option("--limit", "-l", default=200)
@click.pass_context
def report_repos(ctx, org, export_path, limit):
    """Full repo report."""
    cfg = get_config()
    o = org or cfg.org
    client = _client(ctx)
    repos = _get_org_repos(client, o, limit)

    rows = []
    for r in repos:
        rows.append({
            "name": r["name"],
            "visibility": r["visibility"],
            "language": r.get("language") or "",
            "default_branch": r["default_branch"],
            "stars": r["stargazers_count"],
            "forks": r["forks_count"],
            "open_issues": r["open_issues_count"],
            "archived": r["archived"],
            "updated": r["updated_at"][:10],
            "url": r["html_url"],
        })

    if export_path:
        _export(rows, export_path)
    else:
        table = Table(title=f"Repo Report — {o} ({len(rows)} repos)")
        for col in ["name", "visibility", "language", "stars", "archived", "updated"]:
            table.add_column(col)
        for row in rows[:50]:
            table.add_row(str(row["name"]), row["visibility"], row["language"], str(row["stars"]), str(row["archived"]), row["updated"])
        console.print(table)
        if len(rows) > 50:
            console.print(f"[dim]Showing 50/{len(rows)}. Use --export to get all.[/dim]")


@report.command("prs")
@click.option("--org", "-o", default=None)
@click.option("--state", type=click.Choice(["open", "closed", "all"]), default="open")
@click.option("--export", "export_path", default=None)
@click.option("--limit", "-l", default=50, help="Max repos to scan.")
@click.pass_context
def report_prs(ctx, org, state, export_path, limit):
    """Open PRs across org."""
    cfg = get_config()
    o = org or cfg.org
    client = _client(ctx)
    repos = _get_org_repos(client, o, limit)

    rows = []
    for repo in track(repos, description="Scanning PRs...", console=console):
        try:
            prs = client.get(f"/repos/{repo['full_name']}/pulls", params={"state": state, "per_page": 100})
            for p in prs:
                rows.append({
                    "repo": repo["name"],
                    "number": p["number"],
                    "title": p["title"],
                    "author": p["user"]["login"],
                    "branch": p["head"]["ref"],
                    "created": p["created_at"][:10],
                    "updated": p["updated_at"][:10],
                    "url": p["html_url"],
                })
        except Exception:
            pass

    if export_path:
        _export(rows, export_path)
    else:
        table = Table(title=f"PRs ({state}) — {o}")
        table.add_column("Repo", style="cyan")
        table.add_column("#", justify="right")
        table.add_column("Title", max_width=40)
        table.add_column("Author", style="yellow")
        table.add_column("Created", style="dim")
        for row in rows[:50]:
            table.add_row(row["repo"], str(row["number"]), row["title"][:40], row["author"], row["created"])
        console.print(table)
        console.print(f"[dim]Total: {len(rows)} PRs[/dim]")


@report.command("secrets")
@click.option("--org", "-o", default=None)
@click.option("--export", "export_path", default=None)
@click.option("--limit", "-l", default=100)
@click.pass_context
def report_secrets(ctx, org, export_path, limit):
    """Audit which repos have which secrets configured."""
    cfg = get_config()
    o = org or cfg.org
    client = _client(ctx)
    repos = _get_org_repos(client, o, limit)

    rows = []
    for repo in track(repos, description="Scanning secrets...", console=console):
        try:
            data = client.get(f"/repos/{repo['full_name']}/actions/secrets")
            for s in data.get("secrets", []):
                rows.append({"repo": repo["name"], "secret": s["name"], "updated": s.get("updated_at", "")[:10]})
        except Exception:
            pass

    if export_path:
        _export(rows, export_path)
    else:
        table = Table(title=f"Secrets Audit — {o}")
        table.add_column("Repo", style="cyan")
        table.add_column("Secret", style="yellow")
        table.add_column("Updated", style="dim")
        for row in rows[:50]:
            table.add_row(row["repo"], row["secret"], row["updated"])
        console.print(table)
        console.print(f"[dim]Total: {len(rows)} secrets across {len(set(r['repo'] for r in rows))} repos[/dim]")


# --- Audit ---

@click.group("audit")
@click.pass_context
def audit(ctx):
    """Security and access auditing."""


@audit.command("permissions")
@click.option("--org", "-o", default=None)
@click.option("--limit", "-l", default=50)
@click.pass_context
def audit_permissions(ctx, org, limit):
    """Repo permission audit."""
    cfg = get_config()
    o = org or cfg.org
    client = _client(ctx)
    repos = _get_org_repos(client, o, limit)

    table = Table(title=f"Permission Audit — {o}")
    table.add_column("Repo", style="cyan")
    table.add_column("Visibility")
    table.add_column("Admin Teams")
    table.add_column("Push Teams")

    for repo in track(repos, description="Auditing...", console=console):
        try:
            teams = client.get(f"/repos/{repo['full_name']}/teams")
            admin_teams = [t["name"] for t in teams if t.get("permission") == "admin"]
            push_teams = [t["name"] for t in teams if t.get("permission") in ("push", "maintain")]
            table.add_row(repo["name"], repo["visibility"], ", ".join(admin_teams) or "-", ", ".join(push_teams) or "-")
        except Exception:
            pass

    console.print(table)


@audit.command("access")
@click.argument("repo_name")
@click.option("--org", "-o", default=None)
@click.pass_context
def audit_access(ctx, repo_name, org):
    """Who has access to a repo."""
    cfg = get_config()
    o = org or cfg.org
    full_name = f"{o}/{repo_name}" if o and "/" not in repo_name else repo_name
    client = _client(ctx)

    collabs = list(client.paginate(f"/repos/{full_name}/collaborators"))
    table = Table(title=f"Access — {full_name}")
    table.add_column("User", style="cyan")
    table.add_column("Permission")
    table.add_column("Type", style="dim")

    for c in collabs:
        perms = c.get("permissions", {})
        level = "admin" if perms.get("admin") else "write" if perms.get("push") else "read"
        table.add_row(c["login"], level, c.get("type", ""))
    console.print(table)


# --- Compliance ---

@click.group("compliance")
@click.pass_context
def compliance(ctx):
    """Branch protection and policy checks."""


@compliance.command("check")
@click.option("--org", "-o", default=None)
@click.option("--limit", "-l", default=50)
@click.pass_context
def compliance_check(ctx, org, limit):
    """Branch protection rules across all repos."""
    cfg = get_config()
    o = org or cfg.org
    client = _client(ctx)
    repos = _get_org_repos(client, o, limit)

    table = Table(title=f"Branch Protection — {o}")
    table.add_column("Repo", style="cyan")
    table.add_column("Branch")
    table.add_column("Protected")
    table.add_column("Reviews Required")
    table.add_column("Status Checks")

    for repo in track(repos, description="Checking...", console=console):
        branch = repo["default_branch"]
        try:
            bp = client.get(f"/repos/{repo['full_name']}/branches/{branch}/protection")
            reviews = bp.get("required_pull_request_reviews", {})
            review_count = reviews.get("required_approving_review_count", 0) if reviews else 0
            status_checks = "Yes" if bp.get("required_status_checks") else "No"
            table.add_row(repo["name"], branch, "[green]Yes[/green]", str(review_count), status_checks)
        except Exception:
            table.add_row(repo["name"], branch, "[red]No[/red]", "-", "-")

    console.print(table)


# --- Sync ---

@click.group("sync")
@click.pass_context
def sync(ctx):
    """Bulk sync operations across repos."""


@sync.command("labels")
@click.argument("source_repo")
@click.option("--org", "-o", default=None)
@click.option("--targets", required=True, help="Comma-separated target repo names.")
@click.pass_context
def sync_labels(ctx, source_repo, org, targets):
    """Sync labels from source to target repos."""
    cfg = get_config()
    o = org or cfg.org
    source = f"{o}/{source_repo}" if o and "/" not in source_repo else source_repo
    client = _client(ctx)

    labels = list(client.paginate(f"/repos/{source}/labels"))
    target_list = [t.strip() for t in targets.split(",")]

    for target_name in target_list:
        target = f"{o}/{target_name}" if o else target_name
        synced = 0
        for l in labels:
            try:
                client.post(f"/repos/{target}/labels", json={"name": l["name"], "color": l["color"], "description": l.get("description", "")})
                synced += 1
            except Exception:
                pass
        console.print(f"  [green]{target}: {synced}/{len(labels)} labels synced[/green]")


@sync.command("variables")
@click.option("--org", "-o", default=None)
@click.option("--source", required=True, help="Source repo name.")
@click.option("--targets", required=True, help="Comma-separated target repos.")
@click.pass_context
def sync_variables(ctx, org, source, targets):
    """Bulk copy variables across repos."""
    cfg = get_config()
    o = org or cfg.org
    source_full = f"{o}/{source}" if o and "/" not in source else source
    client = _client(ctx)

    data = client.get(f"/repos/{source_full}/actions/variables")
    variables = data.get("variables", [])

    target_list = [t.strip() for t in targets.split(",")]
    for target_name in target_list:
        target = f"{o}/{target_name}" if o else target_name
        for v in variables:
            try:
                client.post(f"/repos/{target}/actions/variables", json={"name": v["name"], "value": v["value"]})
            except Exception:
                try:
                    client.patch(f"/repos/{target}/actions/variables/{v['name']}", json={"name": v["name"], "value": v["value"]})
                except Exception:
                    pass
        console.print(f"  [green]{target}: {len(variables)} variables synced[/green]")


# --- Bulk ---

@click.group("bulk")
@click.pass_context
def bulk(ctx):
    """Bulk operations across repos."""


@bulk.command("issue")
@click.option("--org", "-o", default=None)
@click.option("--repos", required=True, help="Comma-separated repos.")
@click.option("--title", "-t", required=True)
@click.option("--body", "-b", default="")
@click.option("--label", multiple=True)
@click.pass_context
def bulk_issue(ctx, org, repos, title, body, label):
    """File same issue across multiple repos."""
    cfg = get_config()
    o = org or cfg.org
    client = _client(ctx)

    repo_list = [r.strip() for r in repos.split(",")]
    payload = {"title": title, "body": body}
    if label:
        payload["labels"] = list(label)

    for repo_name in repo_list:
        full_name = f"{o}/{repo_name}" if o else repo_name
        try:
            i = client.post(f"/repos/{full_name}/issues", json=payload)
            console.print(f"  [green]{full_name} #{i['number']}[/green]")
        except Exception as e:
            console.print(f"  [red]{full_name}: {e}[/red]")


@bulk.command("pr")
@click.option("--org", "-o", default=None)
@click.option("--repos", required=True, help="Comma-separated repos.")
@click.option("--title", "-t", required=True)
@click.option("--body", "-b", default="")
@click.option("--head", required=True)
@click.option("--base", default="main")
@click.pass_context
def bulk_pr(ctx, org, repos, title, body, head, base):
    """Open same PR across multiple repos."""
    cfg = get_config()
    o = org or cfg.org
    client = _client(ctx)

    repo_list = [r.strip() for r in repos.split(",")]
    for repo_name in repo_list:
        full_name = f"{o}/{repo_name}" if o else repo_name
        try:
            p = client.post(f"/repos/{full_name}/pulls", json={"title": title, "body": body, "head": head, "base": base})
            console.print(f"  [green]{full_name} PR #{p['number']}[/green]")
        except Exception as e:
            console.print(f"  [red]{full_name}: {e}[/red]")


# --- Drift ---

@click.group("drift")
@click.pass_context
def drift(ctx):
    """Detect configuration drift across repos."""


@drift.command("workflows")
@click.argument("workflow_file", default=".github/workflows/ci.yml")
@click.option("--org", "-o", default=None)
@click.option("--limit", "-l", default=50)
@click.pass_context
def drift_workflows(ctx, workflow_file, org, limit):
    """Detect workflow file differences across repos."""
    cfg = get_config()
    o = org or cfg.org
    client = _client(ctx)
    repos = _get_org_repos(client, o, limit)

    import hashlib
    hashes = {}

    for repo in track(repos, description="Checking workflows...", console=console):
        try:
            import base64
            data = client.get(f"/repos/{repo['full_name']}/contents/{workflow_file}")
            content = base64.b64decode(data["content"]).decode()
            h = hashlib.sha256(content.encode()).hexdigest()[:12]
            hashes.setdefault(h, []).append(repo["name"])
        except Exception:
            hashes.setdefault("MISSING", []).append(repo["name"])

    console.print(f"\n[bold]Workflow Drift: {workflow_file}[/bold]")
    for h, repos_list in sorted(hashes.items(), key=lambda x: len(x[1]), reverse=True):
        style = "green" if len(repos_list) > len(hashes) / 2 else "yellow" if h != "MISSING" else "red"
        console.print(f"  [{style}]{h}: {len(repos_list)} repos[/{style}] — {', '.join(repos_list[:5])}{'...' if len(repos_list) > 5 else ''}")


# --- Export helper ---

def _export(rows, path):
    """Export rows to CSV or JSON based on file extension."""
    p = Path(path)
    if p.suffix == ".json":
        p.write_text(json.dumps(rows, indent=2))
    elif p.suffix == ".csv":
        if not rows:
            return
        with open(p, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
    else:
        p.write_text(json.dumps(rows, indent=2))
    console.print(f"[green]Exported {len(rows)} rows to {p}[/green]")
