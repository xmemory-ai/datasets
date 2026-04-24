# Memory benchmarking datasets (xmemory)

This repository holds **memory benchmarking datasets** we used at **xmemory**. It is a **mixed bag**: cleaned-up exports, forked material, and semi-manually generated bundles sit side by side.

## Repository layout

Each dataset has its **own top-level directory** under this repo. Some include **cooking or generation scripts** alongside the data.

## Benchmark bundle layout

Every published bundle follows the same **three-level YAML layout**:

```text
<benchmark>.yml             # benchmark — metrics, thresholds, pointer to dataset
<benchmark>/                # dataset directory
  ├── dataset.yml           # dataset — scenario + instance setup (the schema)
  └── inputs/
      └── data.yml          # inputs — write/read actions with labels
```

In short, **benchmark → dataset → inputs**: a benchmark points at a dataset; the dataset's scenario and instance setup describe the schema; the inputs are the sequence of writes, reads, and evals against a memory system.

## Format

We publish datasets in our own **YAML shape**. The structure is small and self-evident from the files, so it is straightforward to consume with standard YAML tooling or AI-assisted coding.
