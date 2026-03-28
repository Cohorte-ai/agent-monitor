# Metrics & Baselines

Real-time metrics computation and statistical baseline tracking.

---

## Metrics Engine

The metrics engine computes rolling-window metrics for each agent independently. Every time an event is recorded, the engine updates the relevant agent's metrics.

### Metric Definitions

| Metric | Computation | Default Window |
|--------|------------|---------------|
| `event_count` | Count of events within the window | 300s |
| `denial_rate` | `deny_count / guardrail_decision_count` | 300s |
| `cost_per_minute` | `sum(cost) / (window_seconds / 60)` | 300s |
| `avg_latency_ms` | `sum(latency_ms) / count_with_latency` | 300s |

### Rolling Window

The window is configured by `metrics.window_seconds`. Only events within the window contribute to the snapshot. Events older than the window are automatically excluded.

```yaml
metrics:
  window_seconds: 300  # 5 minutes
```

A shorter window (60s) makes metrics more responsive to recent changes but noisier. A longer window (600s) smooths out spikes but delays detection. 300 seconds is a good default for most use cases.

### MetricSnapshot

```python
snap = monitor.get_metrics("sales-agent")
print(snap.event_count)       # 42
print(snap.denial_rate)       # 0.15 (15%)
print(snap.cost_per_minute)   # 0.03 ($0.03/min)
print(snap.avg_latency_ms)    # 287.5
```

If no events exist for the agent, all metrics return zero.

---

## Baselines (Welford's Algorithm)

The baseline tracker maintains running statistics for each (agent, metric) pair using **Welford's online algorithm**. This is an incremental algorithm that computes mean and standard deviation without storing historical values.

### Why Welford's?

Traditional approaches require storing all historical values to compute statistics. For a monitoring system that processes thousands of events per second, that's too much memory. Welford's algorithm maintains just three values: `count`, `mean`, and `M2` (sum of squared differences from the mean).

### The Algorithm

On each update:

```
count += 1
delta = value - mean
mean += delta / count
delta2 = value - mean
M2 += delta * delta2

variance = M2 / count
stddev = sqrt(variance)
```

This is numerically stable and runs in O(1) time and O(1) space per update.

### Z-Score

The z-score measures how many standard deviations a value is from the mean:

```
z = (value - mean) / stddev
```

| Z-Score | Interpretation |
|---------|---------------|
| < 1.0 | Normal |
| 1.0 - 2.0 | Slightly unusual |
| 2.0 - 3.0 | Unusual |
| > 3.0 | Anomalous |
| > 4.0 | Highly anomalous |

### Min Samples

Z-scores are only computed after `min_samples` data points have been collected. Before that, `z_score()` returns `None`. This prevents false alerts during cold start.

```yaml
baselines:
  min_samples: 20  # Need at least 20 data points
```

### Zero Standard Deviation

When all values are identical, stddev is zero and z-score is undefined. The tracker handles this gracefully -- returning `None` or `0.0` instead of dividing by zero.

### Persistence

Baselines can be saved to disk and loaded on restart:

```yaml
baselines:
  save_path: "/var/lib/agent-monitor/baselines.json"
```

This means your baselines survive restarts. After a restart, anomaly detection works immediately instead of waiting for `min_samples` new data points.

### Using the Tracker Directly

```python
from theaios.agent_monitor.baselines import BaselineTracker

tracker = BaselineTracker(min_samples=20)

# Feed values
for value in metric_values:
    tracker.update("agent-name", "metric-name", value)

# Get baseline
baseline = tracker.get_baseline("agent-name", "metric-name")
print(f"Mean: {baseline['mean']:.2f}")
print(f"StdDev: {baseline['stddev']:.2f}")

# Compute z-score
z = tracker.z_score("agent-name", "metric-name", new_value)
if z is not None and z > 3.0:
    print("Anomaly detected!")
```

---

## How Metrics Feed into Anomaly Detection

The flow is:

1. Event arrives -> MetricsEngine computes snapshot
2. Snapshot values feed into BaselineTracker (update running statistics)
3. AnomalyDetector computes z-scores against baselines
4. If z-score exceeds threshold -> alert is dispatched

This happens on every `monitor.record()` call, with negligible overhead.
