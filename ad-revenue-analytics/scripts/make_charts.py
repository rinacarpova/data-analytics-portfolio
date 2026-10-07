"""Render the README charts from the dbt marts into output/.

Run after `dbt build`:
    python scripts/make_charts.py

Each chart is written in a light and a dark version; the README picks one with
<picture> and prefers-color-scheme.
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "src"))
from detection import alert_events, score_series  # noqa: E402

DATABASE = PROJECT_DIR / "data" / "ad_revenue.duckdb"
OUTPUT_DIR = PROJECT_DIR / "output"

THEMES = {
    "light": {
        "surface": "#fcfcfb",
        "ink": "#0b0b0b",
        "ink_secondary": "#52514e",
        "muted": "#898781",
        "grid": "#e1e0d9",
        "baseline": "#c3c2b7",
        "series": ["#2a78d6", "#eb6834", "#1baf7a"],
        "window": "#f0efec",
    },
    "dark": {
        "surface": "#1a1a19",
        "ink": "#ffffff",
        "ink_secondary": "#c3c2b7",
        "muted": "#898781",
        "grid": "#2c2c2a",
        "baseline": "#383835",
        "series": ["#3987e5", "#d95926", "#199e70"],
        "window": "#383835",
    },
}
EFFECTS = [("traffic_effect", "Traffic"), ("mix_effect", "Mix"), ("rate_effect", "Rate")]
HIGHLIGHT_DAYS = ["2019-06-21", "2019-06-22"]
# The detector and parameters the leave-one-exchange-out run picked for exchange-4.
EXAMPLE_SERIES = ("exchange-4", "CPM")
EXAMPLE_DETECTOR = ("rolling z-score", {"window": 168}, 6.0)

_installed_fonts = {font.name for font in matplotlib.font_manager.fontManager.ttflist}
plt.rcParams["font.family"] = [
    name for name in ("Segoe UI", "Helvetica Neue", "Arial") if name in _installed_fonts
] or ["DejaVu Sans"]


def load_daily_split():
    with duckdb.connect(str(DATABASE), read_only=True) as con:
        return con.sql("select * from mart_revenue_change_daily order by report_date").df()


def plot_revenue_change_split(daily, theme_name: str) -> Path:
    theme = THEMES[theme_name]
    fig, ax = plt.subplots(figsize=(10, 5.2), dpi=150)
    fig.patch.set_facecolor(theme["surface"])
    ax.set_facecolor(theme["surface"])

    x = range(len(daily))
    positive_bottom = [0.0] * len(daily)
    negative_bottom = [0.0] * len(daily)
    for (column, _), color in zip(EFFECTS, theme["series"]):
        values = daily[column].tolist()
        bottoms = [pos if v >= 0 else neg for v, pos, neg in zip(values, positive_bottom, negative_bottom)]
        # The edge in the surface colour is the 2px gap between stacked segments.
        ax.bar(x, values, bottom=bottoms, width=0.36, color=color,
               edgecolor=theme["surface"], linewidth=1, zorder=3)
        for i, v in enumerate(values):
            if v >= 0:
                positive_bottom[i] += v
            else:
                negative_bottom[i] += v

    ax.scatter(x, daily["revenue_delta"], s=42, color=theme["ink"],
               edgecolors=theme["surface"], linewidths=2, zorder=4)

    dates = daily["report_date"].astype(str).tolist()
    for day in HIGHLIGHT_DAYS:
        i = dates.index(day)
        row = daily.iloc[i]
        pct = 100 * row["revenue_delta"] / row["baseline_revenue"]
        ax.annotate(f"+{row['revenue_delta']:,.0f}\n(+{pct:.0f}%)", (i, positive_bottom[i]),
                    xytext=(0, 6), textcoords="offset points", ha="center", va="bottom",
                    fontsize=9, color=theme["ink"])

    ax.axhline(0, color=theme["baseline"], linewidth=1, zorder=2)
    ax.grid(axis="y", color=theme["grid"], linewidth=0.5, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.tick_params(colors=theme["muted"], labelsize=9, length=0)
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{d.day}\n{d:%a}" for d in daily["report_date"]])
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:+,.0f}" if v else "0"))
    ax.set_ylim(min(negative_bottom + daily["revenue_delta"].tolist()) * 1.25,
                max(positive_bottom) * 1.3)

    fig.text(0.06, 0.95, "What moved daily revenue against the same weekday of previous weeks",
             fontsize=13, fontweight="bold", color=theme["ink"])
    fig.text(0.06, 0.905, "Revenue change split into traffic, mix and rate effects, 15–30 June 2019",
             fontsize=10, color=theme["ink_secondary"])

    handles = [Patch(facecolor=c, label=label) for (_, label), c in zip(EFFECTS, theme["series"])]
    handles.append(Line2D([], [], marker="o", linestyle="", markersize=7, color=theme["ink"],
                          markeredgecolor=theme["surface"], label="Total change"))
    legend = ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0, 1.08), ncol=4,
                       frameon=False, fontsize=9, handlelength=1.2, columnspacing=1.6)
    for text in legend.get_texts():
        text.set_color(theme["ink_secondary"])

    fig.subplots_adjust(left=0.06, right=0.98, top=0.8, bottom=0.12)
    path = OUTPUT_DIR / f"revenue_change_split_{theme_name}.png"
    fig.savefig(path, facecolor=theme["surface"])
    plt.close(fig)
    return path


def load_detection_example():
    with duckdb.connect(str(DATABASE), read_only=True) as con:
        metrics = con.sql("select * from fct_exchange_metrics_hourly").df()
        windows = con.sql("select * from stg_nab__anomaly_windows").df()
    exchange, metric = EXAMPLE_SERIES
    detector, params, threshold = EXAMPLE_DETECTOR
    scored = score_series(metrics, detector, params)
    series = scored[(scored["exchange"] == exchange) & (scored["metric"] == metric)].reset_index(drop=True)
    series_windows = windows[(windows["exchange"] == exchange) & (windows["metric"] == metric)]
    return series, series_windows, series["score"].abs() > threshold


def plot_detection_example(series, windows, alerts, theme_name: str) -> Path:
    theme = THEMES[theme_name]
    fig, ax = plt.subplots(figsize=(10, 4.6), dpi=150)
    fig.patch.set_facecolor(theme["surface"])
    ax.set_facecolor(theme["surface"])

    for window in windows.itertuples():
        ax.axvspan(window.window_start, window.window_end, color=theme["window"], linewidth=0, zorder=1)
    ax.plot(series["observed_at"], series["metric_value"], color=theme["series"][0], linewidth=1,
            solid_joinstyle="round", zorder=3)
    ax.scatter(series.loc[alerts, "observed_at"], series.loc[alerts, "metric_value"], s=40,
               color=theme["series"][1], edgecolors=theme["surface"], linewidths=2, zorder=4)

    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.grid(axis="y", color=theme["grid"], linewidth=0.5, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.tick_params(colors=theme["muted"], labelsize=9, length=0)
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%d %b"))

    events = alert_events(series["observed_at"], alerts)
    caught = sum(any((e.start <= w.window_end) and (e.end >= w.window_start) for e in events.itertuples())
                 for w in windows.itertuples())
    fig.text(0.06, 0.94, f"Rolling z-score caught {caught} of {len(windows)} labelled anomalies on an ad exchange's CPM",
             fontsize=13, fontweight="bold", color=theme["ink"])
    fig.text(0.06, 0.895, "NAB exchange-4, hourly CPM (log scale), July–September 2011; alert when the hour is "
             "6 standard deviations from the previous week",
             fontsize=10, color=theme["ink_secondary"])
    handles = [
        Line2D([], [], color=theme["series"][0], linewidth=2, label="Hourly CPM"),
        Patch(facecolor=theme["window"], label="Labelled anomaly window"),
        Line2D([], [], marker="o", linestyle="", markersize=7, color=theme["series"][1],
               markeredgecolor=theme["surface"], label="Alert"),
    ]
    legend = ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0, 1.1), ncol=3,
                       frameon=False, fontsize=9, handlelength=1.4, columnspacing=1.6)
    for text in legend.get_texts():
        text.set_color(theme["ink_secondary"])

    fig.subplots_adjust(left=0.06, right=0.98, top=0.78, bottom=0.1)
    path = OUTPUT_DIR / f"detection_example_{theme_name}.png"
    fig.savefig(path, facecolor=theme["surface"])
    plt.close(fig)
    return path


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    daily = load_daily_split()
    example = load_detection_example()
    for theme_name in THEMES:
        for path in (plot_revenue_change_split(daily, theme_name), plot_detection_example(*example, theme_name)):
            print(f"done  {path.relative_to(PROJECT_DIR)}")


if __name__ == "__main__":
    main()
