# Generate Configs with AI

You can use any LLM (Claude, ChatGPT, Gemini, etc.) to generate monitor.yaml configs that are fully compatible with this library. Copy-paste one of the prompts below, answer the follow-up questions, and get a production-ready YAML file.

---

## Prompt 1: Full Config from Scratch

Use this when starting from zero. The AI will ask about your agents, risks, and compliance needs, then generate a complete config.

````
I need you to generate a monitor.yaml config file for the theaios-agent-monitor library. This config will govern how AI agent behavior is monitored, baselined, and controlled.

Before generating, ask me about:
1. What AI agents do we have? (names, roles, what they do)
2. What are the biggest risks? (cost spikes, unauthorized actions, data leaks, errors)
3. What compliance frameworks apply? (SOC 2, GDPR, HIPAA, none)
4. What alert channels do we need? (console for dev, file for audit, webhook for Slack/PagerDuty)
5. What cost thresholds should trigger auto-kill? (e.g., $5/min, $1/min)

Then generate a YAML file following this exact specification:

```yaml
version: "1.0"                              # Required. Always "1.0".

metadata:                                   # Optional. Human-readable metadata.
  name: string                              # Monitor name
  description: string                       # What this config monitors
  author: string                            # Config owner

variables:                                  # Optional. Shared key-value pairs.
  key: value                                # Referenced in string values as ${key}

agents:                                     # Optional. Per-agent tracking config.
  agent-name:                               # Agent identifier (matches event.agent)
    enabled: true                           # Enable/disable tracking for this agent
    event_types:                            # Only track these event types (empty = all)
      - action
      - denial
    tags:                                   # Labels for filtering
      - production

storage:                                    # Optional. Event storage settings.
  path: .agent_monitor/events.jsonl         # Path to JSONL event store
  retention_days: 90                        # Days to retain events (>= 1)

metrics:                                    # Optional. Metrics engine settings.
  default_window_seconds: 300               # Default rolling window (5 min)
  max_window_seconds: 3600                  # Maximum window size (1 hour)

baselines:                                  # Optional. Statistical baseline tracking.
  enabled: true                             # Enable baseline computation
  min_samples: 30                           # Min data points before z-scores work
  metrics:                                  # Which metrics to track baselines for
    - denial_rate
    - error_count
    - cost_per_minute
    - avg_latency_ms
  storage_path: .agent_monitor/baselines.json  # Persistence path

anomaly_detection:                          # Optional. Z-score anomaly detection.
  enabled: true
  rules:
    - name: unique-rule-name                # Required. Unique identifier.
      metric: denial_rate                   # Required. Metric to monitor.
      z_threshold: 3.0                      # Z-score threshold (default 3.0)
      severity: high                        # critical | high | medium | low
      cooldown_seconds: 300                 # Min seconds between repeated alerts
      condition: ""                         # Optional condition expression

kill_switch:                                # Optional. Automatic kill switch policies.
  enabled: true
  state_path: .agent_monitor/kill_state.json  # Persistence path
  policies:
    - name: unique-policy-name              # Required. Unique identifier.
      metric: cost_per_minute               # Required. Metric to evaluate.
      operator: ">"                         # Required. >, <, >=, <=, ==
      threshold: 5.0                        # Required. Trigger value.
      action: kill_agent                    # kill_agent | kill_session | kill_global
      severity: critical                    # Alert severity for the kill
      message: ""                           # Optional custom message

alerts:                                     # Optional. Alert dispatch channels.
  channels:
    - type: console                         # Print to stderr (dev/debug)
      enabled: true
      min_severity: low                     # Minimum severity to show

    - type: file                            # Append JSONL to file (audit trail)
      path: .agent_monitor/alerts.jsonl     # Required for file channels
      min_severity: medium

    - type: webhook                         # HTTP POST (Slack, PagerDuty, etc.)
      url: "${ALERT_WEBHOOK_URL}"           # Required for webhook channels
      headers:                              # Optional HTTP headers
        Authorization: "Bearer ${TOKEN}"
      min_severity: high
```

Valid event types: action, guardrail_trigger, denial, approval_request, approval_response, cost, error, session_start, session_end

Valid metrics: event_count, action_count, denial_count, denial_rate, approval_count, approval_rate, error_count, cost_total, cost_per_minute, avg_latency_ms

Valid severities: critical, high, medium, low

Valid kill actions: kill_agent, kill_session, kill_global

Valid alert channel types: console, file, webhook

Important rules for generation:
- Every anomaly rule must have a unique name and a valid metric
- Every kill policy must have a unique name, valid metric, valid operator, and valid action
- Use z_threshold (not z_score_threshold) for anomaly rules
- Use operator field in kill policies (not just threshold comparison)
- Use state_path (not persistence_path) for kill switch persistence
- Use storage_path (not save_path) for baseline persistence
- Use default_window_seconds and max_window_seconds (not window_seconds or tracked)
- Use variables for values that might change (webhook URLs, thresholds, paths)
- Always include at least one alert channel
- Set reasonable cost thresholds — $5/min is a good starting default for auto-kill
- Enable baseline tracking with min_samples: 30 for production
````

---

## Prompt 2: Add Rules to an Existing Config

Use this when you already have a config and want to extend it.

````
I have an existing theaios-agent-monitor config. I need to add new monitoring rules for [DESCRIBE YOUR NEED].

Here is my current config:

```yaml
[PASTE YOUR CURRENT YAML HERE]
```

Generate additional anomaly_detection rules and/or kill_switch policies following the same format. For each new rule/policy, include:
- A unique name (no duplicates with existing rules)
- A valid metric (event_count, action_count, denial_count, denial_rate, approval_count, approval_rate, error_count, cost_total, cost_per_minute, avg_latency_ms)
- For anomaly rules: z_threshold (float), severity, cooldown_seconds
- For kill policies: operator (>, <, >=, <=, ==), threshold (float), action (kill_agent, kill_session, kill_global), severity

Also tell me if any existing rules should be modified to work well with the new ones.
````

---

## Prompt 3: Industry-Specific Config Starter

Use this to generate a config tailored to a specific industry.

````
Generate a complete theaios-agent-monitor config YAML file for a [INDUSTRY] company.

The company:
- Industry: [e.g., healthcare, financial services, legal, consulting, e-commerce]
- Size: [e.g., 50 employees, 500 employees]
- AI agents: [e.g., customer support agent, internal assistant, data analyst agent]
- Key regulations: [e.g., HIPAA, SOC 2, GDPR, PCI-DSS]

Generate a production-ready YAML config that includes:

1. **Agent tracking** for each agent with appropriate event_types and tags
2. **Storage** with appropriate retention (regulated industries need longer retention)
3. **Baselines** with appropriate min_samples for the expected event volume
4. **Anomaly rules**: cost spikes, denial rate anomalies, latency anomalies, error rate anomalies
5. **Kill policies**: auto-kill on extreme cost, auto-kill on extreme error rate
6. **Alert channels**: console for dev, file for audit, webhook placeholder for ops

Use this YAML format:
- version: "1.0"
- Valid event types: action, guardrail_trigger, denial, approval_request, approval_response, cost, error, session_start, session_end
- Valid metrics: event_count, action_count, denial_count, denial_rate, approval_count, approval_rate, error_count, cost_total, cost_per_minute, avg_latency_ms
- Anomaly rules use z_threshold (not z_score_threshold)
- Kill policies use operator field (>, <, >=, <=, ==)
- Severities: critical, high, medium, low
- Kill actions: kill_agent, kill_session, kill_global
- Use state_path for kill switch persistence, storage_path for baseline persistence

Include thorough anomaly detection rules with appropriate z_threshold values and cooldown periods.
````

---

## Prompt 4: Security Audit a Config

Use this to review an existing config for gaps.

````
Review this theaios-agent-monitor config for monitoring and safety gaps:

```yaml
[PASTE YOUR YAML HERE]
```

Check for:
1. **Missing cost protection** — is there a kill policy for cost_per_minute?
2. **Missing error detection** — is there an anomaly rule for error_count?
3. **Missing denial tracking** — is there an anomaly rule for denial_rate?
4. **Latency monitoring** — is there an anomaly rule for avg_latency_ms?
5. **Kill switch enabled** — is kill_switch.enabled set to true?
6. **Baseline coverage** — are the important metrics tracked in baselines.metrics?
7. **Alert coverage** — is there at least a console channel and a file channel?
8. **Persistence** — are state_path and storage_path configured for restart survival?
9. **Severity accuracy** — are severities assigned correctly? (critical = cost/security, high = data, medium = compliance, low = monitoring)
10. **Cooldown periods** — are cooldown_seconds reasonable? (300s = 5min is good default, critical rules might use 600s)

For each gap found, provide the exact YAML to add.

Valid metrics: event_count, action_count, denial_count, denial_rate, approval_count, approval_rate, error_count, cost_total, cost_per_minute, avg_latency_ms
Valid event types: action, guardrail_trigger, denial, approval_request, approval_response, cost, error, session_start, session_end
Anomaly rules use z_threshold. Kill policies use operator (>, <, >=, <=, ==).
````

---

## Tips for Better Results

1. **Be specific about your agents.** "We have a sales agent that reads CRM data and drafts emails, and a finance agent that queries databases" produces better configs than "we have some AI agents."

2. **Mention your regulations.** SOC 2, GDPR, HIPAA -- each implies specific retention periods, audit requirements, and alert thresholds.

3. **Provide cost context.** "Our agents cost about $0.01 per call, running about 100 calls per minute" helps the AI set realistic thresholds.

4. **Iterate.** Generate a first draft, run `agent-monitor -c config.yaml validate` to check syntax, then ask the AI to fix any issues.

---

## Validate AI-Generated Configs

Always validate before using in production:

```bash
# Check syntax and field validity
agent-monitor -c generated-config.yaml validate

# Inspect the parsed config (see all defaults and interpolated values)
agent-monitor -c generated-config.yaml inspect
```
