"""sgh project — manage GitHub Projects (v2)."""

import click
from rich.console import Console
from rich.table import Table

from supergh.api.client import GitHubClient
from supergh.config import get_config

console = Console()


def _client(ctx) -> GitHubClient:
    return GitHubClient(debug=ctx.obj.get("debug", False))


@click.group("project")
@click.pass_context
def project(ctx):
    """Work with GitHub Projects."""


@project.command("list")
@click.option("--org", "-o", default=None)
@click.option("--limit", "-l", default=20)
@click.pass_context
def project_list(ctx, org, limit):
    """List projects."""
    client = _client(ctx)
    cfg = get_config()
    o = org or cfg.org

    query = """
    query($owner: String!, $first: Int!) {
      organization(login: $owner) {
        projectsV2(first: $first) {
          nodes {
            id number title shortDescription closed url createdAt updatedAt
            items { totalCount }
          }
        }
      }
    }
    """
    data = client.graphql(query, variables={"owner": o, "first": limit})
    projects = data.get("data", {}).get("organization", {}).get("projectsV2", {}).get("nodes", [])

    table = Table(title=f"Projects — {o}")
    table.add_column("#", justify="right")
    table.add_column("Title", style="cyan")
    table.add_column("Items", justify="right")
    table.add_column("Status")
    table.add_column("Updated", style="dim")

    for p in projects:
        status = "[red]Closed[/red]" if p["closed"] else "[green]Open[/green]"
        table.add_row(
            str(p["number"]),
            p["title"],
            str(p["items"]["totalCount"]),
            status,
            p["updatedAt"][:10],
        )
    console.print(table)


@project.command("view")
@click.argument("number", type=int)
@click.option("--org", "-o", default=None)
@click.pass_context
def project_view(ctx, number, org):
    """View project details."""
    client = _client(ctx)
    cfg = get_config()
    o = org or cfg.org

    query = """
    query($owner: String!, $number: Int!) {
      organization(login: $owner) {
        projectV2(number: $number) {
          id title shortDescription closed url createdAt updatedAt
          items(first: 50) {
            totalCount
            nodes {
              content {
                ... on Issue { number title state }
                ... on PullRequest { number title state }
                ... on DraftIssue { title }
              }
            }
          }
          fields(first: 20) {
            nodes { ... on ProjectV2SingleSelectField { name } ... on ProjectV2Field { name } }
          }
        }
      }
    }
    """
    data = client.graphql(query, variables={"owner": o, "number": number})
    p = data.get("data", {}).get("organization", {}).get("projectV2", {})

    if not p:
        console.print(f"[red]Project #{number} not found.[/red]")
        return

    console.print(f"\n[bold cyan]#{number} {p['title']}[/bold cyan]")
    if p.get("shortDescription"):
        console.print(f"  {p['shortDescription']}")
    console.print(f"  Status:   {'Closed' if p['closed'] else 'Open'}")
    console.print(f"  Items:    {p['items']['totalCount']}")
    console.print(f"  Created:  {p['createdAt'][:10]}")
    console.print(f"  Updated:  {p['updatedAt'][:10]}")
    console.print(f"  URL:      {p['url']}")

    items = p.get("items", {}).get("nodes", [])
    if items:
        console.print(f"\n[bold]Items:[/bold]")
        for item in items[:20]:
            content = item.get("content", {})
            if not content:
                continue
            num = content.get("number", "")
            title = content.get("title", "Draft")
            state = content.get("state", "DRAFT")
            style = "green" if state in ("OPEN", "MERGED") else "red" if state == "CLOSED" else "dim"
            prefix = f"#{num} " if num else ""
            console.print(f"  [{style}]{prefix}{title}[/{style}]")


@project.command("create")
@click.argument("title")
@click.option("--org", "-o", default=None)
@click.pass_context
def project_create(ctx, title, org):
    """Create a new project."""
    client = _client(ctx)
    cfg = get_config()
    o = org or cfg.org

    # Get org node ID
    org_data = client.graphql(
        "query($login: String!) { organization(login: $login) { id } }",
        variables={"login": o}
    )
    owner_id = org_data["data"]["organization"]["id"]

    mutation = """
    mutation($ownerId: ID!, $title: String!) {
      createProjectV2(input: {ownerId: $ownerId, title: $title}) {
        projectV2 { number title url }
      }
    }
    """
    data = client.graphql(mutation, variables={"ownerId": owner_id, "title": title})
    p = data["data"]["createProjectV2"]["projectV2"]
    console.print(f"[green]Created project #{p['number']}: {p['title']}[/green]")
    console.print(f"  {p['url']}")


@project.command("close")
@click.argument("number", type=int)
@click.option("--org", "-o", default=None)
@click.pass_context
def project_close(ctx, number, org):
    """Close a project."""
    client = _client(ctx)
    cfg = get_config()
    o = org or cfg.org

    # Get project ID
    data = client.graphql(
        "query($owner: String!, $number: Int!) { organization(login: $owner) { projectV2(number: $number) { id } } }",
        variables={"owner": o, "number": number}
    )
    project_id = data["data"]["organization"]["projectV2"]["id"]

    client.graphql(
        "mutation($id: ID!) { updateProjectV2(input: {projectId: $id, closed: true}) { projectV2 { number } } }",
        variables={"id": project_id}
    )
    console.print(f"[green]Closed project #{number}[/green]")


@project.command("delete")
@click.argument("number", type=int)
@click.option("--org", "-o", default=None)
@click.option("--yes", is_flag=True)
@click.pass_context
def project_delete(ctx, number, org, yes):
    """Delete a project."""
    if not yes:
        click.confirm(f"Delete project #{number}? Cannot be undone", abort=True)
    client = _client(ctx)
    cfg = get_config()
    o = org or cfg.org

    data = client.graphql(
        "query($owner: String!, $number: Int!) { organization(login: $owner) { projectV2(number: $number) { id } } }",
        variables={"owner": o, "number": number}
    )
    project_id = data["data"]["organization"]["projectV2"]["id"]

    client.graphql(
        "mutation($id: ID!) { deleteProjectV2(input: {projectId: $id}) { projectV2 { number } } }",
        variables={"id": project_id}
    )
    console.print(f"[green]Deleted project #{number}[/green]")
