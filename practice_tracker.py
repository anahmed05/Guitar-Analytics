"""
Guitar Practice Tracker  (Step 3 of the Guitar Analytics project)
-----------------------------------------------------------------
Log each practice session, then chart your progress.

The key metric is CHORD CHANGES PER MINUTE: set a 60-second timer, switch
back and forth between two chords (e.g. G and C), and count clean changes.
It's the standard beginner drill and it's easy to measure.

Run:
  python practice_tracker.py log       # add today's session (asks questions)
  python practice_tracker.py report    # print stats + save progress charts

Data is saved in two small CSV files (open them in Excel any time):
  sessions.csv       - one row per session: date, minutes, new shapes, notes
  chord_changes.csv  - one row per drill: date, chord pair, changes per minute
"""

import os
import sys
from datetime import date

import pandas as pd
import matplotlib.pyplot as plt

SESSIONS_FILE = "sessions.csv"
CHANGES_FILE = "chord_changes.csv"

# Fixed colors so each chord pair keeps the same color on every chart
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
           "#e87ba4", "#008300", "#6250d6", "#e34948"]
INK, MUTED, GRID, BG = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


# ---------------------------------------------------------------------
# 1. LOGGING A SESSION
# ---------------------------------------------------------------------

def append_rows(path, rows):
    """Add rows to a CSV, creating it (with headers) the first time."""
    df = pd.DataFrame(rows)
    df.to_csv(path, mode="a", index=False, header=not os.path.exists(path))


def ask(prompt, default=""):
    answer = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    return answer or default


def log_session():
    print("New practice session (press Enter to accept the [default])\n")
    day = ask("Date (YYYY-MM-DD)", str(date.today()))
    minutes = int(ask("Minutes practiced", "30"))

    print("\nChord change drills: enter like  G-C 32, Am-Em 40")
    print("(pair, then how many clean changes in 60 seconds; blank to skip)")
    drills_text = ask("Drills")

    new_shapes = ask("\nNew shapes learned today, space-separated (blank if none)")
    notes = ask("Notes (songs worked on, what felt hard)")

    append_rows(SESSIONS_FILE, [{
        "date": day, "minutes": minutes,
        "new_shapes": new_shapes, "notes": notes,
    }])

    drills = []
    for item in drills_text.split(","):
        parts = item.split()
        if len(parts) == 2:
            pair = "-".join(sorted(parts[0].split("-")))   # C-G same as G-C
            drills.append({"date": day, "pair": pair,
                           "changes_per_min": int(parts[1])})
    if drills:
        append_rows(CHANGES_FILE, drills)

    print(f"\nSaved: {minutes} min, {len(drills)} drill(s) on {day}.")


# ---------------------------------------------------------------------
# 2. REPORT: stats + charts
# ---------------------------------------------------------------------

def style(ax, title):
    ax.set_facecolor(BG)
    ax.set_title(title, loc="left", fontsize=12, color=INK, pad=12)
    ax.grid(axis="y", color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, length=0)


def report():
    if not os.path.exists(SESSIONS_FILE):
        print("No sessions yet. Run:  python practice_tracker.py log")
        return

    sessions = pd.read_csv(SESSIONS_FILE, parse_dates=["date"]).fillna("")
    shapes_known = sorted({s for row in sessions["new_shapes"]
                           for s in str(row).split()})

    print(f"Sessions logged:   {len(sessions)}")
    print(f"Total practice:    {sessions['minutes'].sum() / 60:.1f} hours")
    print(f"Shapes known ({len(shapes_known)}): {' '.join(shapes_known) or '-'}")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5), dpi=150)
    fig.patch.set_facecolor(BG)

    # Chart 1: minutes practiced per week
    weekly = sessions.set_index("date")["minutes"].resample("W-MON",
                                                            label="left").sum()
    ax1.bar(weekly.index.strftime("%b %d"), weekly.values,
            color=PALETTE[0], width=0.6)
    style(ax1, "Minutes practiced per week")
    ax1.set_xlabel("Week starting", color=MUTED)
    ax1.tick_params(axis="x", rotation=45)

    # Chart 2: chord change speed over time, one line per pair
    if os.path.exists(CHANGES_FILE):
        changes = pd.read_csv(CHANGES_FILE, parse_dates=["date"])
        # Best score per pair per day
        best = changes.groupby(["pair", "date"])["changes_per_min"].max()

        print("\nChord change progress (first -> latest, changes/min):")
        pairs = sorted(changes["pair"].unique())     # fixed order = fixed color
        for i, pair in enumerate(pairs[:len(PALETTE)]):
            series = best.loc[pair]
            color = PALETTE[i]
            ax2.plot(series.index, series.values, color=color, linewidth=2,
                     marker="o", markersize=7, markeredgecolor=BG,
                     markeredgewidth=2, label=pair)
            ax2.annotate(pair, (series.index[-1], series.values[-1]),
                         textcoords="offset points", xytext=(8, 0),
                         va="center", fontsize=9, color=INK)
            print(f"  {pair:8s} {series.iloc[0]:>3} -> {series.iloc[-1]:>3}"
                  f"  ({series.iloc[-1] - series.iloc[0]:+d})")
        if len(pairs) > 1:
            ax2.legend(frameon=False, labelcolor=INK, loc="upper left")
        ax2.tick_params(axis="x", rotation=45)
        ax2.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%b %d"))
        ax2.set_ylim(bottom=0)
    style(ax2, "Chord changes per minute")

    fig.tight_layout()
    fig.savefig("practice_progress.png")
    print("\nSaved chart -> practice_progress.png")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "log":
        log_session()
    elif command == "report":
        report()
    else:
        print(__doc__)
