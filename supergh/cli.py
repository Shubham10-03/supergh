"""CLI entry point for supergh."""

import click

from supergh import __version__
from supergh.commands.auth import auth
from supergh.commands.config_cmd import config
from supergh.commands.repo import repo
from supergh.commands.pr import pr
from supergh.commands.issue import issue
from supergh.commands.workflow import workflow, run
from supergh.commands.release import release
from supergh.commands.secret import secret, variable
from supergh.commands.misc import label, milestone, org_cmd, team, gist
from supergh.commands.search import search, browse, status, ssh_key, gpg_key, cache_cmd, api, completion
from supergh.commands.alias import alias
from supergh.commands.codespace import codespace
from supergh.commands.project import project
from supergh.commands.ruleset import ruleset
from supergh.commands.setup import setup
from supergh.extras.pipeline import pipeline
from supergh.extras.report import report, audit, compliance, sync, bulk, drift


# Command categories for grouped help display
COMMAND_GROUPS = [
    ("CORE COMMANDS", [
        "auth", "repo", "pr", "issue", "release", "org",
        "project", "codespace", "gist", "browse",
    ]),
    ("GITHUB ACTIONS COMMANDS", [
        "workflow", "run", "cache", "secret", "variable",
    ]),
    ("ENTERPRISE COMMANDS", [
        "pipeline", "report", "audit", "compliance", "drift", "sync", "bulk",
    ]),
    ("ADDITIONAL COMMANDS", [
        "alias", "api", "config", "gui", "ruleset", "search", "label", "milestone",
        "team", "ssh-key", "gpg-key", "status", "completion",
    ]),
]


class GroupedGroup(click.Group):
    """Custom Click group that displays commands in categorized sections."""

    def format_help(self, ctx, formatter):
        """Write custom help output mimicking gh CLI style."""
        formatter.write("Work seamlessly with GitHub from the command line — plus enterprise superpowers.\n\n")
        formatter.write("USAGE\n")
        formatter.write("  sgh <command> <subcommand> [flags]\n\n")

        # Group commands
        all_listed = set()
        for group_name, cmd_names in COMMAND_GROUPS:
            formatter.write(f"{group_name}\n")
            for name in cmd_names:
                cmd = self.get_command(ctx, name)
                if cmd:
                    help_text = cmd.get_short_help_str(limit=60)
                    formatter.write(f"  {name + ':':<14} {help_text}\n")
                    all_listed.add(name)
            formatter.write("\n")

        # Any unlisted commands
        unlisted = [n for n in self.list_commands(ctx) if n not in all_listed]
        if unlisted:
            formatter.write("OTHER COMMANDS\n")
            for name in unlisted:
                cmd = self.get_command(ctx, name)
                if cmd:
                    help_text = cmd.get_short_help_str(limit=60)
                    formatter.write(f"  {name + ':':<14} {help_text}\n")
            formatter.write("\n")

        formatter.write("FLAGS\n")
        formatter.write("  --debug     Enable debug output (tokens masked)\n")
        formatter.write("  --help      Show help for command\n")
        formatter.write("  --version   Show sgh version\n\n")

        formatter.write("EXAMPLES\n")
        formatter.write("  $ sgh repo list\n")
        formatter.write("  $ sgh pr create -r my-repo --title \"Fix\" --head feature\n")
        formatter.write("  $ sgh pipeline status --limit 20\n")
        formatter.write("  $ sgh compliance check\n")
        formatter.write("  $ sgh ui\n\n")

        formatter.write("LEARN MORE\n")
        formatter.write("  Use `sgh <command> --help` for more information about a command.\n")
        formatter.write("  Config: ~/.supergh/config.toml\n")
        formatter.write("  Logs:   ~/.supergh/logs/sgh.log\n")


@click.group(cls=GroupedGroup, invoke_without_command=True)
@click.version_option(version=__version__, prog_name="sgh")
@click.option("--debug", is_flag=True, help="Enable debug output (tokens masked).")
@click.pass_context
def main(ctx, debug):
    """sgh — a superset GitHub CLI for enterprise workflows."""
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# Core commands
main.add_command(auth)
main.add_command(config)
main.add_command(repo)
main.add_command(pr)
main.add_command(issue)
main.add_command(workflow)
main.add_command(run)
main.add_command(release)
main.add_command(secret)
main.add_command(variable)
main.add_command(label)
main.add_command(milestone)
main.add_command(org_cmd, "org")
main.add_command(team)
main.add_command(gist)
main.add_command(search)
main.add_command(browse)
main.add_command(status)
main.add_command(ssh_key, "ssh-key")
main.add_command(gpg_key, "gpg-key")
main.add_command(cache_cmd, "cache")
main.add_command(api)
main.add_command(completion)

# New commands
main.add_command(alias)
main.add_command(codespace)
main.add_command(project)
main.add_command(ruleset)
main.add_command(setup)

# Superset commands
main.add_command(pipeline)
main.add_command(report)
main.add_command(audit)
main.add_command(compliance)
main.add_command(sync)
main.add_command(bulk)
main.add_command(drift)


# GUI command group
from supergh.commands.gui import gui
main.add_command(gui)


if __name__ == "__main__":
    main()
