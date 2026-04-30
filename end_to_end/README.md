# End-to-end datasets

This directory contains **end-to-end benchmark datasets** across multiple domains: corporate, education, finance, and medical.

## What these datasets represent

Each domain-specific dataset represents a **real-world memory scenario** with its own context and read/write patterns. The datasets are designed to test memory system performance across diverse use cases and query patterns relevant to each domain.

## Layout

Each domain has its own directory with a **benchmark YAML** file and supporting structure:

```text
end_to_end/
├── corporate.yml
├── corporate/
│   ├── dataset.yml
│   ├── schema.yml
│   └── inputs/
│       └── data.yml
├── education.yml
├── education/
│   ├── dataset.yml
│   ├── schema.yml
│   └── inputs/
├── finance.yml
├── finance/
│   ├── dataset.yml
│   ├── schema.yml
│   └── inputs/
├── medical.yml
└── medical/
    ├── dataset.yml
    ├── schema.yml
    └── inputs/
```

Each domain follows the repo-wide **benchmark → dataset → inputs** layout (see the top-level `README.md`).

## Domains

| Domain | Purpose |
|--------|---------|
| **corporate** | Business scenarios with internal processes and workflows |
| **education** | Educational settings with student, instructor, and course data |
| **finance** | Financial transactions and account management scenarios |
| **medical** | Healthcare scenarios with patient records and medical data |

## Using these datasets

Each domain dataset can be consumed independently using standard YAML tooling. The `dataset.yml` describes the schema and scenario setup, while `inputs/data.yml` contains the sequence of write and read operations to evaluate against a memory system.

---

## Appendix A — LLM judge prompt (precision / recall / F1)

To calculate precision / recall metrics we send one message to the judge model per read result. Prompt is below:

```
Evaluate the precision and recall of the 'Prediction' compared to the 'Label' based on the User Query.

===== Query =====
<query>
===== Label (Ground Truth) =====
<label>
===== Prediction =====
<prediction>
====================

Step 1: Count facts
- Count the total number of distinct facts in the Label. For lists, count each item as one fact.
- Count the total number of distinct facts in the Prediction. For lists, count each item as one fact.
- If an answer is "[empty answer]" or blank, decide from the Query and the other answer whether it
  semantically means that the requested value is absent. If yes, count that absence claim as one fact
  rather than zero missing text.

Step 2: Identify matches and mismatches
- True Positives (TP): Facts in Prediction that match facts in Label (semantic equivalence OK).
- False Positives (FP): Facts in Prediction that do NOT match any fact in Label (incorrect or extra wrong info).
- False Negatives (FN): Facts in Label that are NOT captured in Prediction (missed facts).

Step 3: Compute metrics
- Precision = TP / (TP + FP) = fraction of Prediction facts that are correct.
- Recall    = TP / (TP + FN) = fraction of Label facts that are captured.
- If Prediction is blank and does not semantically assert any fact, precision is 0.
- If Label is empty, recall is 1 (nothing to recall).

Guidelines:
1. Consider semantic equivalence, not just exact string matching.
2. Ignore formatting differences (e.g. "19 Jan" vs "January 19th", list order, punctuation).
3. Extra correct information in Prediction (superset) is NOT a false positive.
4. Only genuinely incorrect or contradictory information counts as false positive.
5. Treat blank or missing answers as equivalent to explicit absence answers only when the Query
   makes clear that both answers assert the absence of the requested value.
6. If one answer is empty and the other explicitly states that no value exists, they should be
   treated as the same fact when they communicate the same absence.
7. If you determine the Label and Prediction express the same fact, set precision = 1.0,
   recall = 1.0, and return empty false_positives and false_negatives lists.

Response Format:
Provide a JSON object with:
- "reasoning": A brief explanation of your assessment.
- "label_facts_count": Integer count of facts in Label.
- "prediction_facts_count": Integer count of facts in Prediction.
- "precision": A float between 0.0 and 1.0.
- "recall": A float between 0.0 and 1.0.
- "false_positives": A list of strings describing each false positive (incorrect facts in Prediction).
- "false_negatives": A list of strings describing each false negative (missed facts from Label).
```

### Response JSON schema

```json
{
  "type": "object",
  "properties": {
    "reasoning":               { "type": "string" },
    "label_facts_count":       { "type": "integer" },
    "prediction_facts_count":  { "type": "integer" },
    "precision":               { "type": "number" },
    "recall":                  { "type": "number" },
    "false_positives":         { "type": "array", "items": { "type": "string" } },
    "false_negatives":         { "type": "array", "items": { "type": "string" } }
  },
  "required": [
    "reasoning", "label_facts_count", "prediction_facts_count",
    "precision", "recall", "false_positives", "false_negatives"
  ]
}
```

Metrics are calculated as follows:

```
Precision = (prediction_facts_count - length(false_positives)) / prediction_facts_count
Recall = (label_facts_count - length(false_negatives)) / label_facts_count
F1 = 2 * Precision * Recall / (Precision + Recall​)
```

---

## Appendix B — Synthesis prompt (third-party backends)

Third-party backends (Mem0, Zep, Supermemory, Cognee) return retrieved memory snippets rather than a finished answer. These snippets are passed through a synthesis LLM call to produce the string that the metric judges.

### System prompt

```
You are a memory retrieval assistant.
Answer the user's question concisely and directly, using only the provided memories.
If the memories do not contain a clear answer, say so briefly.
```

### User message shape

```
Memories:
- <memory 1>
- <memory 2>
- …

Question: <read query>
```

Placeholders:

- `<memory N>` — one retrieved fact/snippet per bullet, as returned by the backend's search API.
- `<read query>` — the verbatim `query` field from the `read` action in `inputs/data.yml`.

The synthesis call uses no JSON schema (free-text answer). The resulting string is what the LLM judge in Appendix A receives as `<prediction>`.
