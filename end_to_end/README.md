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
