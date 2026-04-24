"""Shared helpers for step1_generate_outings_jsonl / step2_build_fulltest: outing math and LLM I/O.

Not a CLI entrypoint — import this module from the step scripts only.
Python handles randomization and integer splits; the API phrases natural language where needed.
Requires ANTHROPIC_API_KEY when calling LLM-backed helpers.
"""

import random
from datetime import date, timedelta

import anthropic

from llm import llm
from llm_outputs import ExpenseSentencesOutput, NamesOutput, PlaceTypesOutput

PER_PERSON_OPTIONS = [20, 25, 30, 35, 40, 45, 50, 55, 60]
EXPENSE_BATCH_SIZE_MAX = 50
# Sonnet 4.5+ required for API structured outputs (messages.parse + output_format).
DEFAULT_MODEL = "claude-sonnet-4-5-20250929"


# ---------------------------------------------------------------------------
# Anthropic API helper
# ---------------------------------------------------------------------------

_client = None
_model = DEFAULT_MODEL


def init_api(model=None):
    global _client, _model
    _client = anthropic.Anthropic()  # uses ANTHROPIC_API_KEY env var
    if model:
        _model = model
    llm.configure(_client, _model)


# ---------------------------------------------------------------------------
# Step 1 — Claude generates creative atoms
# ---------------------------------------------------------------------------

def generate_names(n):
    out = llm.generate(
        prompt=(
            f"Generate exactly {n} unique simple first names from diverse cultures. "
            f"Fill the names field with exactly {n} strings."
        ),
        schema=NamesOutput,
    )
    names = out.names
    assert len(names) == n, f"Expected {n} names, got {len(names)}: {names}"
    return names


def generate_place_types(n):
    out = llm.generate(
        prompt=(
            f"Generate exactly {n} unique types of restaurant food, cuisine, or group activity "
            f"(1-2 words each). Fill place_types with exactly {n} strings."
        ),
        schema=PlaceTypesOutput,
    )
    types = out.place_types
    assert len(types) == n, f"Expected {n} types, got {len(types)}: {types}"
    return types


def outing_date_bounds(num_events):
    """Return (A, B_exclusive, last_inclusive) for N unique calendar days ending today."""
    today = date.today()
    a = today - timedelta(days=num_events - 1)
    b_exclusive = today + timedelta(days=1)
    return a, b_exclusive, today


def assign_unique_outing_dates(num_events, shuffle=True):
    """One distinct calendar date per event, from today-(N-1) .. today (shuffled if shuffle)."""
    a, _, _ = outing_date_bounds(num_events)
    days = [a + timedelta(days=i) for i in range(num_events)]
    if shuffle:
        random.shuffle(days)
    return days


def format_attendee_names(attendees):
    if len(attendees) == 2:
        return f"{attendees[0]} and {attendees[1]}"
    return ", ".join(attendees[:-1]) + f", and {attendees[-1]}"


# ---------------------------------------------------------------------------
# Step 2 — Python generates outings & balances (all math, no LLM)
# ---------------------------------------------------------------------------

def create_events(names, place_types, num_events, shuffle_dates=True):
    outing_dates = assign_unique_outing_dates(num_events, shuffle=shuffle_dates)
    events = []
    for i in range(num_events):
        place_type = random.choice(place_types)
        max_attendees = min(8, len(names))
        num_attendees = random.randint(2, max_attendees)
        attendees = sorted(random.sample(names, num_attendees))
        payer = random.choice(attendees)
        per_person = random.choice(PER_PERSON_OPTIONS)
        total = per_person * num_attendees

        assert total % num_attendees == 0, (
            f"Non-integer split: ${total} / {num_attendees}"
        )

        d = outing_dates[i]
        events.append({
            "type": place_type,
            "attendees": attendees,
            "total_usd": total,
            "payer": payer,
            "date_iso": d.isoformat(),
        })
    return events


def compute_balances(events, names):
    bal = {n: 0 for n in names}
    for e in events:
        share = e["total_usd"] // len(e["attendees"])
        for a in e["attendees"]:
            bal[a] -= share
        bal[e["payer"]] += e["total_usd"]
    total = sum(bal.values())
    assert total == 0, f"Balances sum to {total}, expected 0: {bal}"
    return bal


def count_by_type(events):
    """Return {type: count} for how many times each place type appears."""
    counts = {}
    for e in events:
        counts[e["type"]] = counts.get(e["type"], 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Expense line phrasing (step2_build_fulltest)
# ---------------------------------------------------------------------------

def generate_expense_prompts_batched(events, batch_size, progress=None):
    """Ask the model for natural-language expense sentences; up to batch_size per call.

    If progress is callable, call progress(done_count, total) after each batch completes.
    """
    if not events:
        return []
    n = len(events)
    a, b_exclusive, last_day = outing_date_bounds(n)
    a_iso = a.isoformat()
    b_iso = b_exclusive.isoformat()
    last_iso = last_day.isoformat()

    out = []
    for start in range(0, n, batch_size):
        chunk = events[start : start + batch_size]
        k = len(chunk)
        lines = []
        for j, e in enumerate(chunk, start=1):
            names_str = format_attendee_names(e["attendees"])
            lines.append(
                f"{j}. Assigned calendar date (ISO): {e['date_iso']}. "
                f"{names_str} went out for {e['type']}, total bill ${e['total_usd']}, "
                f"payer: {e['payer']}."
            )
        spec = "\n".join(lines)
        prompt = (
            f"You will write exactly {k} separate natural English sentences — one per numbered "
            f"outing below (same order).\n\n"
            f"Date rules (critical):\n"
            f"- Every outing must be anchored to a calendar day in the half-open interval [A, B): "
            f"A is included, B is excluded (B is not a valid outing day).\n"
            f"- Use A = {a_iso} (inclusive) and B = {b_iso} (exclusive). "
            f"Equivalently, valid days are {a_iso} through {last_iso}, inclusive.\n"
            f"- Each line gives the assigned date for that outing in ISO form. "
            f"Your sentence must clearly refer to that same calendar day, including the year, in "
            f"natural language (you may use varied, unambiguous phrasings — not only ISO format).\n"
            f"- Use different date phrasings across sentences; do not copy the same template each time.\n"
            f"- Do not place any outing on a calendar day outside [A, B).\n\n"
            f"Content: mention who went, the kind of outing, the total, and who paid; vary how you "
            f"describe paying (took the check, covered it, picked up the tab, etc.).\n\n"
            f"Outings:\n{spec}\n\n"
            f"Fill sentences with exactly {k} strings in the same order as the numbered outings."
        )
        max_tokens = min(8192, max(1024, k * 150))
        parsed = llm.generate(
            prompt=prompt,
            schema=ExpenseSentencesOutput,
            max_tokens=max_tokens,
        )
        arr = parsed.sentences
        assert len(arr) == k, f"Expected {k} expense sentences, got {len(arr)}: {arr!r}"
        out.extend(arr)
        if progress is not None:
            progress(len(out), n)
    return out
