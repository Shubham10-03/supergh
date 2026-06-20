"""sgh ruleset — view repository and org rulesets."""

import click
from rich.console import Console
from rich.table import Table

from supergh.api.client import GitHubClient
from supergh.commands.pr import _resolve_repo
from supergh.config import get_config

console = Console()


def _client(ctx) -> GitHubClient:
    return GitHubClient(debug=ctx.obj.get("debug", False))


@click.group("ruleset")
@click.pass_context
def ruleset(ctx):
    """View info about repo rulesets."""


@ruleset.command("list")
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.pass_context
def ruleset_list(ctx, repo_name, org):
    """List rulesets for a repo or org."""
    client = _client(ctx)
    cfg = get_config()
    o = org or cfg.org

    if repo_name:
        full_name = f"{o}/{repo_name}" if o and "/" not in repo_name else repo_name
        rulesets = client.get(f"/repos/{full_name}/rulesets")
    else:
        rulesets = client.get(f"/orgs/{o}/rulesets")

    table = Table(title=f"Rulesets — {repo_name or o}")
    table.add_column("ID", justify="right")
    table.add_column("Name", style="cyan")
    table.add_column("Target", style="yellow")
    table.add_column("Enforcement")
    table.add_column("Source", style="dim")

    for rs in rulesets:
        enforcement = rs.get("enforcement", "")
        style = "green" if enforcement == "active" else "yellow" if enforcement == "evaluate" else "dim"
        table.add_row(
            str(rs["id"]),
            rs["name"],
            rs.get("target", ""),
            f"[{style}]{enforcement}[/{style}]",
            rs.get("source_type", ""),
        )
    console.print(table)


@ruleset.command("view")
@click.argument("ruleset_id", type=int)
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.pass_context
def ruleset_view(ctx, ruleset_id, repo_name, org):
    """View ruleset details."""
    client = _client(ctx)
    cfg = get_config()
    o = org or cfg.org

    if repo_name:
        full_name = f"{o}/{repo_name}" if o and "/" not in repo_name else repo_name
        rs = client.get(f"/repos/{full_name}/rulesets/{ruleset_id}")
    else:
        rs = client.get(f"/orgs/{o}/rulesets/{ruleset_id}")

    console.print(f"\n[bold cyan]{rs['name']}[/bold cyan]")
    console.print(f"  ID:          {rs['id']}")
    console.print(f"  Target:      {rs.get('target', '')}")
    console.print(f"  Enforcement: {rs.get('enforcement', '')}")
    console.print(f"  Source:      {rs.get('source_type', '')} / {rs.get('source', {}).get('name', '')}")

    # Conditions
    conditions = rs.get("conditions", {})
    if conditions:
        ref_name = conditions.get("ref_name", {})
        includes = ref_name.get("include", [])
        excludes = ref_name.get("exclude", [])
        if includes:
            console.print(f"  Includes:    {', '.join(includes)}")
        if excludes:
            console.print(f"  Excludes:    {', '.join(excludes)}")

    # Rules
    rules = rs.get("rules", [])
    if rules:
        console.print(f"\n[bold]Rules ({len(rules)}):[/bold]")
        for rule in rules:
            rule_type = rule.get("type", "")
            params = rule.get("parameters", {})
            param_str = ""
            if params:
                param_str = f" ({', '.join(f'{k}={v}' for k, v in params.items())})"
            console.print(f"  • {rule_type}{param_str}")
