"""Command-line interface for the Agent Monitor."""

from __future__ import annotations

import json
import sys
import time

import click

from theaios.agent_monitor.config import ConfigError, load_config
from theaios.agent_monitor.reporting.console import (
    print_alerts_table,
    print_events_table,
    print_status,
)
from theaios.agent_monitor.reporting.json_export import export_json


@click.group()
@click.option(
    "-c",
    "--config",
    default="monitor.yaml",
    help="Path to monitor config file.",
    type=click.Path(),
)
@click.pass_context
def main(ctx: click.Context, config: str) -> None:
    """TheAIOS Agent Monitor — governance-first observability for AI agents."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config


@main.command()
def version() -> None:
    """Print version information."""
    click.echo("theaios-agent-monitor 0.1.0")


@main.command()
@click.pass_context
def validate(ctx: click.Context) -> None:
    """Validate the monitor config file."""
    config_path = ctx.obj["config_path"]
    try:
        cfg = load_config(config_path)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except ConfigError as e:
        click.echo(f"Validation failed:\n{e}", err=True)
        sys.exit(1)

    try:
        from rich.console import Console

        console = Console(stderr=True)
        console.print(f"[green]Config valid:[/green] {config_path}")
    except ImportError:
        click.echo(f"Config valid: {config_path}")

    # Print summary
    n_agents = len(cfg.agents)
    n_anomaly_rules = len(cfg.anomaly_detection.rules)
    n_kill_policies = len(cfg.kill_switch.policies)
    n_channels = len(cfg.alerts.channels)
    click.echo(
        f"  agents: {n_agents}  anomaly_rules: {n_anomaly_rules}  "
        f"kill_policies: {n_kill_policies}  alert_channels: {n_channels}"
    )


@main.command()
@click.pass_context
def inspect(ctx: click.Context) -> None:
    """Dump the parsed config as JSON."""
    config_path = ctx.obj["config_path"]
    try:
        cfg = load_config(config_path)
    except (FileNotFoundError, ConfigError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    from dataclasses import asdict

    click.echo(json.dumps(asdict(cfg), indent=2, default=str))


@main.command()
@click.option("-w", "--window", default=300, type=int, help="Window size in seconds.")
@click.option("-a", "--agent", default=None, help="Filter by agent name.")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
@click.pass_context
def status(ctx: click.Context, window: int, agent: str | None, as_json: bool) -> None:
    """Show current agent metrics and kill switch state."""
    config_path = ctx.obj["config_path"]
    try:
        cfg = load_config(config_path)
    except (FileNotFoundError, ConfigError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    from theaios.agent_monitor.engine import Monitor

    monitor = Monitor(cfg)

    if agent:
        snapshots = [monitor.get_metrics(agent, window)]
    else:
        snapshots = monitor.get_all_metrics(window)

    kill_state = monitor.kill_switch_engine.get_state()

    if as_json:
        click.echo(export_json(snapshots, kill_state))
    else:
        print_status(snapshots, kill_state)


@main.command()
@click.option("-n", "--limit", default=20, type=int, help="Number of events.")
@click.option("-a", "--agent", default=None, help="Filter by agent name.")
@click.option("-t", "--type", "event_type", default=None, help="Filter by event type.")
@click.option("--since", default=None, help="ISO timestamp filter.")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
@click.pass_context
def events(
    ctx: click.Context,
    limit: int,
    agent: str | None,
    event_type: str | None,
    since: str | None,
    as_json: bool,
) -> None:
    """Query stored agent events."""
    config_path = ctx.obj["config_path"]
    try:
        cfg = load_config(config_path)
    except (FileNotFoundError, ConfigError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    from theaios.agent_monitor.engine import Monitor

    monitor = Monitor(cfg)
    entries = monitor.get_events(since=since, agent=agent, event_type=event_type, limit=limit)

    if as_json:
        click.echo(json.dumps(entries, indent=2, default=str))
    else:
        print_events_table(entries)


@main.command()
@click.option("-n", "--limit", default=20, type=int, help="Number of alerts.")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
@click.pass_context
def alerts(ctx: click.Context, limit: int, as_json: bool) -> None:
    """Show recent alerts from the alert log."""
    config_path = ctx.obj["config_path"]
    try:
        cfg = load_config(config_path)
    except (FileNotFoundError, ConfigError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    # Read alerts from configured file channels
    alert_entries: list[dict[str, object]] = []
    for channel in cfg.alerts.channels:
        if channel.type == "file" and channel.path:
            from pathlib import Path

            alert_path = Path(channel.path)
            if alert_path.exists():
                with open(alert_path, encoding="utf-8") as f:
                    for line in f:
                        stripped = line.strip()
                        if stripped:
                            try:
                                alert_entries.append(json.loads(stripped))
                            except json.JSONDecodeError:
                                continue

    # Take last N
    alert_entries = alert_entries[-limit:]

    if as_json:
        click.echo(json.dumps(alert_entries, indent=2, default=str))
    else:
        print_alerts_table(alert_entries)


@main.command()
@click.argument("target")
@click.option("-r", "--reason", default="", help="Reason for kill.")
@click.option("--session", is_flag=True, help="Kill a session instead of an agent.")
@click.option("--global-kill", "global_kill", is_flag=True, help="Activate global kill.")
@click.pass_context
def kill(
    ctx: click.Context,
    target: str,
    reason: str,
    session: bool,
    global_kill: bool,
) -> None:
    """Kill an agent, session, or activate global kill."""
    config_path = ctx.obj["config_path"]
    try:
        cfg = load_config(config_path)
    except (FileNotFoundError, ConfigError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    from theaios.agent_monitor.kill_switch import KillSwitch

    ks = KillSwitch(cfg.kill_switch)
    ks.load()

    if global_kill:
        ks.kill_global(reason or f"Manual global kill at {time.time()}")
        click.echo("Global kill activated.")
    elif session:
        ks.kill_session(target, reason or f"Manual session kill: {target}")
        click.echo(f"Session '{target}' killed.")
    else:
        ks.kill_agent(target, reason or f"Manual agent kill: {target}")
        click.echo(f"Agent '{target}' killed.")

    ks.save()


@main.command()
@click.argument("target")
@click.option("--session", is_flag=True, help="Revive a session instead of an agent.")
@click.option("--global-revive", "global_revive", is_flag=True, help="Deactivate global kill.")
@click.pass_context
def revive(
    ctx: click.Context,
    target: str,
    session: bool,
    global_revive: bool,
) -> None:
    """Revive a killed agent, session, or deactivate global kill."""
    config_path = ctx.obj["config_path"]
    try:
        cfg = load_config(config_path)
    except (FileNotFoundError, ConfigError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    from theaios.agent_monitor.kill_switch import KillSwitch

    ks = KillSwitch(cfg.kill_switch)
    ks.load()

    if global_revive:
        ks.revive_global()
        click.echo("Global kill deactivated.")
    elif session:
        ks.revive(session_id=target)
        click.echo(f"Session '{target}' revived.")
    else:
        ks.revive(agent=target)
        click.echo(f"Agent '{target}' revived.")

    ks.save()


@main.command(name="export")
@click.option(
    "-f",
    "--format",
    "fmt",
    default="json",
    type=click.Choice(["soc2", "gdpr", "json"]),
    help="Compliance export format.",
)
@click.option("--since", default=None, help="ISO timestamp filter.")
@click.option("--until", default=None, help="ISO timestamp filter.")
@click.option("-a", "--agent", default=None, help="Filter by agent name.")
@click.pass_context
def export_cmd(
    ctx: click.Context,
    fmt: str,
    since: str | None,
    until: str | None,
    agent: str | None,
) -> None:
    """Export a compliance report."""
    config_path = ctx.obj["config_path"]
    try:
        cfg = load_config(config_path)
    except (FileNotFoundError, ConfigError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    from theaios.agent_monitor.events import EventStore

    store = EventStore(path=cfg.storage.path)

    from theaios.agent_monitor.compliance import ComplianceExporter

    exporter = ComplianceExporter(store)
    output = exporter.export(format=fmt, since=since, until=until, agent=agent)
    click.echo(output)
