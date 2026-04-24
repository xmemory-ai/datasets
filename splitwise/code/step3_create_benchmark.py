#!/usr/bin/env -S uv run python
"""Export xmemory benchmark bundles (splitwise benchmark layout) from fulltest.json.

Loads init prompts from ``init_prompts.json`` (same order as ``fulltest.json``).

**No-argument defaults:** ``./fulltest.json``, ``init_prompts.json`` beside it,
``./xmemory_benchmark_output/``, **50** datasets, **K=10** sampled attendee outings
per dataset. Prompt index for dataset *i* is ``(i - 1) % P``; **50 must be a
multiple of** ``P`` (e.g. **10 prompts × 5 uses**). Each dataset picks a random
eligible person, samples **K** of their outings, then a random balance question.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from collections import Counter
from datetime import date
from pathlib import Path

# Invoked with no CLI args: match the intended 50-test / 10-outing / 10-prompt×5 suite.
DEFAULT_TOTAL_DATASETS = 50
DEFAULT_OUTINGS_K = 10

# Output directory / YAML slugs (filesystem-safe).
BUNDLE_SLUG = "splitwise_benchmark"


def load_fulltest(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_init_prompts_json(path: Path) -> list[str]:
    """Load prompts from step2's sidecar: ``{\"init_prompts\": [...]}`` or a raw JSON array."""
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "init_prompts" in data:
        raw = data["init_prompts"]
    elif isinstance(data, list):
        raw = data
    else:
        print(
            "error: init_prompts.json must be either a JSON array of strings "
            'or an object {"init_prompts": [...]} (same format step2_build_fulltest.py writes)',
            file=sys.stderr,
        )
        sys.exit(2)
    if not isinstance(raw, list) or not raw:
        print("error: init_prompts list must be non-empty", file=sys.stderr)
        sys.exit(2)
    out: list[str] = []
    for i, item in enumerate(raw):
        if not isinstance(item, str) or not item.strip():
            print(f"error: init_prompts[{i}] must be a non-empty string", file=sys.stderr)
            sys.exit(2)
        out.append(item)
    return out


def _norm_prompt(s: str) -> str:
    return "\n".join(line.rstrip() for line in s.strip().splitlines()).strip()


def assert_init_prompts_match_file(
    *,
    path: Path,
    from_file: list[str],
    from_fulltest: list,
) -> None:
    if not isinstance(from_fulltest, list) or len(from_fulltest) != len(from_file):
        print(
            "error: init_prompts.json and fulltest.json `init_prompts` must have the same length",
            file=sys.stderr,
        )
        sys.exit(2)
    for i, (a, b) in enumerate(zip(from_file, from_fulltest, strict=True)):
        if not isinstance(b, str):
            print(f"error: fulltest.json init_prompts[{i}] must be a string", file=sys.stderr)
            sys.exit(2)
        if _norm_prompt(a) != _norm_prompt(b):
            print(
                f"error: init_prompts.json and fulltest.json disagree at index {i} "
                f"(files must match; see {path})",
                file=sys.stderr,
            )
            sys.exit(2)


def build_person_to_indexed_events(
    events: list, queries: dict, outings_n: int
) -> dict[str, list[tuple[int, dict]]]:
    """Map each queried name to (event_index, event) for events where they are attendees."""
    person_to_indexed_events: dict[str, list[tuple[int, dict]]] = {}
    for name in queries:
        if not isinstance(name, str) or not name:
            continue
        indexed = [
            (i, e)
            for i, e in enumerate(events)
            if isinstance(e, dict) and name in e.get("attendees", [])
        ]
        if len(indexed) >= outings_n:
            person_to_indexed_events[name] = indexed
    return person_to_indexed_events


def balances_for_events(picked_events: list[dict], person: str) -> dict[str, int]:
    people: set[str] = set()
    for e in picked_events:
        attendees = e.get("attendees")
        payer = e.get("payer")
        if not isinstance(attendees, list) or not attendees:
            print("error: each event must have non-empty `attendees` list", file=sys.stderr)
            sys.exit(2)
        if not isinstance(payer, str) or not payer:
            print("error: each event must have non-empty string `payer`", file=sys.stderr)
            sys.exit(2)
        people.update(attendees)
        people.add(payer)

    balances = {p: 0 for p in sorted(people)}
    for e in picked_events:
        attendees = e["attendees"]
        total = e.get("total_usd")
        payer = e["payer"]
        if not isinstance(total, int):
            print("error: each event must have integer `total_usd`", file=sys.stderr)
            sys.exit(2)
        share = total // len(attendees)
        for a in attendees:
            balances[a] -= share
        balances[payer] += total

    if sum(balances.values()) != 0:
        print("error: computed balances do not sum to zero", file=sys.stderr)
        sys.exit(2)
    if person not in balances:
        print(f"error: sampled person {person!r} missing from sampled balances", file=sys.stderr)
        sys.exit(2)
    return balances


def yaml_indent_block(text: str, spaces: int = 6) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line for line in text.splitlines())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate xmemory benchmark assets (splitwise benchmark) from fulltest.json."
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=Path("fulltest.json"),
        help="Path to fulltest.json (default: ./fulltest.json)",
    )
    parser.add_argument(
        "--init-prompts",
        type=Path,
        default=None,
        help=(
            "Init prompts file: {\"init_prompts\": [...]} (step 2) or a raw JSON array "
            "(default: init_prompts.json beside --input)"
        ),
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("xmemory_benchmark_output"),
        help="Output root directory (default: ./xmemory_benchmark_output)",
    )
    parser.add_argument(
        "-n",
        "--outings",
        type=int,
        default=DEFAULT_OUTINGS_K,
        metavar="K",
        help=(
            "Sample K outings that include the chosen person as an attendee "
            f"(default: {DEFAULT_OUTINGS_K})"
        ),
    )
    parser.add_argument(
        "--times",
        type=int,
        default=DEFAULT_TOTAL_DATASETS,
        metavar="N",
        help=(
            "Number of benchmark datasets to emit; must be a multiple of the number of init prompts "
            f"(default: {DEFAULT_TOTAL_DATASETS}, i.e. 10 prompts × 5 full cycles when P=10)"
        ),
    )
    parser.add_argument(
        "--author",
        default="Autogenerated",
        help='Author value for generated YAML files (default: "Autogenerated")',
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional random seed for deterministic sampling",
    )
    args = parser.parse_args()

    fulltest_path = args.input.resolve()
    init_prompts_path = (
        args.init_prompts.resolve()
        if args.init_prompts is not None
        else fulltest_path.with_name("init_prompts.json")
    )
    out_root = args.output_dir.resolve()
    outings_n = args.outings
    author = args.author

    if not fulltest_path.is_file():
        print(f"error: fulltest.json not found at: {fulltest_path}", file=sys.stderr)
        sys.exit(2)
    if not init_prompts_path.is_file():
        print(
            f"error: init prompts file not found at: {init_prompts_path}\n"
            "  (Run step2_build_fulltest.py; it writes init_prompts.json next to fulltest.json.)",
            file=sys.stderr,
        )
        sys.exit(2)
    if outings_n < 1:
        print("error: --outings must be a positive integer", file=sys.stderr)
        sys.exit(2)
    if not author:
        print("error: --author must be non-empty", file=sys.stderr)
        sys.exit(2)

    doc = load_fulltest(fulltest_path)
    events = doc.get("events") or []
    queries = doc.get("queries") or {}
    ft_init = doc.get("init_prompts") or []

    if not isinstance(events, list) or not events:
        print("error: fulltest.json must contain non-empty `events`", file=sys.stderr)
        sys.exit(2)
    if not isinstance(queries, dict) or not queries:
        print("error: fulltest.json must contain non-empty `queries`", file=sys.stderr)
        sys.exit(2)

    prompts = load_init_prompts_json(init_prompts_path)
    assert_init_prompts_match_file(
        path=init_prompts_path,
        from_file=prompts,
        from_fulltest=ft_init,
    )

    p = len(prompts)
    times_n = args.times

    if times_n < 1:
        print("error: total number of datasets must be at least 1", file=sys.stderr)
        sys.exit(2)
    if times_n % p != 0:
        hint = (times_n + p - 1) // p * p
        print(
            f"error: --times ({times_n}) must be a multiple of the number of init prompts ({p}) "
            "so each prompt is used the same number of times in order (datasets 1..P, repeat).\n"
            f"  Example: --times {hint} or --times {5 * p} for five full cycles.",
            file=sys.stderr,
        )
        sys.exit(2)

    uses_per_prompt = times_n // p

    person_to_indexed_events = build_person_to_indexed_events(events, queries, outings_n)
    if not person_to_indexed_events:
        print(
            f"error: no queried person appears as an attendee in at least {outings_n} outings "
            "(increase data or lower --outings).",
            file=sys.stderr,
        )
        sys.exit(2)

    out_root.mkdir(parents=True, exist_ok=True)

    rng = random.Random()
    if args.seed is not None:
        rng.seed(args.seed)

    generated: list[tuple[str, str, int, int]] = []

    for run_idx in range(1, times_n + 1):
        prompt_idx = (run_idx - 1) % p
        instance_description = prompts[prompt_idx].strip()

        eligible_people = sorted(person_to_indexed_events.keys())
        person = rng.choice(eligible_people)
        pool = person_to_indexed_events[person]
        if len(pool) < outings_n:
            print(
                f"error: person {person!r} has only {len(pool)} qualifying outings "
                f"(need {outings_n}). Aborting entire run.",
                file=sys.stderr,
            )
            sys.exit(2)

        indexed = rng.sample(pool, outings_n)
        indexed.sort(key=lambda t: t[0])
        picked_events = [e for _, e in indexed]

        person_queries = queries.get(person)
        if not isinstance(person_queries, list) or not person_queries:
            print(f"error: queries[{person!r}] must be non-empty", file=sys.stderr)
            sys.exit(2)
        question = rng.choice(person_queries)
        if not isinstance(question, str) or not question.strip():
            print(f"error: selected query for {person!r} is empty", file=sys.stderr)
            sys.exit(2)

        balances = balances_for_events(picked_events, person)

        slug = BUNDLE_SLUG if times_n == 1 else f"{BUNDLE_SLUG}_{run_idx:03d}"
        dataset_dir = out_root / slug
        inputs_dir = dataset_dir / "inputs"
        inputs_dir.mkdir(parents=True, exist_ok=True)

        desc_block = yaml_indent_block(instance_description)
        dataset_yml = (
            f"name: {json.dumps('Splitwise benchmark dataset generated from fulltest.json')}\n"
            f"author: {json.dumps(author)}\n"
            f"created_at: {date.today().isoformat()}\n"
            "inputs:\n"
            "  - data.yml\n"
            "scenario:\n"
            "  passthrough_yml: {}\n"
            "instance_setup:\n"
            "  from_plaintext_description:\n"
            "    description: |-\n"
            f"{desc_block}\n"
        )

        benchmark_yml = (
            f'name: {json.dumps("Splitwise benchmark, single-answer accuracy with llm-as-a-judge")}\n'
            f"author: {json.dumps(author)}\n"
            f"created_at: {date.today().isoformat()}\n"
            f"dataset: ./{slug}/dataset.yml\n"
            "\n"
            "metrics:\n"
            "  read:\n"
            "    - single_answer_accuracy_llm:\n"
            "        llm_judge_name: BEDROCK_ANTHROPIC_MINI\n"
            "\n"
            "thresholds:\n"
            "  read:\n"
            "    single_answer_accuracy_llm: 1\n"
        )

        actions_lines: list[str] = []
        for e in picked_events:
            prompt = e.get("prompt")
            if not isinstance(prompt, str) or not prompt.strip():
                print("error: each event must have non-empty string `prompt`", file=sys.stderr)
                sys.exit(2)
            actions_lines.append("- write:")
            actions_lines.append(f"    query: {json.dumps(prompt.strip(), ensure_ascii=False)}")
            actions_lines.append("")

        actions_lines.append("- read:")
        actions_lines.append(f"    query: {json.dumps(question.strip(), ensure_ascii=False)}")
        actions_lines.append("    labels:")
        actions_lines.append(f"      single_answer: {json.dumps(str(balances[person]))}")
        actions_lines.append("")

        data_yml = "\n".join(actions_lines).rstrip() + "\n"

        (dataset_dir / "dataset.yml").write_text(dataset_yml, encoding="utf-8")
        (inputs_dir / "data.yml").write_text(data_yml, encoding="utf-8")
        (out_root / f"{slug}.yml").write_text(benchmark_yml, encoding="utf-8")

        stale_schema = dataset_dir / "schema.yml"
        if stale_schema.exists():
            stale_schema.unlink()
        legacy_runner = dataset_dir / "run_splitwise_benchmark.sh"
        if legacy_runner.exists():
            legacy_runner.unlink()
        legacy_benchmark = dataset_dir / "benchmark.yml"
        if legacy_benchmark.exists():
            legacy_benchmark.unlink()
        legacy_nested_dir = dataset_dir / BUNDLE_SLUG
        if legacy_nested_dir.is_dir():
            shutil.rmtree(legacy_nested_dir)

        generated.append((slug, person, len(picked_events), prompt_idx))

    stale_runner = out_root / "run_splitwise_benchmark.sh"
    if stale_runner.exists():
        stale_runner.unlink()

    usage = Counter(idx for *_, idx in generated)
    print(f"Generated {len(generated)} benchmark bundle(s) ({uses_per_prompt} use(s) per prompt):")
    for slug, person, outings, pidx in generated:
        print(
            f"  {out_root}/{slug}.yml  "
            f"(init_prompt[{pidx}], person={person!r}, outings={outings})"
        )
        print(f"    → {out_root}/{slug}/dataset.yml")
        print(f"    → {out_root}/{slug}/inputs/data.yml")
    print("Init prompt index counts:", dict(sorted(usage.items())))
    print(f"Author: {author!r}")
    print(f"Init prompts file: {init_prompts_path}")
    print(f"Seed: {args.seed if args.seed is not None else 'none'}")


if __name__ == "__main__":
    main()
