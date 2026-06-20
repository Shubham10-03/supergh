"""sgh workflow / sgh run — GitHub Actions commands."""

import json
import time

import click
from rich.console import Console
from rich.table import Table
from rich.live import Live

from supergh.api.client import GitHubClient
from supergh.commands.pr import _resolve_repo

console = Console()


def _client(ctx) -> GitHubClient:
    return GitHubClient(debug=ctx.obj.get("debug", False))


# --- Workflow commands ---

@click.group("workflow")
@click.pass_context
def workflow(ctx):
    """Manage GitHub Actions workflows."""


@workflow.command("list")
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.pass_context
def workflow_list(ctx, repo_name, org):
    """List workflows."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    data = client.get(f"/repos/{full_name}/actions/workflows")

    table = Table(title=f"Workflows — {full_name}")
    table.add_column("ID", justify="right")
    table.add_column("Name", style="cyan")
    table.add_column("State", style="yellow")
    table.add_column("File", style="dim")

    for w in data.get("workflows", []):
        state_style = "green" if w["state"] == "active" else "red"
        table.add_row(str(w["id"]), w["name"], f"[{state_style}]{w['state']}[/{state_style}]", w["path"])
    console.print(table)


@workflow.command("view")
@click.argument("workflow_id")
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.pass_context
def workflow_view(ctx, workflow_id, repo_name, org):
    """View workflow details."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    w = client.get(f"/repos/{full_name}/actions/workflows/{workflow_id}")
    console.print(f"\n[bold cyan]{w['name']}[/bold cyan]")
    console.print(f"  ID:      {w['id']}")
    console.print(f"  State:   {w['state']}")
    console.print(f"  File:    {w['path']}")
    console.print(f"  URL:     {w['html_url']}")


@workflow.command("run")
@click.argument("workflow_id")
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.option("--ref", default="main", help="Branch or tag to run on.")
@click.option("--input", "-i", "inputs", multiple=True, help="Inputs as key=value.")
@click.pass_context
def workflow_run(ctx, workflow_id, repo_name, org, ref, inputs):
    """Trigger a workflow run."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    input_dict = {}
    for inp in inputs:
        k, v = inp.split("=", 1)
        input_dict[k] = v

    payload = {"ref": ref}
    if input_dict:
        payload["inputs"] = input_dict

    client.post(f"/repos/{full_name}/actions/workflows/{workflow_id}/dispatches", json=payload)
    console.print(f"[green]Triggered workflow {workflow_id} on {ref}[/green]")


@workflow.command("enable")
@click.argument("workflow_id")
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.pass_context
def workflow_enable(ctx, workflow_id, repo_name, org):
    """Enable a workflow."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    client.put(f"/repos/{full_name}/actions/workflows/{workflow_id}/enable")
    console.print(f"[green]Enabled workflow {workflow_id}[/green]")


@workflow.command("disable")
@click.argument("workflow_id")
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.pass_context
def workflow_disable(ctx, workflow_id, repo_name, org):
    """Disable a workflow."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    client.put(f"/repos/{full_name}/actions/workflows/{workflow_id}/disable")
    console.print(f"[green]Disabled workflow {workflow_id}[/green]")


# --- Run commands ---

@click.group("run")
@click.pass_context
def run(ctx):
    """Manage workflow runs."""


@run.command("list")
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.option("--workflow", "-w", default=None, help="Filter by workflow ID or filename.")
@click.option("--branch", default=None)
@click.option("--status", type=click.Choice(["completed", "action_required", "cancelled", "failure", "neutral", "skipped", "stale", "success", "timed_out", "in_progress", "queued", "requested", "waiting"]), default=None)
@click.option("--limit", "-l", default=20)
@click.option("--output", "output_fmt", type=click.Choice(["table", "json", "csv"]), default="table", help="Output format.")
@click.option("--export", "export_path", default=None, help="Export to file (.csv, .json, .xlsx, .md).")
@click.pass_context
def run_list(ctx, repo_name, org, workflow, branch, status, limit, output_fmt, export_path):
    """List workflow runs."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)

    params = {"per_page": min(limit, 100)}
    if branch:
        params["branch"] = branch
    if status:
        params["status"] = status

    if workflow:
        path = f"/repos/{full_name}/actions/workflows/{workflow}/runs"
    else:
        path = f"/repos/{full_name}/actions/runs"

    data = client.get(path, params=params)
    runs = data.get("workflow_runs", [])[:limit]

    rows = []
    for r in runs:
        duration = ""
        if r.get("run_started_at") and r.get("updated_at"):
            from datetime import datetime
            start = datetime.fromisoformat(r["run_started_at"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00"))
            secs = int((end - start).total_seconds())
            duration = f"{secs // 60}m {secs % 60}s"
        rows.append({"id": r["id"], "workflow": r["name"], "branch": r.get("head_branch", ""), "status": r["status"], "conclusion": r.get("conclusion") or "", "duration": duration, "started": (r.get("run_started_at") or "")[:16], "url": r["html_url"]})

    if export_path:
        from supergh.export import export_data
        export_data(rows, export_path)
        return

    if output_fmt != "table":
        from supergh.export import format_for_output
        click.echo(format_for_output(rows, output_fmt))
        return

    table = Table(title=f"Workflow Runs — {full_name}")
    table.add_column("ID", justify="right")
    table.add_column("Workflow", style="cyan")
    table.add_column("Branch", style="dim")
    table.add_column("Status")
    table.add_column("Conclusion")
    table.add_column("Duration", style="dim")
    table.add_column("Started", style="dim")

    for row in rows:
        conclusion = row["conclusion"]
        style = "green" if conclusion == "success" else "red" if conclusion == "failure" else "yellow"
        table.add_row(
            str(row["id"]),
            row["workflow"],
            row["branch"] or "-",
            row["status"],
            f"[{style}]{conclusion}[/{style}]" if conclusion else "-",
            row["duration"],
            row["started"],
        )
    console.print(table)


@run.command("view")
@click.argument("run_id", type=int)
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.pass_context
def run_view(ctx, run_id, repo_name, org):
    """View a workflow run."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    r = client.get(f"/repos/{full_name}/actions/runs/{run_id}")

    console.print(f"\n[bold cyan]{r['name']} #{r['run_number']}[/bold cyan]")
    console.print(f"  Status:      {r['status']}")
    console.print(f"  Conclusion:  {r.get('conclusion') or 'pending'}")
    console.print(f"  Branch:      {r['head_branch']}")
    console.print(f"  Commit:      {r['head_sha'][:8]}")
    console.print(f"  Trigger:     {r['event']}")
    console.print(f"  Actor:       {r['actor']['login']}")
    console.print(f"  URL:         {r['html_url']}")

    # Show jobs
    jobs = client.get(f"/repos/{full_name}/actions/runs/{run_id}/jobs")
    if jobs.get("jobs"):
        console.print(f"\n[bold]Jobs:[/bold]")
        for j in jobs["jobs"]:
            conclusion = j.get("conclusion") or "running"
            style = "green" if conclusion == "success" else "red" if conclusion == "failure" else "yellow"
            console.print(f"  [{style}]{conclusion:12}[/{style}] {j['name']}")


@run.command("watch")
@click.argument("run_id", type=int)
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.option("--interval", default=5, help="Poll interval in seconds.")
@click.pass_context
def run_watch(ctx, run_id, repo_name, org, interval):
    """Watch a workflow run live."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)

    with Live(console=console, refresh_per_second=1) as live:
        while True:
            r = client.get(f"/repos/{full_name}/actions/runs/{run_id}")
            jobs = client.get(f"/repos/{full_name}/actions/runs/{run_id}/jobs")

            table = Table(title=f"{r['name']} #{r['run_number']} — {r['status']}")
            table.add_column("Job", style="cyan")
            table.add_column("Status")
            table.add_column("Conclusion")

            for j in jobs.get("jobs", []):
                conclusion = j.get("conclusion") or ""
                style = "green" if conclusion == "success" else "red" if conclusion == "failure" else "yellow"
                table.add_row(j["name"], j["status"], f"[{style}]{conclusion or 'pending'}[/{style}]")

            live.update(table)

            if r["status"] == "completed":
                break
            time.sleep(interval)

    conclusion = r.get("conclusion", "unknown")
    style = "green" if conclusion == "success" else "red"
    console.print(f"\n[{style}]Run completed: {conclusion}[/{style}]")


@run.command("rerun")
@click.argument("run_id", type=int)
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.option("--failed-only", is_flag=True, help="Rerun only failed jobs.")
@click.pass_context
def run_rerun(ctx, run_id, repo_name, org, failed_only):
    """Rerun a workflow run."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    if failed_only:
        client.post(f"/repos/{full_name}/actions/runs/{run_id}/rerun-failed-jobs")
    else:
        client.post(f"/repos/{full_name}/actions/runs/{run_id}/rerun")
    console.print(f"[green]Rerun triggered for run {run_id}[/green]")


@run.command("cancel")
@click.argument("run_id", type=int)
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.pass_context
def run_cancel(ctx, run_id, repo_name, org):
    """Cancel a workflow run."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    client.post(f"/repos/{full_name}/actions/runs/{run_id}/cancel")
    console.print(f"[green]Cancelled run {run_id}[/green]")


@run.command("delete")
@click.argument("run_id", type=int)
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.pass_context
def run_delete(ctx, run_id, repo_name, org):
    """Delete a workflow run."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    client.delete(f"/repos/{full_name}/actions/runs/{run_id}")
    console.print(f"[green]Deleted run {run_id}[/green]")


@run.command("download")
@click.argument("run_id", type=int)
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.option("--dir", "directory", default=".", help="Download directory.")
@click.pass_context
def run_download(ctx, run_id, repo_name, org, directory):
    """Download workflow run artifacts."""
    full_name = _resolve_repo(org, repo_name)
    client = _client(ctx)
    artifacts = client.get(f"/repos/{full_name}/actions/runs/{run_id}/artifacts")

    from pathlib import Path
    import requests as req
    from supergh.auth.middleware import get_auth_provider

    token = get_auth_provider().get_token()
    dest = Path(directory)
    dest.mkdir(parents=True, exist_ok=True)

    for a in artifacts.get("artifacts", []):
        console.print(f"[dim]Downloading {a['name']}...[/dim]")
        r = req.get(
            a["archive_download_url"],
            headers={"Authorization": f"Bearer {token}"},
            stream=True, timeout=60,
        )
        r.raise_for_status()
        path = dest / f"{a['name']}.zip"
        with open(path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        console.print(f"  [green]Saved: {path}[/green]")
