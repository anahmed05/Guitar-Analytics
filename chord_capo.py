"""
Guitar Chord Coverage WITH A CAPO  (Step 2 of the Guitar Analytics project)
---------------------------------------------------------------------------
Question: guitarists learn chord SHAPES, not chords. With a capo, the same
shapes play songs in many keys. How many songs can you play after learning
N shapes, if you're allowed to use a capo?

Example: a song in A (A - D - E - F#m) is the G - C - D - Em shapes with a
capo on fret 2. Step 1 counted those as different songs; this step doesn't.

Needs chord_coverage.py and chordonomicon_v2.csv in the same folder.

Run:
  python chord_capo.py
  python chord_capo.py my_file.csv --max 12 --max-capo 7

Outputs:
  capo_learning_order.csv    - shape order + % playable, with and without capo
  coverage_comparison.png    - both curves on one chart (the headline visual)
"""

import argparse
from collections import Counter

import pandas as pd
import matplotlib.pyplot as plt

# Reuse the cleaning and the step 1 analysis instead of rewriting them
from chord_coverage import song_chord_set, best_learning_order


# ---------------------------------------------------------------------
# 1. MOVING CHORDS DOWN THE NECK (what a capo does, in reverse)
# ---------------------------------------------------------------------
# The 12 notes in order, one fret apart, spelled the same way as step 1.
NOTES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def shape_for(chord, capo):
    """The shape you'd finger to play `chord` with a capo on fret `capo`.
    Capo on 2 raises everything 2 frets, so the shape is 2 frets LOWER:
    shape_for('A', 2) -> 'G',  shape_for('F#m', 2) -> 'Em'."""
    is_minor = chord.endswith("m")
    root = chord[:-1] if is_minor else chord
    shape_root = NOTES[(NOTES.index(root) - capo) % 12]
    return shape_root + ("m" if is_minor else "")


def shape_options(chord_set, max_capo):
    """Every set of shapes that could play this song: one per capo fret."""
    return [frozenset(shape_for(c, k) for c in chord_set)
            for k in range(max_capo + 1)]


# ---------------------------------------------------------------------
# 2. BEST ORDER TO LEARN SHAPES (same greedy idea as step 1)
# ---------------------------------------------------------------------
# A song is playable once ANY of its capo options uses only known shapes.

# The open shapes beginners actually learn first (no barre needed).
OPEN_SHAPES = {"C", "A", "G", "E", "D", "Am", "Em", "Dm"}


def best_shape_order(song_sets, max_shapes, max_capo, allowed=None):
    """allowed: optional set of shapes the learner is willing to learn
    (e.g. OPEN_SHAPES). None means any shape is fair game."""
    set_counts = Counter(song_sets)
    total_songs = sum(set_counts.values())
    options = {s: shape_options(s, max_capo) for s in set_counts}

    known = set()
    playable = 0
    still_open = dict(set_counts)       # songs not yet playable
    results = []

    for step in range(1, max_shapes + 1):
        new_songs = Counter()
        appears_in = Counter()

        for chord_set, count in still_open.items():
            missing_lists = [opt - known for opt in options[chord_set]]
            fewest = min(len(m) for m in missing_lists)

            # Shapes that would finish this song (counted once per song)
            finishers = {next(iter(m)) for m in missing_lists if len(m) == 1}
            for shape in finishers:
                new_songs[shape] += count

            # Tie-breaker: shapes in the song's closest capo options
            closest = set().union(*(m for m in missing_lists
                                    if len(m) == fewest))
            for shape in closest:
                appears_in[shape] += count

        # Which shapes are we allowed to pick from this step?
        if allowed is None:
            candidates = list(appears_in)
        else:
            candidates = sorted(allowed - known)
        if not candidates:
            break

        best = max(candidates, key=lambda s: (new_songs[s], appears_in[s]))
        known.add(best)

        # Remove songs that just became playable
        done = [s for s in still_open
                if any(opt <= known for opt in options[s])]
        for s in done:
            playable += still_open.pop(s)

        results.append({
            "step": step,
            "shape_added": best,
            "shapes_known": " ".join(sorted(known)),
            "songs_playable_capo": playable,
            "pct_playable_capo": round(100 * playable / total_songs, 1),
        })

    return pd.DataFrame(results), total_songs, known


def capo_usage(song_sets, known_shapes, max_capo):
    """For songs playable with these shapes, which capo fret do they need?
    (Picks the lowest fret that works, since that's what most people use.)"""
    frets = Counter()
    for s in song_sets:
        for k, opt in enumerate(shape_options(s, max_capo)):
            if opt <= known_shapes:
                frets[k] += 1
                break
    return frets


# ---------------------------------------------------------------------
# 3. CHART: exact chords vs. shapes with a capo
# ---------------------------------------------------------------------

def plot_comparison(merged, total_songs, out_path, capo_name="Shapes + capo"):
    blue, orange = "#2a78d6", "#eb6834"
    ink, muted, grid, bg = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"

    fig, ax = plt.subplots(figsize=(10, 5.8), dpi=150)
    fig.patch.set_facecolor(bg)
    ax.set_facecolor(bg)

    lines = [
        ("pct_playable_capo", "shape_added", orange, capo_name),
        ("pct_playable", "chord_added", blue, "Exact chords (no capo)"),
    ]
    for col, label_col, color, name in lines:
        ax.plot(merged["step"], merged[col], color=color, linewidth=2,
                marker="o", markersize=7, markeredgecolor=bg,
                markeredgewidth=2, label=name, zorder=3)
        # Direct label at the end of each line
        last = merged.iloc[-1]
        ax.annotate(f"{name}: {last[col]:.0f}%",
                    (last["step"], last[col]), textcoords="offset points",
                    xytext=(8, 0), va="center", fontsize=9, color=ink)

    # Label the shapes learned along the capo line
    for _, row in merged.iterrows():
        ax.annotate(row["shape_added"],
                    (row["step"], row["pct_playable_capo"]),
                    textcoords="offset points", xytext=(0, 9),
                    ha="center", fontsize=8, color=muted)

    ax.set_title(f"Learning shapes + using a capo unlocks far more songs\n"
                 f"({total_songs:,} songs, best learning order for each)",
                 loc="left", fontsize=13, color=ink, pad=14)
    ax.set_xlabel("Chords / shapes learned", color=muted)
    ax.set_ylabel("% of songs fully playable", color=muted)
    ax.set_xticks(merged["step"])
    ax.set_ylim(0, 100)
    ax.set_xlim(0.5, merged["step"].max() + 3.5)   # room for end labels
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.legend(loc="upper left", frameon=False, labelcolor=ink)

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
                        help="how many chords/shapes to learn (default 12)")
    parser.add_argument("--max-capo", type=int, default=7,
                        help="highest capo fret allowed (default 7)")
    parser.add_argument("--open-only", action="store_true",
                        help="only learn open shapes: C A G E D Am Em Dm")
    args = parser.parse_args()
    allowed = OPEN_SHAPES if args.open_only else None
    capo_name = "Open shapes + capo" if args.open_only else "Shapes + capo"
    suffix = "_open" if args.open_only else ""

    print(f"Loading {args.csv} ...")
    df = pd.read_csv(args.csv, usecols=["chords"], low_memory=False)
    song_sets = [s for s in df["chords"].map(song_chord_set) if len(s) >= 3]
    print(f"  {len(song_sets):,} songs kept after cleaning")

    print("Running exact-chord analysis (step 1) ...")
    exact, total = best_learning_order(song_sets, args.max)

    print(f"Running shape + capo analysis (capo frets 0-{args.max_capo}) ...")
    capo, _, _ = best_shape_order(song_sets, args.max, args.max_capo, allowed)

    merged = exact.merge(capo, on="step")
    merged["capo_gain_pts"] = (merged["pct_playable_capo"]
                               - merged["pct_playable"]).round(1)

    print("\nExact chords vs. shapes + capo:")
    print(merged[["step", "chord_added", "pct_playable", "shape_added",
                  "pct_playable_capo", "capo_gain_pts"]].to_string(index=False))

    # Which capo frets do the first 4 shapes rely on?
    first_four = set(capo["shape_added"].head(4))
    frets = capo_usage(song_sets, first_four, args.max_capo)
    n = sum(frets.values())
    print(f"\nSongs playable with just {' '.join(sorted(first_four))}: "
          f"{n:,} ({100 * n / total:.1f}%)")
    print("Capo fret they need:")
    for k in sorted(frets):
        label = "no capo" if k == 0 else f"fret {k}"
        print(f"  {label:8s} {frets[k]:>8,}  ({100 * frets[k] / n:4.1f}%)")

    merged.to_csv(f"capo_learning_order{suffix}.csv", index=False)
    print(f"\nSaved table -> capo_learning_order{suffix}.csv")
    plot_comparison(merged, total, f"coverage_comparison{suffix}.png",
                    capo_name)


if __name__ == "__main__":
    main()
