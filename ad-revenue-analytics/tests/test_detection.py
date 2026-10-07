import numpy as np
import pandas as pd
import pytest

from detection import alert_events, match_events, robust_zscore, rolling_zscore, summarise


def hours(n: int, start: str = "2011-07-01") -> pd.Series:
    return pd.Series(pd.date_range(start, periods=n, freq="h"))


def test_rolling_zscore_uses_only_the_past():
    values = pd.Series([1.0, 2.0, 1.0, 2.0, 1.0, 2.0, 50.0, 1.0, 2.0, 1.0])
    scores = rolling_zscore(values, window=4)
    assert scores.iloc[:4].isna().all()            # not enough history yet
    assert scores.iloc[6] > 10                     # the spike stands out against the past
    unspiked = rolling_zscore(values.where(values.index != 6, 1.0), window=4)
    pd.testing.assert_series_equal(scores.iloc[:6], unspiked.iloc[:6])  # the future does not leak back


def test_robust_zscore_ignores_past_spikes_and_constant_history():
    noisy = pd.Series(np.r_[np.tile([1.0, 1.2, 0.8], 8), 1.0])
    with_past_spike = noisy.copy()
    with_past_spike.iloc[5] = 100.0
    assert abs(robust_zscore(noisy, 24).iloc[-1] - robust_zscore(with_past_spike, 24).iloc[-1]) < 1e-9
    constant = pd.Series([1.0] * 25)
    assert np.isnan(robust_zscore(constant, 24).iloc[-1])  # no spread, no score, no alert


def test_alert_events_merge_close_alerts_and_split_on_gaps():
    timestamps = hours(12)
    alerts = pd.Series([0, 1, 1, 0, 1, 0, 0, 0, 0, 1, 1, 0], dtype=bool)
    events = alert_events(timestamps, alerts, max_gap_hours=3)
    assert len(events) == 2
    assert events.loc[0, "start"] == timestamps[1] and events.loc[0, "end"] == timestamps[4]
    assert events.loc[1, "start"] == timestamps[9]


def test_alert_events_without_alerts():
    assert alert_events(hours(5), pd.Series([False] * 5)).empty


def test_match_events_counts_true_events_and_detected_windows():
    t = hours(48)
    events = pd.DataFrame({"start": [t[5], t[30]], "end": [t[7], t[31]]})
    windows = pd.DataFrame({"window_start": [t[6], t[40]], "window_end": [t[10], t[45]]})
    assert match_events(events, windows) == {"events": 2, "true_events": 1, "windows": 2, "detected_windows": 1}


def test_summarise_pools_counts():
    counts = pd.DataFrame({"events": [4, 0], "true_events": [2, 0], "windows": [2, 2], "detected_windows": [1, 1]})
    result = summarise(counts)
    assert result["precision"] == 0.5 and result["recall"] == 0.5 and result["f1"] == pytest.approx(0.5)
    assert result["false_events"] == 2
