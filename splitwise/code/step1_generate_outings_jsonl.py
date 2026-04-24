#!/usr/bin/env -S uv run python
# Example (repo root): ./step1_generate_outings_jsonl.py --people 10 --places 20 --events 50
"""step1_generate_outings_jsonl: random setup data (cast, place types, dated outings, balances).

Uses the Anthropic API for creative names and place types only (no natural-language prompts).
Writes outings.jsonl: one JSON object per line, each line one outing event,
in chronological order (earliest date first).

Requires ANTHROPIC_API_KEY.
"""

import argparse
import json
import os
import random
import sys

from datetime import date, timedelta

import generate_with_key as g

# Defaults for this step (may differ from generate_with_key.py)
DEFAULT_PEOPLE = 10
DEFAULT_PLACES = 10
DEFAULT_EVENTS = 100


def outing_date_window(num_events):
    """Inclusive calendar range [today - N + 1, today] for N == num_events."""
    today = date.today()
    start = today - timedelta(days=num_events - 1)
    return start, today


def assert_outing_dates_in_window(events, start, end):
    for e in events:
        d = date.fromisoformat(e["date_iso"])
        if d < start or d > end:
            raise AssertionError(
                f"Outing date {e['date_iso']} outside [{start.isoformat()}, {end.isoformat()}]"
            )


def main():
    parser = argparse.ArgumentParser(
        description="Generate outings.jsonl: one line per outing (chronological), no prompts."
    )
    parser.add_argument("--people", type=int, default=DEFAULT_PEOPLE,
                        help=f"Number of people (default {DEFAULT_PEOPLE})")
    parser.add_argument("--places", type=int, default=DEFAULT_PLACES,
                        help=f"Number of distinct place types (default {DEFAULT_PLACES})")
    parser.add_argument("--events", type=int, default=DEFAULT_EVENTS,
                        help=f"Number of outing events (default {DEFAULT_EVENTS})")
    parser.add_argument(
        "-o", "--output", default="outings.jsonl",
        help="Output JSONL path (default outings.jsonl)",
    )
    parser.add_argument("--model", default=g.DEFAULT_MODEL,
                        help=f"Model (default {g.DEFAULT_MODEL})")
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        metavar="S",
        help="Fix Python randomness in outing construction (reproducible splits/dates order); "
        "LLM names/places still vary unless the API is deterministic",
    )
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("error: ANTHROPIC_API_KEY is not set", file=sys.stderr)
        sys.exit(2)

    if args.people < 2:
        print("error: --people must be at least 2", file=sys.stderr)
        sys.exit(2)
    if args.places < 1:
        print("error: --places must be at least 1", file=sys.stderr)
        sys.exit(2)
    if args.events < 1:
        print("error: --events must be at least 1", file=sys.stderr)
        sys.exit(2)

    g.init_api(model=args.model)

    start_d, end_d = outing_date_window(args.events)

    print("=== Generating names (API) ===")
    names = g.generate_names(args.people)
    print(f"  → {names}\n")

    print("=== Generating place types (API) ===")
    place_types = g.generate_place_types(args.places)
    print(f"  → {place_types}\n")

    print("=== Creating outings (Python) ===")
    if args.seed is not None:
        random.seed(args.seed)
    events = g.create_events(names, place_types, args.events, shuffle_dates=False)
    assert_outing_dates_in_window(events, start_d, end_d)

    type_counts = g.count_by_type(events)
    balances = g.compute_balances(events, names)

    for e in events:
        per = e["total_usd"] // len(e["attendees"])
        print(
            f"  {e['date_iso']} {e['type']}: {e['attendees']} → ${e['total_usd']} "
            f"(${per}/person), payer={e['payer']}"
        )
    print(f"\n  Type counts: {type_counts}")
    print("\n  Balances:")
    for n, b in balances.items():
        print(f"    {n}: {b:+d}")

    with open(args.output, "w", encoding="utf-8") as f:
        for e in events:
            event_obj = {
                "date_iso": e["date_iso"],
                "type": e["type"],
                "attendees": e["attendees"],
                "total_usd": e["total_usd"],
                "payer": e["payer"],
            }
            f.write(json.dumps(event_obj, ensure_ascii=False) + "\n")

    print(f"\n=== Wrote {args.output} ({len(events)} events, chronological) ===")


if __name__ == "__main__":
    main()
