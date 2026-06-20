<p align="center">
  <img src="assets/logo.png" alt="sgh" width="80">
</p>

# supergh (sgh)

A superset GitHub CLI for enterprise workflows. Everything `gh` does, plus cross-repo pipeline intelligence, org-wide reports, compliance checks, bulk operations, and a built-in web dashboard.

## Installation

### macOS / Linux

```bash
curl -fsSL https://raw.githubusercontent.com/<org>/supergh/main/install.sh | bash
```

### Windows (PowerShell)

```powershell
irm https://raw.githubusercontent.com/<org>/supergh/main/install.ps1 | iex
```

### Manual Download

Download the binary for your platform from [Releases](https://github.com/<org>/supergh/releases/latest):

| Platform | File |
|----------|------|
| macOS (Apple Silicon) | `sgh-macos-arm64` |
| macOS (Intel) | `sgh-macos-x86_64` |
| Linux (x86_64) | `sgh-linux-x86_64` |
| Windows | `sgh-windows-x86_64.exe` |

Then place it in your PATH and make it executable (`chmod +x sgh` on macOS/Linux).

## Authentication

```bash
sgh auth pat          # Personal Access Token (quickest)
sgh auth oauth        # OAuth device flow
sgh auth app          # GitHub App (for automation/CI)
sgh auth status       # Check current auth
```

## Usage

```bash
# Repos
sgh repo list
sgh repo view my-repo
sgh repo create new-repo --private

# Pull Requests
sgh pr list -r my-repo
sgh pr create -r my-repo --title "Fix" --head feature-branch
sgh pr merge 1 -r my-repo --method squash

# Issues
sgh issue list -r my-repo
sgh issue create -r my-repo --title "Bug report"
sgh issue close 42 -r my-repo

# Workflows & Pipelines
sgh workflow list -r my-repo
sgh run list -r my-repo
sgh run watch 12345 -r my-repo
sgh pipeline status --limit 20

# Reports & Export
sgh report repos --export repos.xlsx
sgh report prs --export open-prs.csv
sgh repo list --output json
sgh repo list --export repos.md

# Compliance & Auditing
sgh compliance check
sgh audit permissions
sgh audit access my-repo

# Bulk Operations
sgh bulk issue --repos "repo1,repo2" --title "Update deps"
sgh sync labels source-repo --targets repo1,repo2

# Web Dashboard
sgh ui                # Opens browser dashboard
```

## Configuration

Config: `~/.supergh/config.toml`
Logs: `~/.supergh/logs/sgh.log`

Tokens: OS keychain only (never on disk)

```bash
sgh config set core.default_org my-org
sgh config list
```

## Development

```bash
git clone <repo> && cd supergh
python -m pip install -e ".[ui,export,dev]"
python run.py --help
```

### Build from source

```bash
pip install pyinstaller
python build.py
# Output: dist/sgh (or dist/sgh.exe on Windows)
```

## License

MIT
