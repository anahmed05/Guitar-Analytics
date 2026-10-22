"""
Guitar Chord Coverage Analysis  (Step 1 of the Guitar Analytics project)
-------------------------------------------------------------------------
Question: if a beginner learns chords in the smartest possible order,
how many popular songs can they play after each new chord?

Data: the Chordonomicon dataset (chord progressions for ~680k songs).
  Download "chordonomicon_v2.csv" from
  https://huggingface.co/datasets/ailsntua/Chordonomicon  (Files tab)
  and put it in the same folder as this script.

Run:
  pip install pandas matplotlib
  python chord_coverage.py                        # uses chordonomicon_v2.csv
  python chord_coverage.py my_file.csv --max 15   # other file / more chords

Outputs (saved next to the script):
  coverage_curve.png   - the headline chart
  learning_order.csv   - the chord order + % of songs playable at each step
"""

import argparse
import re
from collections import Counter

import pandas as pd
import matplotlib.pyplot as plt


# ---------------------------------------------------------------------
# 1. CLEANING: turn messy chord text into simple "beginner" chords
# ---------------------------------------------------------------------
# Songs list chords like "Cmaj7", "G/B", "Bbsus4". A beginner would just
# play C, G, and Bb, so we keep only the root note + major/minor.

# Same note, two spellings (e.g. A# and Bb). Pick the name guitarists use.
ENHARMONIC = {
    "Db": "C#", "D#": "Eb", "Gb": "F#", "G#": "Ab", "A#": "Bb",
    "Cb": "B", "Fb": "E", "E#": "F", "B#": "C",
}

CHORD_PATTERN = re.compile(r"^([A-G])([#b]?)(.*)$")


def simplify_chord(token):
    """'Cmaj7' -> 'C', 'Am7' -> 'Am', 'G/B' -> 'G', 'F#m' -> 'F#m'.
    Returns None for anything that isn't a chord (section tags, 'N.C.')."""
    token = token.split("/")[0]                     # drop the bass note
    match = CHORD_PATTERN.match(token)
    if not match:
        return None
    root = match.group(1) + match.group(2)
    root = ENHARMONIC.get(root, root)
    quality = match.group(3)
    # "m" means minor, but "maj" means major (Cmaj7 is a major chord)
    is_minor = quality.startswith("m") and not quality.startswith("maj")
    return root + ("m" if is_minor else "")


def song_chord_set(chord_text):
    """Full chord text for one song -> the set of simple chords it uses."""
    chords = set()
    for token in str(chord_text).split():
        if token.startswith("<"):                   # skip tags like <verse_1>
            continue
        chord = simplify_chord(token)
        if chord:
            chords.add(chord)
    return frozenset(chords)


# ---------------------------------------------------------------------
# 2. ANALYSIS: find the best order to learn chords
# ---------------------------------------------------------------------
# A song is "playable" once you know every chord in it.
# Greedy approach: at each step, learn the chord that makes the most
# new songs playable. (Ties go to the chord that appears in the most
# not-yet-playable songs, so early steps still pick useful chords.)

def best_learning_order(song_sets, max_chords):
    # Many songs use the exact same chord set (e.g. G C D Em), so we
    # count each unique set once with a weight. Much faster.
    set_counts = Counter(song_sets)
    total_songs = sum(set_counts.values())

    known = set()
    playable = 0
    results = []

    for step in range(1, max_chords + 1):
        new_songs = Counter()   # songs a chord would make playable now
        appears_in = Counter()  # songs (not yet playable) using that chord

        for chord_set, count in set_counts.items():
            missing = chord_set - known
            if not missing:
                continue                            # already playable
            for chord in missing:
                appears_in[chord] += count
            if len(missing) == 1:
                new_songs[next(iter(missing))] += count

        if not appears_in:
            break                                   # everything is playable

        best = max(appears_in, key=lambda c: (new_songs[c], appears_in[c]))
        known.add(best)
        playable += new_songs[best]
        results.append({
            "step": step,
            "chord_added": best,
            "chords_known": " ".join(sorted(known)),
            "songs_playable": playable,
            "pct_playable": round(100 * playable / total_songs, 1),
        })

    return pd.DataFrame(results), total_songs


# ---------------------------------------------------------------------
# 3. CHART: the coverage curve
# ---------------------------------------------------------------------

def plot_coverage(order, total_songs, out_path):
    blue, ink, muted, grid = "#2a78d6", "#0b0b0b", "#52514e", "#e4e3df"

    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=150)
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")

    ax.plot(order["step"], order["pct_playable"], color=blue, linewidth=2,
            marker="o", markersize=7, markeredgecolor="#fcfcfb",
            markeredgewidth=2, zorder=3)

    # Label each point with the chord learned at that step
    for _, row in order.iterrows():
        ax.annotate(row["chord_added"], (row["step"], row["pct_playable"]),
                    textcoords="offset points", xytext=(0, 9),
                    ha="center", fontsize=9, color=muted)

    ax.set_title(f"How many songs can you play after learning N chords?\n"
                 f"({total_songs:,} songs, best learning order)",
                 loc="left", fontsize=13, color=ink, pad=14)
    ax.set_xlabel("Chords learned", color=muted)
    ax.set_ylabel("% of songs fully playable", color=muted)
    ax.set_xticks(order["step"])
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")

    ax.grid(axis="y", color=grid, linewidth=1)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(grid)
    ax.tick_params(colors=muted, length=0)

    fig.tight_layout()
    fig.savefig(out_path)
    print(f"Saved chart -> {out_path}")


# ---------------------------------------------------------------------
# 4. RUN IT
# ---------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", nargs="?", default="chordonomicon_v2.csv")
    parser.add_argument("--max", type=int, default=12,
                        help="how many chords to learn (default 12)")
    args = parser.parse_args()

    print(f"Loading {args.csv} ...")
    df = pd.read_csv(args.csv, usecols=["chords"], low_memory=False)
    print(f"  {len(df):,} songs loaded")

    song_sets = df["chords"].map(song_chord_set)
    # Ignore songs with fewer than 3 chords (usually bad or partial data)
    song_sets = [s for s in song_sets if len(s) >= 3]
    print(f"  {len(song_sets):,} songs kept after cleaning")

    # Quick look: which chords show up in the most songs?
    chord_freq = Counter(c for s in song_sets for c in s)
    print("\nTop 10 chords (% of songs that use them):")
    for chord, n in chord_freq.most_common(10):
        print(f"  {chord:4s} {100 * n / len(song_sets):5.1f}%")

    order, total = best_learning_order(song_sets, args.max)
    print("\nBest learning order:")
    print(order.to_string(index=False))

    order.to_csv("learning_order.csv", index=False)
    print("\nSaved table -> learning_order.csv")
    plot_coverage(order, total, "coverage_curve.png")


if __name__ == "__main__":
    main()
