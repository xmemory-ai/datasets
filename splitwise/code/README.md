# How to run Splitwise benchmarks

In this repository the project files live under **`splitwise/code/`**; run `uv` and the step scripts from that directory.

A small pipeline for building **Splitwise-style** shared-expense scenarios with the Anthropic API, producing **`fulltest.json`** for downstream use. **Step 3** optionally exports YAML benchmark bundles for xmemory-style tooling.

## Setup

Install [uv](https://docs.astral.sh/uv/), then from this directory:

```bash
uv sync
```

Run scripts with `uv run python <script>.py …`, or use `./step3_create_benchmark.py` after `chmod +x` (it is committed executable).

## Environment variables

| Variable | Required for | Purpose |
|----------|----------------|----------|
| `ANTHROPIC_API_KEY` | Steps 1–2 (API phrasing) | Anthropic API access |

## Pipeline overview

```text
step1_generate_outings_jsonl   →   outings.jsonl
        ↓
step2_build_fulltest           →   fulltest.json (+ init_prompts.json sidecar)

step3_create_benchmark (optional) → xmemory_benchmark_output/
```

Step 3 uses this sampling rule: pick a person who has enough outings, sample **N** of their outings (file order preserved), then pick one of their balance questions.

## Step 1 — generate outings (JSONL)

Creates **one JSON object per line** (chronological outings: attendees, totals, payer, dates). Uses the API only for names and place types.

```bash
uv run python step1_generate_outings_jsonl.py --people 10 --places 20 --events 500
```

Default output: `outings.jsonl` (override with `-o`).

## Step 2 — build `fulltest.json`

Reads `outings.jsonl`, calls the API for init paragraphs, expense phrasing, and per-person balance questions. Writes **`fulltest.json`** with `init_prompts`, `events` (with `prompt` per outing), and `queries`. Also writes **`init_prompts.json`** next to the output (duplicate slice of `init_prompts` only).

```bash
uv run python step2_build_fulltest.py -i outings.jsonl -o fulltest.json
```

## Step 3 — export xmemory benchmark bundles

Reads **`fulltest.json`** (events + queries) and **`init_prompts.json`** beside it. Step 2 writes that sidecar as `{"init_prompts": [...]}` (same strings as in `fulltest.json`). Step 3 also accepts a raw JSON array if you prefer. Emits numbered datasets under **`xmemory_benchmark_output/`**.

**With no arguments** (from a directory that already has `./fulltest.json` and `./init_prompts.json`): emits **50** datasets (`splitwise_benchmark_001` … `_050`), **10** sampled attendee outings per dataset, rotating init prompts in order (`(run − 1) % P`). That implies **50 must be divisible by** `P` (the standard step‑2 suite has **10** prompts → **5 uses each**). Override counts with **`--times`** / **`--outings`**.

- **Sampling:** each dataset picks a **random person** among those with at least **K** outings as an attendee, samples **K** of those outings (`--outings`, default **10**), then a **random** balance question for that person. If no one qualifies, or the chosen person’s pool is too small, the **whole run exits with an error**.

Executable entrypoint:

```bash
cd splitwise/code   # after step 2 produced fulltest.json + init_prompts.json here
./step3_create_benchmark.py
```

## Generated files (typically gitignored)

The repo ignores local artifacts such as `outings.jsonl`, `fulltest.json`, `init_prompts.json`, `output/`, `result/`, and `xmemory_benchmark_output/`. Regenerate them with the steps above rather than committing them.

## Layout

| Path | Role |
|------|------|
| `step1_generate_outings_jsonl.py`, `step2_build_fulltest.py` | Data generation CLI |
| `step3_create_benchmark.py` | Optional xmemory benchmark export |
| `generate_with_key.py` | Imported helpers (not a standalone CLI) |
| `llm.py`, `llm_outputs.py` | Anthropic + Pydantic structured-output plumbing |
| `pyproject.toml`, `uv.lock` | Dependencies for `uv sync` |

Use `uv run python <script> --help` on any step script for full flags and defaults.

## 2026-April-3 Links

Manual runs and notes (historical):

[ChatGPT without memory](https://chatgpt.com/share/69d00366-c8b0-8332-b9d8-8339d79c84a7).
[Claude Desktop Incognito](https://docs.google.com/document/d/1ZVqKKaKpF7EpmeUn_1uxTAbSnIyNumiFiX5Z8N9EKk8/edit?usp=sharing).
