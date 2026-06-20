"""sgh ui — Web UI server (localhost only)."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Body
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from supergh.api.client import GitHubClient
from supergh.config import get_config
from supergh.utils.logger import get_logger

log = get_logger()

UI_DIR = Path(__file__).parent
TEMPLATES_DIR = UI_DIR / "templates"
STATIC_DIR = UI_DIR / "static"

app = FastAPI(title="supergh", docs_url=None, redoc_url=None)


def _client() -> GitHubClient:
    return GitHubClient()


def _org() -> str:
    return get_config().org


# ─── Pages ───

@app.get("/", response_class=HTMLResponse)
async def index():
    html = (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


# ─── Auth Info API ───

@app.get("/api/auth")
async def auth_info():
    from supergh.auth.middleware import get_auth_provider
    try:
        provider = get_auth_provider()
        st = provider.status()
        return {
            "authenticated": st.authenticated,
            "auth_type": st.auth_type,
            "username": st.username or "",
            "org": st.org or "",
            "app_name": st.app_name or "",
            "app_id": st.app_id or "",
            "expires_in": st.expires_in_seconds,
        }
    except Exception as e:
        log.error(f"Auth info failed: {e}")
        return {"authenticated": False, "auth_type": "", "username": "", "org": "", "app_name": "", "app_id": "", "expires_in": None}


@app.post("/api/auth/pat")
async def auth_with_pat(data: dict = Body()):
    import requests as req
    token = data.get("token", "").strip()
    if not token:
        return {"ok": False, "error": "No token provided"}

    resp = req.get(
        "https://api.github.com/user",
        headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"},
        timeout=30,
    )
    if resp.status_code != 200:
        return {"ok": False, "error": resp.json().get("message", "Invalid token")}

    username = resp.json()["login"]
    from supergh.auth.store import TokenStore
    store = TokenStore(namespace="oauth")
    store.set_token("access_token", token)
    store.set_token("username", username)

    # Resolve and cache permissions
    from supergh.auth.permissions import resolve_permissions_from_scopes, store_permissions
    scopes = resp.headers.get("X-OAuth-Scopes", "")
    perms = resolve_permissions_from_scopes(scopes)
    store_permissions(perms, namespace="oauth")

    cfg = get_config()
    cfg.set(f"profiles.{cfg.active_profile_name}.auth_type", "oauth")

    log.info(f"UI auth: logged in as {username}")
    return {"ok": True, "username": username}


@app.post("/api/auth/oauth/start")
async def auth_oauth_start(data: dict = Body()):
    """Start OAuth device flow."""
    import requests as req
    client_id = data.get("client_id", "").strip()
    if not client_id:
        return {"error": "Client ID is required"}

    resp = req.post(
        "https://github.com/login/device/code",
        headers={"Accept": "application/json"},
        data={"client_id": client_id, "scope": "repo read:org admin:org"},
        timeout=30,
    )
    if resp.status_code != 200:
        return {"error": "Failed to start device flow"}

    result = resp.json()
    return {
        "device_code": result.get("device_code"),
        "user_code": result.get("user_code"),
        "verification_uri": result.get("verification_uri"),
        "interval": result.get("interval", 5),
    }


@app.post("/api/auth/oauth/poll")
async def auth_oauth_poll(data: dict = Body()):
    """Poll for OAuth device flow token."""
    import requests as req
    import time

    device_code = data.get("device_code", "")
    client_id = data.get("client_id", "")
    interval = data.get("interval", 5)

    # Poll for up to 5 minutes
    for _ in range(60):
        time.sleep(interval)
        resp = req.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={"client_id": client_id, "device_code": device_code, "grant_type": "urn:ietf:params:oauth:grant-type:device_code"},
            timeout=30,
        )
        result = resp.json()
        if "access_token" in result:
            token = result["access_token"]
            # Verify token and get username
            user_resp = req.get(
                "https://api.github.com/user",
                headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"},
                timeout=30,
            )
            if user_resp.status_code == 200:
                username = user_resp.json()["login"]
                from supergh.auth.store import TokenStore
                store = TokenStore(namespace="oauth")
                store.set_token("access_token", token)
                store.set_token("username", username)
                if result.get("refresh_token"):
                    store.set_token("refresh_token", result["refresh_token"])

                cfg = get_config()
                cfg.set(f"profiles.{cfg.active_profile_name}.auth_type", "oauth")
                log.info(f"UI OAuth: logged in as {username}")
                return {"ok": True, "username": username}
            return {"ok": False, "error": "Token received but failed to verify"}

        error = result.get("error", "")
        if error == "authorization_pending":
            continue
        elif error == "slow_down":
            interval += 5
            continue
        elif error in ("expired_token", "access_denied"):
            return {"ok": False, "error": f"Authorization {error.replace('_', ' ')}"}

    return {"ok": False, "error": "Authorization timed out. Please try again."}


@app.post("/api/auth/app")
async def auth_with_app(data: dict = Body()):
    """Authenticate via GitHub App."""
    app_id = data.get("app_id", "").strip()
    pem = data.get("pem", "").strip()
    org = data.get("org", "").strip()

    if not app_id or not pem or not org:
        return {"ok": False, "error": "App ID, PEM key, and org are all required"}

    try:
        import jwt
        import time as t
        import requests as req
        from cryptography.hazmat.primitives.serialization import load_pem_private_key

        # Generate JWT
        private_key = load_pem_private_key(pem.encode(), password=None)
        now = int(t.time())
        payload = {"iat": now - 60, "exp": now + (10 * 60), "iss": app_id}
        token = jwt.encode(payload, private_key, algorithm="RS256")

        # Get app info
        app_resp = req.get(
            "https://api.github.com/app",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            timeout=30,
        )
        if app_resp.status_code != 200:
            return {"ok": False, "error": "Invalid App ID or PEM key"}

        app_info = app_resp.json()
        app_name = app_info.get("name", f"App {app_id}")

        # Find installation for org
        inst_resp = req.get(
            "https://api.github.com/app/installations",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            timeout=30,
        )
        installations = inst_resp.json() if inst_resp.status_code == 200 else []
        install = next((i for i in installations if i.get("account", {}).get("login", "").lower() == org.lower()), None)

        if not install:
            return {"ok": False, "error": f"App '{app_name}' is not installed on org '{org}'"}

        # Get installation token
        inst_token_resp = req.post(
            f"https://api.github.com/app/installations/{install['id']}/access_tokens",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            timeout=30,
        )
        if inst_token_resp.status_code != 201:
            return {"ok": False, "error": "Failed to generate installation token"}

        token_data = inst_token_resp.json()
        inst_token = token_data["token"]
        inst_permissions = token_data.get("permissions", {})

        # Resolve and cache permissions
        from supergh.auth.permissions import resolve_permissions_from_app_install, store_permissions
        namespace = f"app_{app_id}_{org}"
        perms = resolve_permissions_from_app_install(inst_permissions)
        store_permissions(perms, namespace=namespace)

        # Store token
        from supergh.auth.store import TokenStore
        store = TokenStore(namespace=namespace)
        store.set_token("access_token", inst_token)
        store.set_token("installed_org", org)
        store.set_token("app_name", app_name)

        cfg = get_config()
        cfg.set(f"profiles.{cfg.active_profile_name}.auth_type", "app")
        cfg.set(f"profiles.{cfg.active_profile_name}.app_id", app_id)
        cfg.set(f"profiles.{cfg.active_profile_name}.org", org)
        cfg.set("core.default_org", org)

        log.info(f"UI App auth: {app_name} on {org}")
        return {"ok": True, "app_name": app_name, "org": org}

    except Exception as e:
        log.error(f"App auth failed: {e}")
        return {"ok": False, "error": str(e)}


@app.post("/api/auth/logout")
async def auth_logout():
    from supergh.auth.middleware import get_auth_provider
    try:
        provider = get_auth_provider()
        provider.logout()
    except Exception:
        pass
    return {"ok": True}


# ─── Permissions API ───

@app.get("/api/permissions")
async def get_permissions():
    """Return cached permissions from keychain. No extra API calls."""
    from supergh.auth.permissions import get_cached_permissions
    perms = get_cached_permissions()
    if perms:
        return perms
    # Fallback: return empty permissions (not authenticated or not resolved yet)
    return {
        "repos": {"read": False, "write": False, "reason": "Permissions not resolved. Re-authenticate."},
        "issues": {"read": False, "write": False, "reason": "Permissions not resolved. Re-authenticate."},
        "pulls": {"read": False, "write": False, "reason": "Permissions not resolved. Re-authenticate."},
        "actions": {"read": False, "write": False, "reason": "Permissions not resolved. Re-authenticate."},
        "secrets": {"read": False, "write": False, "reason": "Permissions not resolved. Re-authenticate."},
        "teams": {"read": False, "write": False, "reason": "Permissions not resolved. Re-authenticate."},
        "members": {"read": False, "write": False, "reason": "Permissions not resolved. Re-authenticate."},
    }


# ─── Repos API ───

@app.get("/api/repos")
async def list_repos(page: int = 1, per_page: int = 30, sort: str = "pushed"):
    client = _client()
    repos = []
    try:
        all_repos = []
        for r in client.paginate(f"/orgs/{_org()}/repos", params={"per_page": per_page, "sort": sort, "page": page}):
            all_repos.append({"name": r["name"], "full_name": r["full_name"], "visibility": r["visibility"], "language": r.get("language") or "", "stars": r["stargazers_count"], "forks": r["forks_count"], "issues": r["open_issues_count"], "default_branch": r["default_branch"], "archived": r["archived"], "updated": r["updated_at"][:10], "description": r.get("description") or "", "url": r["html_url"]})
            if len(all_repos) >= per_page:
                break
        has_more = len(all_repos) == per_page
        return {"items": all_repos, "page": page, "per_page": per_page, "has_more": has_more}
    except Exception as e:
        log.error(f"list_repos failed: {e}")
        return {"items": [], "page": page, "per_page": per_page, "has_more": False}


@app.get("/api/repos/{name}")
async def get_repo(name: str):
    client = _client()
    return client.get(f"/repos/{_org()}/{name}")


@app.get("/api/repos-search")
async def search_repos(q: str, per_page: int = 30):
    """Search repos in org via GitHub Search API."""
    client = _client()
    org = _org()
    query = f"{q} org:{org}" if org else q
    try:
        data = client.get("/search/repositories", params={"q": query, "per_page": per_page})
        items = []
        for r in data.get("items", []):
            items.append({"name": r["name"], "full_name": r["full_name"], "visibility": r["visibility"], "language": r.get("language") or "", "stars": r["stargazers_count"], "forks": r["forks_count"], "issues": r["open_issues_count"], "default_branch": r["default_branch"], "archived": r["archived"], "updated": r["updated_at"][:10], "description": r.get("description") or "", "url": r["html_url"]})
        return {"items": items, "total": data.get("total_count", 0)}
    except Exception as e:
        log.warning(f"search_repos failed: {e}")
        return {"items": [], "total": 0}


@app.post("/api/repos")
async def create_repo(data: dict = Body()):
    client = _client()
    return client.post(f"/orgs/{_org()}/repos", json=data)


@app.patch("/api/repos/{name}")
async def update_repo(name: str, data: dict = Body()):
    client = _client()
    return client.patch(f"/repos/{_org()}/{name}", json=data)


@app.delete("/api/repos/{name}")
async def delete_repo(name: str):
    client = _client()
    client.delete(f"/repos/{_org()}/{name}")
    return {"ok": True}


# ─── PRs API ───

@app.get("/api/repos/{name}/pulls")
async def list_prs(name: str, state: str = "open", page: int = 1, per_page: int = 30):
    client = _client()
    prs = []
    try:
        for p in client.paginate(f"/repos/{_org()}/{name}/pulls", params={"state": state, "per_page": per_page, "page": page}):
            prs.append({"number": p["number"], "title": p["title"], "author": p["user"]["login"], "state": p["state"], "branch": p["head"]["ref"], "base": p["base"]["ref"], "draft": p["draft"], "created": p["created_at"][:10], "updated": p["updated_at"][:10], "url": p["html_url"], "labels": [l["name"] for l in p.get("labels", [])], "reviewers": [r["login"] for r in p.get("requested_reviewers", [])]})
            if len(prs) >= per_page:
                break
    except Exception as e:
        log.warning(f"list_prs({name}) failed: {e}")
    return {"items": prs, "page": page, "per_page": per_page, "has_more": len(prs) == per_page}


@app.post("/api/repos/{name}/pulls")
async def create_pr(name: str, data: dict = Body()):
    client = _client()
    return client.post(f"/repos/{_org()}/{name}/pulls", json=data)


@app.patch("/api/repos/{name}/pulls/{number}")
async def update_pr(name: str, number: int, data: dict = Body()):
    client = _client()
    return client.patch(f"/repos/{_org()}/{name}/pulls/{number}", json=data)


@app.put("/api/repos/{name}/pulls/{number}/merge")
async def merge_pr(name: str, number: int, data: dict = Body()):
    client = _client()
    return client.put(f"/repos/{_org()}/{name}/pulls/{number}/merge", json=data)


# ─── Issues API ───

@app.get("/api/repos/{name}/issues")
async def list_issues(name: str, state: str = "open", page: int = 1, per_page: int = 30):
    client = _client()
    issues = []
    try:
        for i in client.paginate(f"/repos/{_org()}/{name}/issues", params={"state": state, "per_page": per_page, "page": page}):
            if "pull_request" in i:
                continue
            issues.append({"number": i["number"], "title": i["title"], "author": i["user"]["login"], "state": i["state"], "created": i["created_at"][:10], "updated": i["updated_at"][:10], "labels": [l["name"] for l in i.get("labels", [])], "assignees": [a["login"] for a in i.get("assignees", [])], "comments": i["comments"], "url": i["html_url"]})
            if len(issues) >= per_page:
                break
    except Exception as e:
        log.warning(f"list_issues({name}) failed: {e}")
    return {"items": issues, "page": page, "per_page": per_page, "has_more": len(issues) == per_page}


@app.post("/api/repos/{name}/issues")
async def create_issue(name: str, data: dict = Body()):
    client = _client()
    return client.post(f"/repos/{_org()}/{name}/issues", json=data)


@app.patch("/api/repos/{name}/issues/{number}")
async def update_issue(name: str, number: int, data: dict = Body()):
    client = _client()
    return client.patch(f"/repos/{_org()}/{name}/issues/{number}", json=data)


# ─── Workflows & Runs API ───

@app.get("/api/repos/{name}/workflows")
async def list_workflows(name: str):
    client = _client()
    try:
        data = client.get(f"/repos/{_org()}/{name}/actions/workflows")
        return [{"id": w["id"], "name": w["name"], "state": w["state"], "path": w["path"]} for w in data.get("workflows", [])]
    except Exception as e:
        log.warning(f"list_workflows({name}) failed: {e}")
        return []


@app.get("/api/repos/{name}/runs")
async def list_runs(name: str, limit: int = 20):
    client = _client()
    try:
        data = client.get(f"/repos/{_org()}/{name}/actions/runs", params={"per_page": limit})
        runs = []
        for r in data.get("workflow_runs", [])[:limit]:
            runs.append({"id": r["id"], "name": r["name"], "status": r["status"], "conclusion": r.get("conclusion") or "", "branch": r.get("head_branch", ""), "event": r["event"], "actor": r["actor"]["login"], "started": (r.get("run_started_at") or "")[:16], "url": r["html_url"]})
        return runs
    except Exception as e:
        log.warning(f"list_runs({name}) failed: {e}")
        return []


@app.post("/api/repos/{name}/workflows/{workflow_id}/dispatch")
async def trigger_workflow(name: str, workflow_id: str, data: dict = Body()):
    client = _client()
    client.post(f"/repos/{_org()}/{name}/actions/workflows/{workflow_id}/dispatches", json=data)
    return {"ok": True}


@app.post("/api/repos/{name}/runs/{run_id}/rerun")
async def rerun_workflow(name: str, run_id: int):
    client = _client()
    client.post(f"/repos/{_org()}/{name}/actions/runs/{run_id}/rerun")
    return {"ok": True}


@app.post("/api/repos/{name}/runs/{run_id}/cancel")
async def cancel_run(name: str, run_id: int):
    client = _client()
    client.post(f"/repos/{_org()}/{name}/actions/runs/{run_id}/cancel")
    return {"ok": True}


# ─── Secrets & Variables API ───

@app.get("/api/repos/{name}/secrets")
async def list_secrets(name: str):
    client = _client()
    try:
        data = client.get(f"/repos/{_org()}/{name}/actions/secrets")
        return [{"name": s["name"], "updated": s.get("updated_at", "")[:10]} for s in data.get("secrets", [])]
    except Exception as e:
        log.warning(f"list_secrets({name}) failed: {e}")
        return []


@app.get("/api/repos/{name}/variables")
async def list_variables(name: str):
    client = _client()
    try:
        data = client.get(f"/repos/{_org()}/{name}/actions/variables")
        return [{"name": v["name"], "value": v["value"], "updated": v.get("updated_at", "")[:10]} for v in data.get("variables", [])]
    except Exception as e:
        log.warning(f"list_variables({name}) failed: {e}")
        return []


# ─── Teams API ───

@app.get("/api/teams")
async def list_teams():
    client = _client()
    teams = []
    try:
        for t in client.paginate(f"/orgs/{_org()}/teams"):
            teams.append({"name": t["name"], "slug": t["slug"], "privacy": t.get("privacy", ""), "members": t.get("members_count", 0)})
    except Exception as e:
        log.warning(f"list_teams failed: {e}")
    return teams


# ─── Pipeline overview ───

@app.get("/api/pipelines")
async def pipeline_overview(limit: int = 30):
    client = _client()
    repos = []
    for r in client.paginate(f"/orgs/{_org()}/repos", params={"per_page": 100, "sort": "pushed"}):
        repos.append(r)
        if len(repos) >= limit:
            break

    pipelines = []
    for repo in repos:
        try:
            data = client.get(f"/repos/{repo['full_name']}/actions/runs", params={"per_page": 1})
            runs = data.get("workflow_runs", [])
            if runs:
                r = runs[0]
                pipelines.append({"repo": repo["name"], "workflow": r["name"], "status": r["status"], "conclusion": r.get("conclusion") or "pending", "branch": r.get("head_branch", ""), "actor": r["actor"]["login"], "started": (r.get("run_started_at") or "")[:16], "url": r["html_url"]})
        except Exception:
            pass
    return pipelines


# ─── Compliance API ───

@app.get("/api/compliance")
async def compliance_check(page: int = 1, per_page: int = 20):
    client = _client()
    org = _org()
    repos = []
    for r in client.paginate(f"/orgs/{org}/repos", params={"per_page": per_page, "sort": "pushed", "page": page}):
        repos.append(r)
        if len(repos) >= per_page:
            break

    results = []
    for repo in repos:
        branch = repo["default_branch"]
        try:
            bp = client.get(f"/repos/{repo['full_name']}/branches/{branch}/protection")
            reviews = bp.get("required_pull_request_reviews", {})
            review_count = reviews.get("required_approving_review_count", 0) if reviews else 0
            dismiss_stale = reviews.get("dismiss_stale_reviews", False) if reviews else False
            require_owners = reviews.get("require_code_owner_reviews", False) if reviews else False
            status_checks = bp.get("required_status_checks", {})
            status_strict = status_checks.get("strict", False) if status_checks else False
            status_contexts = status_checks.get("contexts", []) if status_checks else []
            enforce_admins = bp.get("enforce_admins", {}).get("enabled", False) if bp.get("enforce_admins") else False
            linear_history = bp.get("required_linear_history", {}).get("enabled", False) if bp.get("required_linear_history") else False
            force_push = bp.get("allow_force_pushes", {}).get("enabled", False) if bp.get("allow_force_pushes") else False
            deletions = bp.get("allow_deletions", {}).get("enabled", False) if bp.get("allow_deletions") else False
            results.append({
                "repo": repo["name"], "branch": branch, "protected": True,
                "reviews_required": review_count, "dismiss_stale_reviews": dismiss_stale,
                "require_code_owners": require_owners,
                "status_checks": bool(status_checks), "status_strict": status_strict,
                "status_contexts": status_contexts,
                "enforce_admins": enforce_admins, "linear_history": linear_history,
                "allow_force_push": force_push, "allow_deletions": deletions,
            })
        except Exception:
            results.append({
                "repo": repo["name"], "branch": branch, "protected": False,
                "reviews_required": None, "dismiss_stale_reviews": False,
                "require_code_owners": False,
                "status_checks": False, "status_strict": False, "status_contexts": [],
                "enforce_admins": False, "linear_history": False,
                "allow_force_push": False, "allow_deletions": False,
            })
    return {"items": results, "page": page, "per_page": per_page, "has_more": len(repos) == per_page}


# ─── Search ───

@app.get("/api/search")
async def search(q: str, type: str = "code"):
    client = _client()
    org = _org()
    query = f"{q} org:{org}" if org else q
    if type == "code":
        return client.get("/search/code", params={"q": query, "per_page": 20})
    elif type == "repos":
        return client.get("/search/repositories", params={"q": query, "per_page": 20})
    elif type == "issues":
        return client.get("/search/issues", params={"q": query + " is:issue", "per_page": 20})
    elif type == "prs":
        return client.get("/search/issues", params={"q": query + " is:pr", "per_page": 20})
    return {"items": []}


# ─── Server launcher ───

def start_server(port: int = 8787, open_browser: bool = True):
    import webbrowser
    import threading
    import signal
    import sys
    import uvicorn

    url = f"http://127.0.0.1:{port}"

    def handle_exit(sig, frame):
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


# Mount static AFTER all routes are defined (so it doesn't shadow them)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
