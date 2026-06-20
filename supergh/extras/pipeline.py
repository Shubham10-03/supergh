"""sgh pipeline — cross-repo pipeline intelligence commands."""

import json
from datetime import datetime

import click
from rich.console import Console
from rich.table import Table
from rich.progress import track

from supergh.api.client import GitHubClient
from supergh.config import get_config

console = Console()


def _client(ctx) -> GitHubClient:
    return GitHubClient(debug=ctx.obj.get("debug", False))


def _get_org_repos(client, org, limit=100):
    """Fetch repos from org."""
    repos = []
    for r in client.paginate(f"/orgs/{org}/repos", params={"per_page": 100, "sort": "pushed"}):
        repos.append(r)
        if len(repos) >= limit:
            break
    return repos


@click.group("pipeline")
@click.pass_context
def pipeline(ctx):
    """Cross-repo pipeline intelligence."""


@pipeline.command("status")
@click.option("--org", "-o", default=None)
@click.option("--limit", "-l", default=20, help="Max repos to check.")
@click.pass_context
def pipeline_status(ctx, org, limit):
    """Live pipeline health across all repos."""
    cfg = get_config()
    o = org or cfg.org
    client = _client(ctx)
    repos = _get_org_repos(client, o, limit)

    table = Table(title=f"Pipeline Status — {o}")
    table.add_column("Repo", style="cyan")
    table.add_column("Workflow", style="dim")
    table.add_column("Status")
    table.add_column("Conclusion")
    table.add_column("Branch", style="dim")
    table.add_column("Duration", style="dim")

    for repo in track(repos, description="Checking pipelines...", console=console):
        try:
            data = client.get(f"/repos/{repo['full_name']}/actions/runs", params={"per_page": 1})
            runs = data.get("workflow_runs", [])
            if not runs:
                continue
            r = runs[0]
            conclusion = r.get("conclusion") or ""
            style = "green" if conclusion == "success" else "red" if conclusion == "failure" else "yellow"
            duration = ""
            if r.get("run_started_at") and r.get("updated_at"):
                start = datetime.fromisoformat(r["run_started_at"].replace("Z", "+00:00"))
                end = datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00"))
                secs = int((end - start).total_seconds())
                duration = f"{secs // 60}m {secs % 60}s"
            table.add_row(repo["name"], r["name"], r["status"], f"[{style}]{conclusion or 'pending'}[/{style}]", r.get("head_branch", ""), duration)
        except Exception:
            pass

    console.print(table)


@pipeline.command("history")
@click.argument("repo_name")
@click.option("--org", "-o", default=None)
@click.option("--workflow", "-w", default=None, help="Workflow ID or filename.")
@click.option("--limit", "-l", default=20)
@click.pass_context
def pipeline_history(ctx, repo_name, org, workflow, limit):
    """Run history with duration trends."""
    cfg = get_config()
    o = org or cfg.org
    full_name = f"{o}/{repo_name}" if o and "/" not in repo_name else repo_name
    client = _client(ctx)

    path = f"/repos/{full_name}/actions/workflows/{workflow}/runs" if workflow else f"/repos/{full_name}/actions/runs"
    data = client.get(path, params={"per_page": limit})

    table = Table(title=f"Pipeline History — {full_name}")
    table.add_column("#", justify="right")
    table.add_column("Workflow", style="cyan")
    table.add_column("Conclusion")
    table.add_column("Duration", style="dim")
    table.add_column("Date", style="dim")

    durations = []
    for r in data.get("workflow_runs", [])[:limit]:
        conclusion = r.get("conclusion") or ""
        style = "green" if conclusion == "success" else "red" if conclusion == "failure" else "yellow"
        duration = ""
        secs = 0
        if r.get("run_started_at") and r.get("updated_at"):
            start = datetime.fromisoformat(r["run_started_at"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00"))
            secs = int((end - start).total_seconds())
            duration = f"{secs // 60}m {secs % 60}s"
            durations.append(secs)
        table.add_row(str(r["run_number"]), r["name"], f"[{style}]{conclusion}[/{style}]", duration, (r.get("run_started_at") or "")[:10])

    console.print(table)
    if durations:
        avg = sum(durations) // len(durations)
        console.print(f"\n  Avg duration: {avg // 60}m {avg % 60}s | Min: {min(durations) // 60}m | Max: {max(durations) // 60}m")


@pipeline.command("trigger")
@click.option("--org", "-o", default=None)
@click.option("--repos", required=True, help="Comma-separated repo names.")
@click.option("--workflow", "-w", required=True, help="Workflow ID or filename.")
@click.option("--ref", default="main")
@click.pass_context
def pipeline_trigger(ctx, org, repos, workflow, ref):
    """Trigger workflows across multiple repos."""
    cfg = get_config()
    o = org or cfg.org
    client = _client(ctx)

    repo_list = [r.strip() for r in repos.split(",")]
    for repo_name in repo_list:
        full_name = f"{o}/{repo_name}"
        try:
            client.post(f"/repos/{full_name}/actions/workflows/{workflow}/dispatches", json={"ref": ref})
            console.print(f"  [green]Triggered {full_name}[/green]")
        except Exception as e:
            console.print(f"  [red]Failed {full_name}: {e}[/red]")


@pipeline.command("compare")
@click.argument("repo_name")
@click.option("--org", "-o", default=None)
@click.option("--workflow", "-w", default=None)
@click.option("--limit", "-l", default=30)
@click.pass_context
def pipeline_compare(ctx, repo_name, org, workflow, limit):
    """Compare run durations, spot regressions."""
    cfg = get_config()
    o = org or cfg.org
    full_name = f"{o}/{repo_name}" if o and "/" not in repo_name else repo_name
    client = _client(ctx)

    path = f"/repos/{full_name}/actions/workflows/{workflow}/runs" if workflow else f"/repos/{full_name}/actions/runs"
    data = client.get(path, params={"per_page": limit, "status": "completed"})

    runs = data.get("workflow_runs", [])
    durations = []
    for r in runs:
        if r.get("run_started_at") and r.get("updated_at"):
            start = datetime.fromisoformat(r["run_started_at"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00"))
            durations.append({"run": r["run_number"], "secs": int((end - start).total_seconds()), "conclusion": r.get("conclusion")})

    if not durations:
        console.print("[yellow]No completed runs found.[/yellow]")
        return

    avg = sum(d["secs"] for d in durations) // len(durations)
    console.print(f"\n[bold]Duration Analysis — {full_name}[/bold]")
    console.print(f"  Avg: {avg // 60}m {avg % 60}s")
    console.print(f"  Min: {min(d['secs'] for d in durations) // 60}m")
    console.print(f"  Max: {max(d['secs'] for d in durations) // 60}m")

    # Flag regressions (>50% above average)
    regressions = [d for d in durations if d["secs"] > avg * 1.5]
    if regressions:
        console.print(f"\n  [red]Regressions ({len(regressions)} runs >50% above avg):[/red]")
        for d in regressions[:5]:
            console.print(f"    Run #{d['run']}: {d['secs'] // 60}m {d['secs'] % 60}s ({d['conclusion']})")


@pipeline.command("flaky")
@click.argument("repo_name")
@click.option("--org", "-o", default=None)
@click.option("--limit", "-l", default=50, help="Runs to analyze.")
@click.pass_context
def pipeline_flaky(ctx, repo_name, org, limit):
    """Detect flaky jobs by failure pattern analysis."""
    cfg = get_config()
    o = org or cfg.org
    full_name = f"{o}/{repo_name}" if o and "/" not in repo_name else repo_name
    client = _client(ctx)

    data = client.get(f"/repos/{full_name}/actions/runs", params={"per_page": limit, "status": "completed"})
    runs = data.get("workflow_runs", [])

    job_stats = {}  # job_name -> {"pass": 0, "fail": 0}

    for r in track(runs[:limit], description="Analyzing runs...", console=console):
        try:
            jobs = client.get(f"/repos/{full_name}/actions/runs/{r['id']}/jobs")
            for j in jobs.get("jobs", []):
                name = j["name"]
                if name not in job_stats:
                    job_stats[name] = {"pass": 0, "fail": 0}
                if j.get("conclusion") == "success":
                    job_stats[name]["pass"] += 1
                elif j.get("conclusion") == "failure":
                    job_stats[name]["fail"] += 1
        except Exception:
            pass

    # Flaky = fails sometimes but not always (10-90% failure rate)
    flaky_jobs = []
    for name, stats in job_stats.items():
        total = stats["pass"] + stats["fail"]
        if total < 3:
            continue
        fail_rate = stats["fail"] / total
        if 0.1 <= fail_rate <= 0.9:
            flaky_jobs.append((name, fail_rate, stats))

    flaky_jobs.sort(key=lambda x: x[1], reverse=True)

    if not flaky_jobs:
        console.print("[green]No flaky jobs detected.[/green]")
        return

    table = Table(title=f"Flaky Jobs — {full_name}")
    table.add_column("Job", style="cyan")
    table.add_column("Fail Rate", style="red")
    table.add_column("Pass", style="green", justify="right")
    table.add_column("Fail", style="red", justify="right")

    for name, rate, stats in flaky_jobs:
        table.add_row(name, f"{rate:.0%}", str(stats["pass"]), str(stats["fail"]))
    console.print(table)
