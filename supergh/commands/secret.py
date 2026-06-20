"""sgh secret / sgh variable — manage secrets and variables."""

import json
from base64 import b64encode

import click
from rich.console import Console
from rich.table import Table

from supergh.api.client import GitHubClient
from supergh.commands.pr import _resolve_repo
from supergh.config import get_config

console = Console()


def _client(ctx) -> GitHubClient:
    return GitHubClient(debug=ctx.obj.get("debug", False))


# --- Secrets ---

@click.group("secret")
@click.pass_context
def secret(ctx):
    """Manage repository/org secrets."""


@secret.command("list")
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.option("--env", "environment", default=None, help="Environment name.")
@click.option("--org-level", is_flag=True, help="List org-level secrets.")
@click.pass_context
def secret_list(ctx, repo_name, org, environment, org_level):
    """List secrets."""
    client = _client(ctx)
    cfg = get_config()

    if org_level:
        o = org or cfg.org
        data = client.get(f"/orgs/{o}/actions/secrets")
    elif environment:
        full_name = _resolve_repo(org, repo_name)
        data = client.get(f"/repos/{full_name}/environments/{environment}/secrets")
    else:
        full_name = _resolve_repo(org, repo_name)
        data = client.get(f"/repos/{full_name}/actions/secrets")

    table = Table(title="Secrets")
    table.add_column("Name", style="cyan")
    table.add_column("Created", style="dim")
    table.add_column("Updated", style="dim")

    for s in data.get("secrets", []):
        table.add_row(s["name"], s.get("created_at", "")[:10], s.get("updated_at", "")[:10])
    console.print(table)


@secret.command("set")
@click.argument("name")
@click.argument("value")
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.option("--env", "environment", default=None)
@click.option("--org-level", is_flag=True)
@click.pass_context
def secret_set(ctx, name, value, repo_name, org, environment, org_level):
    """Set a secret."""
    client = _client(ctx)
    cfg = get_config()

    if org_level:
        o = org or cfg.org
        key_data = client.get(f"/orgs/{o}/actions/secrets/public-key")
        encrypted = _encrypt_secret(key_data["key"], value)
        client.put(f"/orgs/{o}/actions/secrets/{name}", json={"encrypted_value": encrypted, "key_id": key_data["key_id"], "visibility": "all"})
    elif environment:
        full_name = _resolve_repo(org, repo_name)
        repo_id = client.get(f"/repos/{full_name}")["id"]
        key_data = client.get(f"/repositories/{repo_id}/environments/{environment}/secrets/public-key")
        encrypted = _encrypt_secret(key_data["key"], value)
        client.put(f"/repositories/{repo_id}/environments/{environment}/secrets/{name}", json={"encrypted_value": encrypted, "key_id": key_data["key_id"]})
    else:
        full_name = _resolve_repo(org, repo_name)
        key_data = client.get(f"/repos/{full_name}/actions/secrets/public-key")
        encrypted = _encrypt_secret(key_data["key"], value)
        client.put(f"/repos/{full_name}/actions/secrets/{name}", json={"encrypted_value": encrypted, "key_id": key_data["key_id"]})

    console.print(f"[green]Set secret {name}[/green]")


@secret.command("delete")
@click.argument("name")
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.option("--env", "environment", default=None)
@click.option("--org-level", is_flag=True)
@click.pass_context
def secret_delete(ctx, name, repo_name, org, environment, org_level):
    """Delete a secret."""
    client = _client(ctx)
    cfg = get_config()

    if org_level:
        o = org or cfg.org
        client.delete(f"/orgs/{o}/actions/secrets/{name}")
    elif environment:
        full_name = _resolve_repo(org, repo_name)
        repo_id = client.get(f"/repos/{full_name}")["id"]
        client.delete(f"/repositories/{repo_id}/environments/{environment}/secrets/{name}")
    else:
        full_name = _resolve_repo(org, repo_name)
        client.delete(f"/repos/{full_name}/actions/secrets/{name}")

    console.print(f"[green]Deleted secret {name}[/green]")


def _encrypt_secret(public_key: str, secret_value: str) -> str:
    """Encrypt a secret using the repo's public key (libsodium sealed box)."""
    from nacl import encoding, public

    public_key_bytes = public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key_bytes)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return b64encode(encrypted).decode("utf-8")


# --- Variables ---

@click.group("variable")
@click.pass_context
def variable(ctx):
    """Manage repository/org variables."""


@variable.command("list")
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.option("--env", "environment", default=None)
@click.option("--org-level", is_flag=True)
@click.pass_context
def variable_list(ctx, repo_name, org, environment, org_level):
    """List variables."""
    client = _client(ctx)
    cfg = get_config()

    if org_level:
        o = org or cfg.org
        data = client.get(f"/orgs/{o}/actions/variables")
    elif environment:
        full_name = _resolve_repo(org, repo_name)
        data = client.get(f"/repos/{full_name}/environments/{environment}/variables")
    else:
        full_name = _resolve_repo(org, repo_name)
        data = client.get(f"/repos/{full_name}/actions/variables")

    table = Table(title="Variables")
    table.add_column("Name", style="cyan")
    table.add_column("Value", style="green")
    table.add_column("Updated", style="dim")

    for v in data.get("variables", []):
        table.add_row(v["name"], v["value"][:50], v.get("updated_at", "")[:10])
    console.print(table)


@variable.command("set")
@click.argument("name")
@click.argument("value")
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.option("--env", "environment", default=None)
@click.option("--org-level", is_flag=True)
@click.pass_context
def variable_set(ctx, name, value, repo_name, org, environment, org_level):
    """Set a variable."""
    client = _client(ctx)
    cfg = get_config()

    payload = {"name": name, "value": value}

    if org_level:
        o = org or cfg.org
        try:
            client.patch(f"/orgs/{o}/actions/variables/{name}", json=payload)
        except Exception:
            payload["visibility"] = "all"
            client.post(f"/orgs/{o}/actions/variables", json=payload)
    elif environment:
        full_name = _resolve_repo(org, repo_name)
        try:
            client.patch(f"/repos/{full_name}/environments/{environment}/variables/{name}", json=payload)
        except Exception:
            client.post(f"/repos/{full_name}/environments/{environment}/variables", json=payload)
    else:
        full_name = _resolve_repo(org, repo_name)
        try:
            client.patch(f"/repos/{full_name}/actions/variables/{name}", json=payload)
        except Exception:
            client.post(f"/repos/{full_name}/actions/variables", json=payload)

    console.print(f"[green]Set variable {name}[/green]")


@variable.command("delete")
@click.argument("name")
@click.option("--repo", "-r", "repo_name", default=None)
@click.option("--org", "-o", default=None)
@click.option("--env", "environment", default=None)
@click.option("--org-level", is_flag=True)
@click.pass_context
def variable_delete(ctx, name, repo_name, org, environment, org_level):
    """Delete a variable."""
    client = _client(ctx)
    cfg = get_config()

    if org_level:
        o = org or cfg.org
        client.delete(f"/orgs/{o}/actions/variables/{name}")
    elif environment:
        full_name = _resolve_repo(org, repo_name)
        client.delete(f"/repos/{full_name}/environments/{environment}/variables/{name}")
    else:
        full_name = _resolve_repo(org, repo_name)
        client.delete(f"/repos/{full_name}/actions/variables/{name}")

    console.print(f"[green]Deleted variable {name}[/green]")
