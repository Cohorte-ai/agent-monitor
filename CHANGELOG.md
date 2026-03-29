# Changelog

All notable changes to theaios-agent-monitor will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-03-29

### Security

- SSRF protection on webhook alerts: blocks private IPs, loopback, link-local, non-HTTP schemes
- Atomic writes for kill switch state persistence (tempfile + replace)
- JSON structure validation when loading kill state from disk
- Config structural validation before env var interpolation

## [0.1.0] - 2026-03-28

### Added

- **Core engine** — full monitoring pipeline: event recording, metrics computation, baseline tracking, anomaly detection, kill switch evaluation, alert dispatch, and compliance export
- **YAML configuration** — declarative config format (`monitor.yaml`) with validation, environment variable interpolation (`${VAR}`), and typed parsing into `MonitorConfig`
- **Event model** — five event types: `llm_call`, `tool_call`, `guardrail_decision`, `error`, `custom`, with freeform `data` dict and optional `session_id`
- **EventStore** — in-memory append-only event log with filtering by agent, event_type, and timestamp, tail queries, count, prune, and clear
- **MetricsEngine** — rolling window metrics computation: `event_count`, `denial_rate`, `cost_per_minute`, `avg_latency_ms`, configurable window size
- **BaselineTracker** — Welford's online algorithm for running mean and standard deviation, z-score computation, min_samples guard, save/load persistence
- **AnomalyDetector** — z-score threshold rules with cooldown, wildcard agent matching, per-metric evaluation, alert generation
- **KillSwitch** — three-level kill (agent, session, global), manual kill/revive, automatic kill policies on metric thresholds, save/load persistence
- **AlertDispatcher** — multi-channel alert delivery: console (stderr), file (JSONL), webhook (HTTP POST)
- **ComplianceExporter** — three export formats: SOC 2 (with controls), GDPR (with data subjects), JSON (generic), filtering by agent, time range
- **GuardrailsMonitor adapter** — bridges theaios-guardrails decisions into the monitoring pipeline, auto-records `guardrail_decision` events
- **CLI** (`agent-monitor`) — commands for `version`, `validate`, `inspect`, `record`, `metrics`, `kill`, `revive`, `export`
- **Type safety** — enums for `EventType`, `Severity`, `MetricName`, `KillAction`, with validation sets `VALID_EVENT_TYPES`, `VALID_SEVERITIES`, `VALID_METRICS`, `VALID_KILL_ACTIONS`
- ~120 unit tests across types, config, events, metrics, baselines, anomaly detection, kill switch, alerts, compliance, engine, guardrails adapter, and end-to-end integration
- CI pipeline: lint, typecheck, test (Python 3.10-3.13), build verification
- MkDocs Material documentation site with 10 pages
- Example configs (basic + enterprise) and 4 runnable Python examples
- End-to-end test guide with 20 manual test steps
- PEP 561 compliant (`py.typed` marker)

### Dependencies

- `pyyaml>=6.0` — YAML parsing
- `click>=8.0` — CLI framework
- `rich>=13.0` — console output formatting

### Optional Dependencies

- `theaios-guardrails>=0.1` — guardrails adapter integration
- `opentelemetry-api>=1.20`, `opentelemetry-sdk>=1.20` — OTel export
- `httpx>=0.27` — webhook alert channel

[0.1.0]: https://github.com/Cohorte-ai/agent-monitor/releases/tag/v0.1.0
