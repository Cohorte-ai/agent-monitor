"""Alert dispatcher — routes alerts to configured channels."""

from __future__ import annotations

import ipaddress
import json
import sys
import time
import urllib.request
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlparse

from theaios.agent_monitor.types import (
    SEVERITY_ORDER,
    AlertConfig,
    AnomalyAlert,
)


def _validate_url(url: str) -> None:
    """Validate a URL to prevent SSRF attacks.

    Rejects non-HTTP(S) schemes and private/internal IP addresses.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Only http/https URLs allowed, got: {parsed.scheme}")
    hostname = parsed.hostname or ""
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            raise ValueError(f"Private/internal IP addresses not allowed: {hostname}")
    except ValueError as exc:
        # Re-raise our own ValueError (SSRF block), but ignore parse errors
        # (hostname is not an IP literal, which is fine)
        if "not allowed" in str(exc):
            raise


class AlertDispatcher:
    """Routes anomaly alerts and kill notifications to configured channels.

    Supports console (Rich stderr), file (JSONL), and webhook (stdlib
    urllib.request) channels. Each channel has a configurable minimum
    severity threshold.
    """

    def __init__(self, config: AlertConfig) -> None:
        self._config = config

    def _severity_passes(self, severity: str, min_severity: str) -> bool:
        """Check if a severity level meets the minimum threshold."""
        return SEVERITY_ORDER.get(severity, 3) <= SEVERITY_ORDER.get(min_severity, 3)

    def _dispatch_console(self, message: str, severity: str) -> None:
        """Dispatch an alert to the console using Rich."""
        try:
            from rich.console import Console

            console = Console(stderr=True)
            style_map = {
                "critical": "bold red",
                "high": "red",
                "medium": "yellow",
                "low": "dim",
            }
            style = style_map.get(severity, "")
            console.print(f"[{style}][ALERT][/{style}] [{style}]{message}[/{style}]")
        except ImportError:
            print(f"[ALERT] {message}", file=sys.stderr)

    def _dispatch_file(self, entry: dict[str, object], path: str) -> None:
        """Dispatch an alert to a JSONL file."""
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    def _dispatch_webhook(
        self,
        entry: dict[str, object],
        url: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Dispatch an alert via HTTP POST using stdlib urllib.request."""
        # Security: validate URL to prevent SSRF
        try:
            _validate_url(url)
        except ValueError:
            print(f"[ALERT] Blocked webhook to unsafe URL: {url}", file=sys.stderr)
            return

        payload = json.dumps(entry, default=str).encode("utf-8")
        req_headers = {"Content-Type": "application/json"}
        if headers:
            req_headers.update(headers)

        req = urllib.request.Request(
            url,
            data=payload,
            headers=req_headers,
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            # Alerting must never crash the hot path — log and continue
            print(f"[ALERT] Failed to dispatch webhook to {url}", file=sys.stderr)

    def dispatch(self, alert: AnomalyAlert) -> None:
        """Dispatch an anomaly alert to all qualifying channels."""
        entry: dict[str, object] = {
            "type": "anomaly",
            "timestamp": alert.timestamp or time.time(),
            **asdict(alert),
        }

        for channel in self._config.channels:
            if not channel.enabled:
                continue
            if not self._severity_passes(alert.severity, channel.min_severity):
                continue

            if channel.type == "console":
                self._dispatch_console(alert.message, alert.severity)
            elif channel.type == "file":
                self._dispatch_file(entry, channel.path)
            elif channel.type == "webhook":
                self._dispatch_webhook(entry, channel.url, channel.headers)

    def dispatch_kill(self, agent: str, reason: str, severity: str = "critical") -> None:
        """Dispatch a kill switch notification to all qualifying channels."""
        now = time.time()
        message = f"KILL SWITCH: agent='{agent}' — {reason}"
        entry: dict[str, object] = {
            "type": "kill",
            "timestamp": now,
            "agent": agent,
            "reason": reason,
            "severity": severity,
            "message": message,
        }

        for channel in self._config.channels:
            if not channel.enabled:
                continue
            if not self._severity_passes(severity, channel.min_severity):
                continue

            if channel.type == "console":
                self._dispatch_console(message, severity)
            elif channel.type == "file":
                self._dispatch_file(entry, channel.path)
            elif channel.type == "webhook":
                self._dispatch_webhook(entry, channel.url, channel.headers)
