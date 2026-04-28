#!/usr/bin/env -S uv run python
"""step2_build_fulltest: turn outings.jsonl into fulltest.json (setup, events, balance queries).

Reads step1_generate_outings_jsonl output (one JSON outing per line). Uses Anthropic API for phrasing.
Produces short, simple init setup prompts by default (full roster, default “everyone attended” if unspecified),
even split across attendees, payer owed shares; expense lines; and queries. Each init paragraph
includes (via LLM prompt) a clarification that same venue/type on different dates counts as distinct outings.
Each balance query string is suffixed with plain-text answer-format rules for downstream eval tooling.
Also writes init_prompts.json next to the main output (same init_prompts slice as in fulltest).
Requires ANTHROPIC_API_KEY.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import generate_with_key as g
from llm_outputs import BalanceQuestionsVariety, InitSetupParagraph

DEFAULT_INPUT = "outings.jsonl"
DEFAULT_OUTPUT = "fulltest.json"
DEFAULT_VARIETY = 3
DEFAULT_INIT_PROMPTS = 10


# Appended to every balance query string (single signed integer USD balance; no prose).
BALANCE_QUERY_PLAIN_ANSWER_SUFFIX = (
    "\n\n"
    "Answer with one signed integer in USD: positive if the group owes them, "
    "negative if they owe the group. Just the integer — no words, no currency symbol."
)


def load_outings(path):
    events = []
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            for key in ("date_iso", "type", "attendees", "total_usd", "payer"):
                if key not in obj:
                    print(f"error: {path}:{lineno}: missing {key!r}", file=sys.stderr)
                    sys.exit(2)
            events.append(obj)
    return events


def names_for_queries(events, cast_path):
    if cast_path:
        with open(cast_path, encoding="utf-8") as f:
            names = json.load(f)
        if not isinstance(names, list) or not all(isinstance(x, str) for x in names):
            print("error: --cast must be a JSON array of strings", file=sys.stderr)
            sys.exit(2)
        return names
    seen = set()
    for e in events:
        for a in e["attendees"]:
            seen.add(a)
    return sorted(seen)


def generate_balance_queries_variety(name, variety):
    """Return `variety` distinct natural-language balance questions for `name` (no answer-format suffix).

    Questions are kept clean: they ask for the exact dollar balance and nothing more.
    The sign convention and output format live in BALANCE_QUERY_PLAIN_ANSWER_SUFFIX, which
    is appended downstream — do NOT restate either here.
    """
    prompt = (
        "You write short natural English questions about one person's balance in a shared expense tracker.\n\n"
        "Each question must ask for the exact numerical balance in dollars (the specific amount), "
        "not merely who owes whom in the abstract. Keep each question to one short sentence.\n\n"
        "Do NOT restate any sign convention, do NOT explain what positive/negative means, "
        "and do NOT include answer-format instructions — those are appended separately downstream. "
        "Just ask the question.\n\n"
        f"Write exactly {variety} distinct questions that elicit {name}'s current balance as a concrete dollar amount. "
        f"Vary tone and phrasing. Fill the questions field with exactly {variety} strings."
    )
    max_tokens = min(2048, max(256, variety * 180))
    parsed = g.llm.generate(
        prompt=prompt,
        schema=BalanceQuestionsVariety,
        max_tokens=max_tokens,
    )
    arr = parsed.questions
    if len(arr) != variety:
        raise ValueError(
            f"Expected {variety} balance questions for {name!r}, got {len(arr)}: {arr!r}"
        )
    return arr


def _init_prompt_instruction_block(num, roster):
    return (
        "You write brief opening instructions for a conversational agent that helps a fixed friend group track "
        "shared outings (meals, activities, etc.). Keep wording plain and compact.\n\n"
        "AUTHORITATIVE GROUP ROSTER (use exactly; do not rename or omit anyone):\n"
        f"- There are exactly {num} people in the group.\n"
        f"- Their names, in this order, are: {roster}\n\n"
        "Requirements for this paragraph (all must be satisfied):\n"
        f"- Explicitly state how many people are in the group ({num}) and name every member at least once, "
        "using the exact spellings above.\n"
        "- Do NOT mention positive balances, negative balances, zero balances, or any sign convention.\n"
        "- Be short and simple: about 2–4 sentences total, each sentence tight and concrete—no filler, "
        "no long anecdotes, no repeated restatements of the same rule.\n"
        "- Explain that for every outing we will record: who participated, the total bill in dollars, "
        "and who paid the bill (one payer who covers the check).\n"
        "- Spell out the accounting model explicitly: the total is split **evenly** across **everyone "
        "who attended that outing** (equal shares). The payer advanced the full amount; each other "
        "participant therefore owes the payer their fair share of that bill (their equal portion). "
        "Say that this shared, even-split assumption is how we will reason about who owes whom.\n"
        "- CRITICAL DEFAULT FOR AMBIGUOUS EXPENSE MESSAGES: state clearly that whenever a later "
        "expense message does **not** spell out exactly which subset of the group attended that outing, "
        f"the agent must assume **the full group** (all {num} people listed above) participated—unless "
        "the message explicitly names a different subset.\n"
        "- Mention that later in the conversation we will ask follow-up questions about balances or "
        "who owes what, grounded in this even-split rule—without defining how those answers should be "
        "signed or labeled.\n"
        "- DISTINCTNESS: state explicitly that outings at the same location or of the same type "
        "on different calendar dates are **distinct** outings and must never be merged or "
        "deduplicated. Weave this naturally into the paragraph.\n"
        "- DATE STORAGE FORMAT: state explicitly that every outing's date must be stored in the "
        "database as a dash-separated ISO calendar date in the form YYYY-MM-DD (e.g. 2026-01-15), "
        "regardless of how the source message phrases the date. This canonical format is essential "
        "because later questions will look up outings by date.\n"
    )


def generate_init_prompts(count, group_names):
    """Return `count` distinct short setup paragraphs; one API call per paragraph."""
    if len(group_names) < 2:
        print("error: need at least 2 people in the group for init prompts", file=sys.stderr)
        sys.exit(2)

    num = len(group_names)
    roster = json.dumps(group_names, ensure_ascii=False)
    base = _init_prompt_instruction_block(num, roster)
    out = []
    max_tokens = 512

    for i in range(1, count + 1):
        done_before = i - 1
        left_including = count - done_before
        print(
            f"  init: paragraph {i}/{count} — already {done_before} generated, "
            f"{left_including} left (including this one)",
            flush=True,
        )
        prompt = (
            base
            + f"\nThis is init setup paragraph {i} of {count} for the same group. "
            "It must stand alone and satisfy every requirement above. "
            "Vary wording slightly from other paragraphs in this series, but stay brief—do not add "
            "extra length just for variety.\n\n"
            "Put the full paragraph in the paragraph field only (no bullet list of rules, no preamble)."
        )
        block = g.llm.generate(
            prompt=prompt,
            schema=InitSetupParagraph,
            max_tokens=max_tokens,
            verbose=False,
        )
        out.append(block.paragraph.strip())
        done_after = i
        left_after = count - done_after
        print(
            f"  init: now {done_after} generated, {left_after} left",
            flush=True,
        )

    return out


def main():
    parser = argparse.ArgumentParser(
        description="Build fulltest.json from outings.jsonl (API phrasing)."
    )
    parser.add_argument(
        "-i", "--input", default=DEFAULT_INPUT,
        help=f"Outings JSONL from step1_generate_outings_jsonl.py (default {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "-o", "--output", default=DEFAULT_OUTPUT,
        help=f"Output path (default {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--prompts", type=int, default=DEFAULT_INIT_PROMPTS, metavar="N",
        help=(
            f"How many distinct init/setup paragraphs to generate (default {DEFAULT_INIT_PROMPTS})"
        ),
    )
    parser.add_argument(
        "--variety", type=int, default=DEFAULT_VARIETY,
        help=f"Balance question phrasings per person (default {DEFAULT_VARIETY})",
    )
    parser.add_argument(
        "--cast",
        metavar="PATH",
        help="Optional JSON file: array of names for query keys (default: union of attendees)",
    )
    parser.add_argument(
        "--expense-batch-size",
        type=int,
        default=g.EXPENSE_BATCH_SIZE_MAX,
        metavar="N",
        help=(
            f"Outing expense prompts per API call, 1–{g.EXPENSE_BATCH_SIZE_MAX} "
            f"(default {g.EXPENSE_BATCH_SIZE_MAX})"
        ),
    )
    parser.add_argument("--model", default=g.DEFAULT_MODEL,
                        help=f"Model (default {g.DEFAULT_MODEL})")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("error: ANTHROPIC_API_KEY is not set", file=sys.stderr)
        sys.exit(2)

    if args.prompts < 1:
        print("error: --prompts must be at least 1", file=sys.stderr)
        sys.exit(2)

    if args.variety < 1:
        print("error: --variety must be at least 1", file=sys.stderr)
        sys.exit(2)

    if not (1 <= args.expense_batch_size <= g.EXPENSE_BATCH_SIZE_MAX):
        print(
            f"error: --expense-batch-size must be 1..{g.EXPENSE_BATCH_SIZE_MAX}",
            file=sys.stderr,
        )
        sys.exit(2)

    if not os.path.isfile(args.input):
        print(f"error: input not found: {args.input}", file=sys.stderr)
        sys.exit(2)

    events = load_outings(args.input)
    if not events:
        print("error: no outings in input", file=sys.stderr)
        sys.exit(2)

    g.init_api(model=args.model)

    names = names_for_queries(events, args.cast)
    if not names:
        print("error: no names for queries (use --cast)", file=sys.stderr)
        sys.exit(2)

    print("=== Init / setup prompts (API) ===")
    print(f"  group: {len(names)} people → {names}")
    print(f"  init: one API call per paragraph ({args.prompts} total)\n", flush=True)
    init_prompts = generate_init_prompts(args.prompts, names)
    print()

    print("=== Expense prompts (API) ===")
    n_exp = len(events)
    print(f"  expenses: {n_exp} total to generate (batch size {args.expense_batch_size})", flush=True)

    def expense_progress(done, total):
        left = total - done
        print(f"  expenses: {done} generated, {left} left", flush=True)

    prompts = g.generate_expense_prompts_batched(
        events, args.expense_batch_size, progress=expense_progress
    )
    if len(prompts) != len(events):
        raise RuntimeError(f"prompt count {len(prompts)} != events {len(events)}")

    events_out = []
    for e, p in zip(events, prompts):
        events_out.append({**e, "prompt": p})

    print("\n=== Balance query prompts (API) ===")
    queries = {}
    total_names = len(names)
    for i, name in enumerate(names, start=1):
        done_before = i - 1
        left_including = total_names - done_before
        print(
            f"  balance queries: person {i}/{total_names} ({name}) — "
            f"already {done_before} generated, {left_including} left (including this one)",
            flush=True,
        )
        raw_qs = generate_balance_queries_variety(name, args.variety)
        queries[name] = [q.strip() + BALANCE_QUERY_PLAIN_ANSWER_SUFFIX for q in raw_qs]
        done_after = i
        left_after = total_names - done_after
        print(
            f"  balance queries: now {done_after} generated, {left_after} left",
            flush=True,
        )

    doc = {
        "init_prompts": init_prompts,
        "events": events_out,
        "queries": queries,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")

    init_sidecar = Path(args.output).resolve().parent / "init_prompts.json"
    init_fragment = {"init_prompts": init_prompts}
    with open(init_sidecar, "w", encoding="utf-8") as f:
        json.dump(init_fragment, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\n=== Wrote {args.output} ===")
    print(f"=== Wrote {init_sidecar} (init_prompts only) ===")


if __name__ == "__main__":
    main()
