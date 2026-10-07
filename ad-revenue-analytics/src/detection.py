"""Anomaly detectors for hourly ad metrics and their evaluation against labelled windows.

Every detector is causal: the score of an hour uses only earlier observations, the way
a live alert would. A detector returns a score per observation; an alert fires when the
absolute score exceeds a threshold. Consecutive alerts are merged into alert events, and
events are matched to the labelled anomaly windows:

- precision = alert events that overlap a labelled window / all alert events
- recall    = labelled windows with at least one alert / all labelled windows
"""

from __future__ import annotations

from collections.abc import Callable
from itertools import product

import numpy as np
import pandas as pd

MAD_TO_STD = 1.4826  # scales the median absolute deviation to a standard deviation for normal data


def _mad(values: np.ndarray) -> float:
    return float(np.median(np.abs(values - np.median(values))))


def rolling_zscore(values: pd.Series, window: int) -> pd.Series:
    """Distance from the mean of the previous `window` observations, in standard deviations."""
    history = values.shift(1).rolling(window, min_periods=window)
    return (values - history.mean()) / history.std()


def robust_zscore(values: pd.Series, window: int) -> pd.Series:
    """Like the z-score, but with median and MAD, so past spikes do not inflate the scale."""
    history = values.shift(1).rolling(window, min_periods=window)
    scale = MAD_TO_STD * history.apply(_mad, raw=True)
    return (values - history.median()) / scale.replace(0, np.nan)


def seasonal_zscore(values: pd.Series, timestamps: pd.Series, days: int, window: int) -> pd.Series:
    """Distance from the median of the same hour over the previous `days` days, scaled by the
    robust spread of that distance over the previous `window` observations."""
    hour = timestamps.dt.hour
    expected = values.groupby(hour).transform(lambda s: s.shift(1).rolling(days, min_periods=days).median())
    residual = values - expected
    history = residual.shift(1).rolling(window, min_periods=window // 2)
    scale = MAD_TO_STD * history.apply(_mad, raw=True)
    return (residual - history.median()) / scale.replace(0, np.nan)


def level_shift_zscore(values: pd.Series, recent: int, window: int) -> pd.Series:
    """Mean of the last `recent` observations against the mean of the `window` observations
    before them. Single spikes average out; a sustained shift in level builds up."""
    recent_mean = values.rolling(recent, min_periods=recent).mean()
    history = values.shift(recent).rolling(window, min_periods=window)
    return (recent_mean - history.mean()) / (history.std() / np.sqrt(recent))


# name -> (score function of one series, parameter grid)
Detector = Callable[[pd.DataFrame, dict], pd.Series]
DETECTORS: dict[str, tuple[Detector, dict[str, list]]] = {
    "rolling z-score": (
        lambda series, p: rolling_zscore(series["metric_value"], p["window"]),
        {"window": [24, 72, 168]},
    ),
    "robust z-score": (
        lambda series, p: robust_zscore(series["metric_value"], p["window"]),
        {"window": [24, 72, 168]},
    ),
    "seasonal z-score": (
        lambda series, p: seasonal_zscore(series["metric_value"], series["observed_at"], p["days"], p["window"]),
        {"days": [3, 7], "window": [72, 168]},
    ),
    "level shift": (
        lambda series, p: level_shift_zscore(series["metric_value"], p["recent"], p["window"]),
        {"recent": [6, 12, 24], "window": [72, 168]},
    ),
}
THRESHOLDS = [3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 15.0, 20.0]


def alert_events(timestamps: pd.Series, alerts: pd.Series, max_gap_hours: float = 3) -> pd.DataFrame:
    """Merge alerting observations into events; a gap longer than `max_gap_hours` starts a new one."""
    fired = timestamps[alerts.fillna(False).astype(bool)].sort_values()
    if fired.empty:
        return pd.DataFrame({"start": pd.Series(dtype="datetime64[ns]"), "end": pd.Series(dtype="datetime64[ns]")})
    new_event = fired.diff().dt.total_seconds().div(3600).gt(max_gap_hours).cumsum()
    return fired.groupby(new_event.values).agg(["min", "max"]).set_axis(["start", "end"], axis=1).reset_index(drop=True)


def match_events(events: pd.DataFrame, windows: pd.DataFrame) -> dict[str, int]:
    """Count alert events that overlap a labelled window, and windows that got at least one alert."""
    overlaps = np.array([
        [(event.start <= window.window_end) and (event.end >= window.window_start) for window in windows.itertuples()]
        for event in events.itertuples()
    ], dtype=bool).reshape(len(events), len(windows))
    return {
        "events": len(events),
        "true_events": int(overlaps.any(axis=1).sum()),
        "windows": len(windows),
        "detected_windows": int(overlaps.any(axis=0).sum()),
    }


def summarise(counts: pd.DataFrame) -> dict[str, float]:
    """Pooled precision, recall and F1 from per-series counts."""
    events, true_events = counts["events"].sum(), counts["true_events"].sum()
    precision = true_events / events if events else 0.0
    recall = counts["detected_windows"].sum() / counts["windows"].sum()
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "alert_events": int(events),
        "false_events": int(events - true_events),
    }


def score_series(metrics: pd.DataFrame, detector: str, params: dict) -> pd.DataFrame:
    """Scores of one detector for every series, in time order."""
    score, _ = DETECTORS[detector]
    parts = []
    for _, series in metrics.groupby(["exchange", "metric"], sort=True):
        series = series.sort_values("observed_at").reset_index(drop=True)
        parts.append(series.assign(score=score(series, params)))
    return pd.concat(parts, ignore_index=True)


def evaluate(scored: pd.DataFrame, windows: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """Per-series event counts for a threshold on the absolute score."""
    rows = []
    for (exchange, metric), series in scored.groupby(["exchange", "metric"], sort=True):
        events = alert_events(series["observed_at"], series["score"].abs() > threshold)
        series_windows = windows[(windows["exchange"] == exchange) & (windows["metric"] == metric)]
        rows.append({"exchange": exchange, "metric": metric, **match_events(events, series_windows)})
    return pd.DataFrame(rows)


def grid(detector: str) -> list[dict]:
    _, param_grid = DETECTORS[detector]
    return [dict(zip(param_grid, values)) for values in product(*param_grid.values())]


def grid_counts(metrics: pd.DataFrame, windows: pd.DataFrame) -> pd.DataFrame:
    """Per-series counts for every detector, parameter set and threshold."""
    rows = []
    for detector in DETECTORS:
        for params in grid(detector):
            scored = score_series(metrics, detector, params)
            for threshold in THRESHOLDS:
                counts = evaluate(scored, windows, threshold)
                rows.append(counts.assign(detector=detector, params=str(params), threshold=threshold))
    return pd.concat(rows, ignore_index=True)


def cross_validate(counts: pd.DataFrame) -> pd.DataFrame:
    """Leave one exchange out: pick each detector's parameters and threshold by pooled F1 on the
    other exchanges, then score them on the held-out one. Returns one row per detector and fold."""
    keys = ["detector", "params", "threshold"]
    rows = []
    for held_out in sorted(counts["exchange"].unique()):
        train = counts[counts["exchange"] != held_out]
        test = counts[counts["exchange"] == held_out]
        train_scores = train.groupby(keys).apply(lambda g: pd.Series(summarise(g)), include_groups=False).reset_index()
        for detector, candidates in train_scores.groupby("detector"):
            best = candidates.sort_values(["f1", "precision"], ascending=False).iloc[0]
            chosen = test[(test["detector"] == detector) & (test["params"] == best["params"])
                          & (test["threshold"] == best["threshold"])]
            rows.append({"held_out": held_out, "detector": detector, "params": best["params"],
                         "threshold": best["threshold"], **chosen[["events", "true_events", "windows",
                                                                     "detected_windows"]].sum().to_dict()})
    return pd.DataFrame(rows)
