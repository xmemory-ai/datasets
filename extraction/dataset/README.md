# Insurance Claims Extraction Dataset

This directory contains the structured extraction dataset used for evaluating object-level usability in insurance-claim information extraction.

## Goal

Extraction reporting should prioritize object-level usability, not only field-level overlap. Alongside field metrics, evaluation emphasizes strict object correctness, error type breakdowns, and validation-loop dynamics (retry rate and convergence behavior).

Because the extraction architecture uses local retries, convergence curves are treated as a system-health signal.

## Dataset

We evaluate structured extraction on the insurance claims dataset from Cleanlab's structured output benchmark:

- https://github.com/cleanlab/structured-output-benchmark

Each example pairs:

- an insurance claim document text
- a ground-truth structured record

The core dataset wiring is defined in [dataset.yml](dataset.yml), with:

- input file: [inputs/insurance_claims_extraction.csv](inputs/insurance_claims_extraction.csv)
- schema: [schema.json](schema.json)
- text column: `claim_text`
- ground-truth column: `ground_truth`

## Schema Coverage

Ground-truth objects follow a schema with four areas:

1. Basic claim
2. Insurance policy information
3. List of insured objects
4. Incident information

These structured objects serve as the reference output for all evaluation runs.

## Metrics

We report three complementary metrics with increasing strictness:

1. Field-level precision / recall / F1
2. Object-level accuracy
3. Output-level accuracy

Definitions:

- Field-level precision / recall / F1: computed over individual scalar fields.
- Object-level accuracy: proportion of individual objects where every field exactly matches ground truth.
- Output-level accuracy: proportion of claims where all extracted objects are fully correct (entire structured output matches ground truth).
