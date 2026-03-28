"""Rich terminal output for agent monitor status, events, and alerts."""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from theaios.agent_monitor.types import KillState, MetricSnapshot


def _format_timestamp(ts: float | object) -> str:
    """Format a unix timestamp as a human-readable string."""
    if isinstance(ts, (int, float)) and ts > 0:
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    return str(ts) if ts else "-"


def print_status(snapshots: list[MetricSnapshot], kill_state: KillState) -> None:
    """Print a Rich table of agent metrics and kill switch state."""
    try:
        from rich.console import Console
        from rich.table import Table

        console = Console(stderr=True)

        # Kill state banner
        if kill_state.global_kill:
            console.print("[bold red]GLOBAL KILL ACTIVE[/bold red]")
            reason = kill_state.reasons.get("global", "")
            if reason:
                console.print(f"  Reason: {reason}")

        if kill_state.killed_agents:
            console.print(
                f"[red]Killed agents:[/red] {', '.join(sorted(kill_state.killed_agents))}"
            )
        if kill_state.killed_sessions:
            console.print(
                f"[red]Killed sessions:[/red] {', '.join(sorted(kill_state.killed_sessions))}"
            )

        # Metrics table
        table = Table(title="Agent Metrics")
        table.add_column("Agent", style="cyan")
        table.add_column("Window (s)", justify="right")
        table.add_column("Events", justify="right")
        table.add_column("Actions", justify="right")
        table.add_column("Denials", justify="right")
        table.add_column("Denial Rate", justify="right")
        table.add_column("Approvals", justify="right")
        table.add_column("Errors", justify="right")
        table.add_column("Cost ($)", justify="right")
        table.add_column("$/min", justify="right")
        table.add_column("Avg Latency (ms)", justify="right")

        for snap in snapshots:
            killed = snap.agent in kill_state.killed_agents or kill_state.global_kill
            agent_display = f"[red]{snap.agent} (KILLED)[/red]" if killed else snap.agent

            denial_style = "red" if snap.denial_rate > 0.5 else ""
            error_style = "red" if snap.error_count > 0 else ""

            table.add_row(
                agent_display,
                str(snap.window_seconds),
                str(snap.event_count),
                str(snap.action_count),
                str(snap.denial_count),
                f"[{denial_style}]{snap.denial_rate:.2%}[/{denial_style}]"
                if denial_style
                else f"{snap.denial_rate:.2%}",
                str(snap.approval_count),
                f"[{error_style}]{snap.error_count}[/{error_style}]"
                if error_style
                else str(snap.error_count),
                f"{snap.cost_total:.4f}",
                f"{snap.cost_per_minute:.6f}",
                f"{snap.avg_latency_ms:.1f}",
            )

        console.print(table)

    except ImportError:
        # Fallback without Rich
        if kill_state.global_kill:
            print("GLOBAL KILL ACTIVE", file=sys.stderr)
        for snap in snapshots:
            print(
                f"{snap.agent}: events={snap.event_count} actions={snap.action_count} "
                f"denials={snap.denial_count} denial_rate={snap.denial_rate:.2%} "
                f"errors={snap.error_count} cost=${snap.cost_total:.4f} "
                f"avg_latency={snap.avg_latency_ms:.1f}ms",
                file=sys.stderr,
            )


def print_events_table(entries: list[dict[str, object]]) -> None:
    """Print a Rich table of agent events."""
    try:
        from rich.console import Console
        from rich.table import Table

        console = Console(stderr=True)

        table = Table(title="Agent Events")
        table.add_column("Timestamp", style="dim")
        table.add_column("Agent", style="cyan")
        table.add_column("Type")
        table.add_column("Session")
        table.add_column("User")
        table.add_column("Cost ($)", justify="right")
        table.add_column("Latency (ms)", justify="right")

        for entry in entries:
            event_type = str(entry.get("event_type", ""))
            type_style = ""
            if event_type == "denial":
                type_style = "red"
            elif event_type == "error":
                type_style = "bold red"
            elif event_type == "action":
                type_style = "green"

            type_display = (
                f"[{type_style}]{event_type}[/{type_style}]" if type_style else event_type
            )

            cost = entry.get("cost_usd")
            latency = entry.get("latency_ms")

            table.add_row(
                _format_timestamp(entry.get("timestamp", 0)),
                str(entry.get("agent", "")),
                type_display,
                str(entry.get("session_id", "") or "-"),
                str(entry.get("user", "") or "-"),
                f"{float(str(cost)):.4f}" if cost else "-",
                f"{float(str(latency)):.1f}" if latency else "-",
            )

        console.print(table)

    except ImportError:
        for entry in entries:
            print(
                f"{_format_timestamp(entry.get('timestamp', 0))} "
                f"{entry.get('agent', '')} {entry.get('event_type', '')}",
                file=sys.stderr,
            )


def print_alerts_table(entries: list[dict[str, object]]) -> None:
    """Print a Rich table of alerts."""
    try:
        from rich.console import Console
        from rich.table import Table

        console = Console(stderr=True)

        table = Table(title="Alerts")
        table.add_column("Timestamp", style="dim")
        table.add_column("Type")
        table.add_column("Agent", style="cyan")
        table.add_column("Severity")
        table.add_column("Message")

        for entry in entries:
            severity = str(entry.get("severity", ""))
            sev_style_map = {
                "critical": "bold red",
                "high": "red",
                "medium": "yellow",
                "low": "dim",
            }
            sev_style = sev_style_map.get(severity, "")
            sev_display = f"[{sev_style}]{severity}[/{sev_style}]" if sev_style else severity

            table.add_row(
                _format_timestamp(entry.get("timestamp", 0)),
                str(entry.get("type", "")),
                str(entry.get("agent", "")),
                sev_display,
                str(entry.get("message", "")),
            )

        console.print(table)

        if not entries:
            console.print("[dim]No alerts found.[/dim]")

    except ImportError:
        for entry in entries:
            print(
                f"{_format_timestamp(entry.get('timestamp', 0))} "
                f"[{entry.get('severity', '')}] {entry.get('message', '')}",
                file=sys.stderr,
            )
