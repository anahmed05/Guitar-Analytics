"""
Common Chord Progressions  (Guitar Analytics project, extra analysis)
---------------------------------------------------------------------
Question: how many songs share the same chord PATTERN, no matter the key?

"G D Em C" in G and "A E F#m D" in A are the same pattern, just higher
(exactly what a capo does). The script finds each song's key, counts
patterns in a key-free way, then SHOWS every pattern in the key of G so
the results read like chords you can play.
So "G - D - Em - C" in the results = that pattern in ANY key.

Needs chord_coverage.py and chordonomicon_v2.csv in the same folder.

Run:
  python chord_progressions.py

Outputs:
  top_progressions.csv       - top 10 loops of each size (2, 3, 4 chords)
  top_progressions.png       - chart comparing the top loops of each size
  progressions_by_genre.csv  - famous patterns by genre (if genre data exists)
"""

import argparse
from collections import Counter

import pandas as pd
import matplotlib.pyplot as plt

from chord_coverage import simplify_chord

NOTES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]

# Fret distance from the key's home note -> Roman numeral
NUMERALS = ["I", "bII", "II", "bIII", "III", "IV",
            "#IV", "V", "bVI", "VI", "bVII", "VII"]

DISPLAY_KEY = "G"   # results are shown as if every song were in G


def in_display_key(numeral):
    """Turn the internal label back into a playable chord in G:
    'I' -> 'G', 'IV' -> 'C', 'V' -> 'D', 'vi' -> 'Em', 'bVII' -> 'F'."""
    minor = numeral.islower()
    # Uppercase the numeral but keep a leading flat/sharp sign as is
    if numeral[0] in "b#":
        base = numeral[0] + numeral[1:].upper()
    else:
        base = numeral.upper()
    distance = NUMERALS.index(base)
    root = NOTES[(NOTES.index(DISPLAY_KEY) + distance) % 12]
    return root + ("m" if minor else "")


def show(pattern):
    return " - ".join(in_display_key(n) for n in pattern)

# The 6 chords that naturally belong to a major key: I ii iii IV V vi
IN_KEY = {(0, False), (2, True), (4, True), (5, False), (7, False), (9, True)}


# ---------------------------------------------------------------------
# 1. CHORDS IN ORDER (not just which chords, but the sequence)
# ---------------------------------------------------------------------

def song_sequence(chord_text):
    """'<verse_1> G G D Em C' -> ['G', 'D', 'Em', 'C'] (repeats removed)."""
    seq = []
    for token in str(chord_text).split():
        if token.startswith("<"):
            continue
        chord = simplify_chord(token)
        if chord and (not seq or seq[-1] != chord):
            seq.append(chord)
    return seq


def split_chord(chord):
    """'F#m' -> (6, True)  i.e. (position of the root note, is it minor?)"""
    minor = chord.endswith("m")
    root = chord[:-1] if minor else chord
    return NOTES.index(root), minor


# ---------------------------------------------------------------------
# 2. FIND EACH SONG'S KEY, THEN CONVERT TO ROMAN NUMERALS
# ---------------------------------------------------------------------
# Simple rule: try all 12 keys and pick the one where the most chords
# "belong". Ties go to the key whose home chord (I) appears most, and
# the song's first and last chords get extra weight, since songs often
# start and end on home.
#
# Minor-key songs end up described from their relative major
# (Am-F-C-G is read as vi-IV-I-V in C). That's on purpose: it's the
# same loop of chords, just starting in a different spot.

def find_key(parsed):
    best_key, best_score = 0, None
    for key in range(12):
        fits = sum(((r - key) % 12, m) in IN_KEY for r, m in parsed)
        home = sum(r == key and not m for r, m in parsed)
        ends = sum(r == key and not m for r, m in (parsed[0], parsed[-1]))
        score = (fits, home + ends)
        if best_score is None or score > best_score:
            best_key, best_score = key, score
    return best_key


def to_numerals(seq):
    parsed = [split_chord(c) for c in seq]
    key = find_key(parsed)
    out = []
    for root, minor in parsed:
        numeral = NUMERALS[(root - key) % 12]
        out.append(numeral.lower() if minor else numeral)
    return out


# ---------------------------------------------------------------------
# 3. COUNT PATTERNS
# ---------------------------------------------------------------------
# A "pattern" = any 4 chords in a row. Each pattern counts once per song,
# so a song that repeats I-V-vi-IV 20 times still counts as 1 song.
# Patterns are treated as loops: vi-IV-I-V counts as I-V-vi-IV.

def rotations(pattern):
    """A loop has no fixed start: I-V-vi-IV, V-vi-IV-I, vi-IV-I-V,
    IV-I-V-vi are all the same 4 chords going around in a circle."""
    return {tuple(pattern[i:] + pattern[:i]) for i in range(len(pattern))}


def canonical(pattern):
    """Pick one standard way to write a loop, so its 4 starting points
    count as ONE pattern. Prefer starting on I (home), and skip any
    version that puts the same chord twice in a row."""
    # ii-V-I-ii starts and ends on the same chord: it's really a 3-chord
    # loop (ii-V-I) going around, so describe it with 3 chords.
    if len(pattern) > 3 and pattern[0] == pattern[-1]:
        return canonical(pattern[:-1])
    # I-IV-I-IV is just two chords going back and forth (a "vamp")
    if len(pattern) == 4 and pattern[:2] == pattern[2:]:
        return canonical(pattern[:2])
    options = [r for r in sorted(rotations(list(pattern)))
               if all(a != b for a, b in zip(r, r[1:]))]
    if not options:
        return tuple(pattern)
    starts_home = [r for r in options if r[0] == "I"]
    return (starts_home or options)[0]


FAMOUS = {
    "G-D-Em-C loop ('4 chord song')": rotations(["I", "V", "vi", "IV"]),
    "G-Em-C-D loop ('50s doo-wop')": rotations(["I", "vi", "IV", "V"]),
    "G-C-D-C (rock & country)": {("I", "IV", "V", "IV")},
}


def analyze(df, window=4):
    pattern_songs = Counter()
    famous_hits = {name: [] for name in FAMOUS}
    only_four = []          # song uses ONLY I, IV, V, vi (any order)

    for text in df["chords"]:
        seq = song_sequence(text)
        if len(set(seq)) < 3:
            for name in FAMOUS:
                famous_hits[name].append(None)
            only_four.append(None)
            continue

        numerals = to_numerals(seq)
        windows = {tuple(numerals[i:i + window])
                   for i in range(len(numerals) - window + 1)}
        pattern_songs.update({canonical(w) for w in windows})

        for name, patterns in FAMOUS.items():
            famous_hits[name].append(bool(windows & patterns))
        only_four.append(set(numerals) <= {"I", "IV", "V", "vi"})

    result = df.copy()
    for name in FAMOUS:
        result[name] = famous_hits[name]
    result["Only G, C, D, Em chords"] = only_four
    result = result.dropna(subset=["Only G, C, D, Em chords"])
    flag_cols = list(FAMOUS) + ["Only G, C, D, Em chords"]
    result[flag_cols] = result[flag_cols].astype(bool)
    return pattern_songs, result


# ---------------------------------------------------------------------
# 4. CHART: top loops, split by how many different chords they use
# ---------------------------------------------------------------------
# Comparing a 2-chord vamp to a 4-chord loop isn't fair (shorter loops
# show up in more songs almost automatically), so each size gets its
# own panel.

def plot_top(top, total, out_path, per_panel=6):
    blue, ink, muted, grid, bg = "#2a78d6", "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
    sizes = [2, 3, 4]
    max_pct = top["pct_songs"].max()

    fig, axes = plt.subplots(1, 3, figsize=(15, 5.2), dpi=150)
    fig.patch.set_facecolor(bg)
    for ax, size in zip(axes, sizes):
        group = top[top["chords_in_loop"] == size].head(per_panel).iloc[::-1]
        ax.set_facecolor(bg)
        if group.empty:
            ax.set_yticks([])
            ax.text(0.5, 0.5, "none found", transform=ax.transAxes,
                    ha="center", color=muted)
        ax.barh(group["pattern"], group["pct_songs"], color=blue, height=0.6)
        for y, pct in enumerate(group["pct_songs"]):
            ax.annotate(f"{pct:.1f}%", (pct, y), textcoords="offset points",
                        xytext=(6, 0), va="center", fontsize=9, color=ink)
        ax.set_title(f"{size}-chord loops", loc="left", fontsize=12,
                     color=ink, pad=10)
        ax.set_xlim(0, max_pct * 1.25)            # same scale on every panel
        ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
        ax.grid(axis="x", color=grid, linewidth=1)
        ax.set_axisbelow(True)
        for side in ("top", "right", "bottom"):
            ax.spines[side].set_visible(False)
        ax.spines["left"].set_color(grid)
        ax.tick_params(colors=muted, length=0)
        ax.tick_params(axis="y", labelcolor=ink)

    fig.suptitle(f"Most common chord loops (shown in G, but counted in every key)  "
                 f"- % of {total:,} songs that use each one",
                 x=0.01, ha="left", fontsize=13, color=ink)
    fig.tight_layout()
    fig.savefig(out_path)
    print(f"Saved chart -> {out_path}")


# ---------------------------------------------------------------------
# 5. RUN IT
# ---------------------------------------------------------------------

SHORT_NAMES = {
    "G-D-Em-C loop ('4 chord song')": "4-chord song",
    "G-Em-C-D loop ('50s doo-wop')": "50s loop",
    "G-C-D-C (rock & country)": "G-C-D-C",
    "Only G, C, D, Em chords": "only G/C/D/Em",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", nargs="?", default="chordonomicon_v2.csv")
    args = parser.parse_args()

    columns = pd.read_csv(args.csv, nrows=0).columns
    use = ["chords"] + (["main_genre"] if "main_genre" in columns else [])

    print(f"Loading {args.csv} ...")
    df = pd.read_csv(args.csv, usecols=use, low_memory=False)
    print("Finding keys and patterns (this takes a few minutes) ...")
    pattern_songs, songs = analyze(df)
    total = len(songs)
    print(f"  {total:,} songs analyzed")

    top = pd.DataFrame(pattern_songs.most_common(),
                       columns=["pattern", "songs"])
    top["chords_in_loop"] = top["pattern"].map(lambda p: len(set(p)))
    top["pattern"] = top["pattern"].map(show)
    top["pct_songs"] = (100 * top["songs"] / total).round(1)
    top = top.groupby("chords_in_loop").head(10)   # top 10 of each size

    for size in (2, 3, 4):
        group = top[top["chords_in_loop"] == size]
        if group.empty:
            continue
        print(f"\nTop {size}-chord loops:")
        print(group[["pattern", "songs", "pct_songs"]].head(8)
              .to_string(index=False))

    flags = list(FAMOUS) + ["Only G, C, D, Em chords"]
    print("\nFamous patterns (% of all songs):")
    for name in flags:
        n = int(songs[name].sum())
        print(f"  {name:36s} {n:>8,}  ({100 * n / total:4.1f}%)")

    top.to_csv("top_progressions.csv", index=False)
    print("\nSaved table -> top_progressions.csv")
    plot_top(top, total, "top_progressions.png")

    if "main_genre" in songs.columns:
        by_genre = (songs.dropna(subset=["main_genre"])
                    .groupby("main_genre")[flags].mean().mul(100).round(1))
        by_genre.insert(0, "songs", songs.groupby("main_genre").size())
        by_genre = by_genre.sort_values(flags[0], ascending=False)
        by_genre = by_genre.rename(columns=SHORT_NAMES)
        print("\nBy genre (% of songs in that genre):")
        print(by_genre.to_string())
        by_genre.to_csv("progressions_by_genre.csv")
        print("Saved table -> progressions_by_genre.csv")


if __name__ == "__main__":
    main()
