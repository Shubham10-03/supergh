"""sgh auth — authentication commands."""

import click
from rich.console import Console

from supergh.auth.middleware import get_auth_provider
from supergh.auth.store import TokenStore
from supergh.config import get_config

console = Console()


def _check_existing_auth():
    """Warn if already authenticated via any method and require confirmation."""
    try:
        # Check OAuth/PAT tokens
        oauth_store = TokenStore(namespace="oauth")
        oauth_token = oauth_store.get_token("access_token")
        oauth_user = oauth_store.get_token("username")

        # Check App auth from config
        cfg = get_config()
        profile = cfg.active_profile
        app_id = profile.get("app_id", "")
        pem_path = profile.get("pem_path", "")
        app_configured = bool(app_id and pem_path)

        # Determine what's active
        active_type = cfg.auth_type
        authenticated = False
        identity = ""

        if active_type == "app" and app_configured:
            authenticated = True
            org = profile.get("org", "") or cfg.get("core.default_org", "")
            app_store = TokenStore(namespace=f"app_{app_id}_{org}")
            app_name = app_store.get_token("app_name") or f"App {app_id}"
            identity = f"{app_name} on {org}"
        elif oauth_token:
            authenticated = True
            identity = oauth_user or "token"

        if authenticated:
            console.print(f"[yellow]Already authenticated: {identity} (type: {active_type})[/yellow]")
            if not click.confirm("Re-authenticate? This will overwrite your current credentials"):
                raise SystemExit(0)
    except SystemExit:
        raise
    except Exception:
        pass


@click.group("auth")
def auth():
    """Authenticate with GitHub.

    \b
    Auth methods:
      pat    — Personal Access Token (quickest)
      oauth  — Browser-based device flow (requires setup-oauth first)
      app    — GitHub App with PEM key (for automation/CI)
    """


@auth.command()
@click.option("--from-file", "-f", type=click.Path(exists=True), help="Read token from a file.")
def pat(from_file):
    """Login with a Personal Access Token."""
    import requests

    _check_existing_auth()

    if from_file:
        from pathlib import Path
        token = Path(from_file).read_text(encoding="utf-8").strip()
    else:
        token = click.prompt("GitHub PAT").strip()

    if not token:
        console.print("[red]No token provided.[/red]")
        raise SystemExit(1)

    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
    resp = requests.get("https://api.github.com/user", headers=headers, timeout=30)
    if resp.status_code != 200:
        console.print(f"[red]Token rejected by GitHub (HTTP {resp.status_code}).[/red]")
        try:
            msg = resp.json().get("message", "")
            if msg:
                console.print(f"[red]  {msg}[/red]")
        except Exception:
            pass
        raise SystemExit(1)

    username = resp.json()["login"]
    store = TokenStore(namespace="oauth")
    store.set_token("access_token", token)
    store.set_token("username", username)

    # Resolve and cache permissions from scopes
    scopes_header = resp.headers.get("X-OAuth-Scopes", "")
    from supergh.auth.permissions import resolve_permissions_from_scopes, store_permissions
    perms = resolve_permissions_from_scopes(scopes_header)
    store_permissions(perms, namespace="oauth")

    console.print(f"[green]Logged in as {username}[/green]")

    cfg = get_config()
    org = cfg.org
    if org:
        org_resp = requests.get(
            f"https://api.github.com/orgs/{org}",
            headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"},
            timeout=30,
        )
        if org_resp.status_code == 200:
            console.print(f"[green]Org access verified: {org}[/green]")
        else:
            console.print(f"[yellow]Cannot access org '{org}'. Check PAT scopes (needs: repo, read:org).[/yellow]")


@auth.command()
def oauth():
    """Login via OAuth device flow (opens browser).

    \b
    Requires setup-oauth first to register a Client ID.
    """
    _check_existing_auth()
    from supergh.auth.oauth import GitHubOAuthAuth

    cfg = get_config()
    store = TokenStore(namespace="oauth_app")
    client_id = store.get_token("client_id") or cfg.get("oauth.client_id", "")

    if not client_id:
        console.print("[red]No OAuth App registered.[/red]")
        console.print("Run [cyan]sgh auth setup-oauth[/cyan] first.")
        raise SystemExit(1)

    provider = GitHubOAuthAuth(org=cfg.org)
    provider.login(client_id=client_id)


@auth.command()
@click.option("--name", "-n", default=None, help="Friendly app name. Reuses a registered app if it exists.")
@click.option("--app-id", "app_id_opt", default=None, help="GitHub App ID (first-time registration).")
@click.option("--pem", "pem_opt", default=None, type=click.Path(), help="Path to PEM private key (first-time registration; copied into ~/.supergh/apps/).")
@click.option("--org", "org_opt", default=None, help="Org to use (skips the installation prompt).")
def app(name, app_id_opt, pem_opt, org_opt):
    """Login with a GitHub App (PEM key).

    \b
    First time (registers the app, copying the PEM into ~/.supergh/apps/):
      sgh auth app --name captwo --app-id 123 --pem ./captwo.pem
      sgh auth app            # interactive: prompts for name, App ID, PEM path

    \b
    Afterwards (reuse a registered app — no path needed):
      sgh auth app --name captwo

    Registered apps are listed by: sgh app list
    """
    _check_existing_auth()
    from pathlib import Path
    import requests
    import jwt as pyjwt
    import time as t

    from supergh.auth.app_registry import get_registry

    cfg = get_config()
    registry = get_registry()

    # --- Resolve app_id + pem path from the registry or from first-time input ---
    reused = False
    if name and registry.exists(name):
        entry = registry.get(name)
        if not registry.pem_present(entry):
            console.print(f"[red]Registered app '{name}' is missing its PEM file "
                          f"({entry.pem_file}). Re-register with --pem.[/red]")
            raise SystemExit(1)
        app_id = entry.app_id
        pem_file = registry.pem_path(entry)
        if not org_opt and entry.org:
            org_opt = entry.org
        reused = True
        console.print(f"[dim]Using registered app '{name}' (ID: {app_id}).[/dim]")
    else:
        # First-time registration path.
        if not name:
            name = click.prompt("App name (for future reuse)")
        app_id = app_id_opt or click.prompt("GitHub App ID")
        pem_input = pem_opt or click.prompt("Path to PEM file")
        pem_src = Path(pem_input).expanduser()
        if not pem_src.exists():
            console.print(f"[red]PEM file not found: {pem_input}[/red]")
            raise SystemExit(1)
        # Register now (copies PEM into ~/.supergh/apps/ with 0600 perms).
        try:
            entry = registry.register(name=name, app_id=str(app_id), pem_source=pem_src,
                                      org=org_opt or "", overwrite=True)
        except (ValueError, FileNotFoundError) as e:
            console.print(f"[red]{e}[/red]")
            raise SystemExit(1)
        pem_file = registry.pem_path(entry)
        console.print(f"[dim]Registered app '{name}' → {entry.pem_file} (key stored securely).[/dim]")

    pem_bytes = Path(pem_file).read_bytes()

    # Validate PEM format
    if b"-----BEGIN" not in pem_bytes:
        console.print("[red]Invalid PEM file — must contain a private key.[/red]")
        raise SystemExit(1)

    # Generate JWT and validate against GitHub
    console.print("[dim]Validating credentials against GitHub...[/dim]")
    try:
        now = int(t.time())
        payload = {"iat": now - 60, "exp": now + 600, "iss": str(app_id)}
        jwt_token = pyjwt.encode(payload, pem_bytes, algorithm="RS256")
    except Exception as e:
        console.print(f"[red]Failed to sign JWT — invalid PEM key.[/red]")
        console.print(f"[red]  {e}[/red]")
        raise SystemExit(1)

    # Verify app exists
    resp = requests.get(
        "https://api.github.com/app",
        headers={"Authorization": f"Bearer {jwt_token}", "Accept": "application/vnd.github+json"},
        timeout=30,
    )
    if resp.status_code == 401:
        console.print("[red]Authentication failed — App ID and PEM key do not match.[/red]")
        console.print("[red]  Ensure the PEM belongs to this App ID and has not been revoked.[/red]")
        raise SystemExit(1)
    if resp.status_code != 200:
        console.print(f"[red]GitHub API error (HTTP {resp.status_code}): {resp.json().get('message', '')}[/red]")
        raise SystemExit(1)

    app_name = resp.json().get("name", f"App {app_id}")
    console.print(f"  App verified: [cyan]{app_name}[/cyan]")

    # Check installations
    inst_resp = requests.get(
        "https://api.github.com/app/installations",
        headers={"Authorization": f"Bearer {jwt_token}", "Accept": "application/vnd.github+json"},
        timeout=30,
    )
    installations = inst_resp.json() if inst_resp.status_code == 200 else []

    if not installations:
        console.print("[red]This App has no installations. Install it on an organization first.[/red]")
        raise SystemExit(1)

    # Pick org: explicit --org/registry, else single install, else prompt.
    orgs = [i["account"]["login"] for i in installations if i.get("account")]
    if org_opt and org_opt in orgs:
        org = org_opt
    elif len(orgs) == 1:
        org = orgs[0]
    else:
        console.print(f"  Installed on: {', '.join(orgs)}")
        org = click.prompt("  Which org to use", type=click.Choice(orgs))

    # Persist the resolved org back to the registry entry.
    registry.set_org(name, org)

    # Get installation token to fully validate
    install = next(i for i in installations if i["account"]["login"] == org)
    token_resp = requests.post(
        f"https://api.github.com/app/installations/{install['id']}/access_tokens",
        headers={"Authorization": f"Bearer {jwt_token}", "Accept": "application/vnd.github+json"},
        timeout=30,
    )
    if token_resp.status_code != 201:
        console.print(f"[red]Failed to generate installation token for '{org}'.[/red]")
        console.print(f"[red]  {token_resp.json().get('message', '')}[/red]")
        raise SystemExit(1)

    # All good — resolve permissions and save
    token_data = token_resp.json()
    inst_token = token_data["token"]
    inst_permissions = token_data.get("permissions", {})

    from supergh.auth.permissions import resolve_permissions_from_app_install, store_permissions
    perms = resolve_permissions_from_app_install(inst_permissions)
    namespace = f"app_{app_id}_{org}"
    store_permissions(perms, namespace=namespace)

    store = TokenStore(namespace=namespace)
    store.set_token("access_token", inst_token)
    store.set_token("installed_org", org)
    store.set_token("app_name", app_name)

    # Use the app name as the profile name so multiple apps coexist.
    profile_name = name or cfg.active_profile_name
    cfg.set(f"profiles.{profile_name}.auth_type", "app")
    cfg.set(f"profiles.{profile_name}.app_id", str(app_id))
    cfg.set(f"profiles.{profile_name}.pem_path", str(pem_file))
    cfg.set(f"profiles.{profile_name}.org", org)
    cfg.set("core.default_profile", profile_name)
    cfg.set("core.default_org", org)

    verb = "Reusing" if reused else "Registered &"
    console.print(f"[green]{verb} authenticated as {app_name} on {org} (profile: {profile_name})[/green]")


@auth.command("setup-oauth")
def setup_oauth():
    """Register an OAuth App Client ID for device flow.

    \b
    Prerequisites:
      1. Create an OAuth App at https://github.com/settings/developers
      2. Set callback URL to http://localhost
      3. Enable "Device Flow" in app settings
      4. Copy the Client ID
    """
    client_id = click.prompt("OAuth App Client ID")

    if not client_id or len(client_id) < 10:
        console.print("[red]Invalid Client ID.[/red]")
        raise SystemExit(1)

    store = TokenStore(namespace="oauth_app")
    store.set_token("client_id", client_id)
    console.print("[green]Client ID registered.[/green]")
    console.print("Next: run [cyan]sgh auth oauth[/cyan]")


@auth.command()
def logout():
    """Clear all stored tokens from keychain."""
    provider = get_auth_provider()
    provider.logout()
    console.print("[green]Logged out.[/green]")


@auth.command()
def status():
    """Show current auth status."""
    provider = get_auth_provider()
    st = provider.status()

    if st.authenticated:
        console.print("[green]Authenticated[/green]")
        console.print(f"  Type:     {st.auth_type}")
        if st.auth_type == "app":
            console.print(f"  App:      {st.app_name or 'N/A'} (ID: {st.app_id or 'N/A'})")
            username_display = (st.username or 'N/A').replace('[', '\\[')  
            console.print(f"  User:     {username_display}")
            console.print(f"  Id:       {st.app_id or 'N/A'}")
        else:
            console.print(f"  User:     {st.username or 'N/A'}")
        console.print(f"  Org:      {st.org or 'N/A'}")
        if st.expires_in_seconds is not None:
            console.print(f"  Expires:  {st.expires_in_seconds // 60} min remaining")
    else:
        console.print("[yellow]Not authenticated.[/yellow]")
        console.print("  Run: sgh auth pat | sgh auth oauth | sgh auth app")


@auth.command()
@click.confirmation_option(prompt="This will print your token to the terminal. Continue?")
def token():
    """Print current access token (requires confirmation)."""
    provider = get_auth_provider()
    click.echo(provider.get_token())


@auth.command()
def refresh():
    """Force refresh the current token."""
    provider = get_auth_provider()
    if hasattr(provider, 'get_token'):
        import inspect
        sig = inspect.signature(provider.get_token)
        if 'force_refresh' in sig.parameters:
            provider.get_token(force_refresh=True)
        else:
            provider.get_token()
    console.print("[green]Token refreshed.[/green]")

@auth.command()
@click.argument("profile")
def switch(profile):
    """Switch to a different auth profile."""
    cfg = get_config()
    profiles = cfg.get("profiles", {})
    if profile not in profiles:
        console.print(f"[red]Profile '{profile}' not found.[/red]")
        console.print(f"Available: {', '.join(profiles.keys())}")
        raise SystemExit(1)
    cfg.set("core.default_profile", profile)
    console.print(f"[green]Switched to profile '{profile}'[/green]")


@auth.command()
def permissions():
    """View current permissions (cached from auth time)."""
    from supergh.auth.permissions import get_cached_permissions
    from rich.table import Table

    perms = get_cached_permissions()
    if not perms:
        console.print("[yellow]No permissions cached. Re-authenticate to resolve permissions.[/yellow]")
        console.print("  Run: sgh auth pat | sgh auth oauth | sgh auth app")
        raise SystemExit(1)

    table = Table(title="Permissions")
    table.add_column("Scope", style="cyan")
    table.add_column("Read")
    table.add_column("Write")

    for scope, levels in perms.items():
        read = "[green]✓[/green]" if levels.get("read") else "[red]✕[/red]"
        write = "[green]✓[/green]" if levels.get("write") else "[red]✕[/red]"
        table.add_row(scope, read, write)

    console.print(table)
