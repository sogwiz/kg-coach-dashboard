# AI Engineer Take-Home

A staff-level take-home for AI engineering candidates: build a **knowledge graph** from exercise data and clinical ontologies, then a **coach dashboard** on top of it — an **AI workout generator** and a **member-context copilot** — that gives **safe, personalized, explainable** recommendations.

- **Time:** 1 day
- **Stack:** your choice — we want you to pick the tools and defend them
- **Data:** synthetic only (provided in [`data/`](./data)); never use real member data

## What's in this repo

| Path | Purpose |
|------|---------|
| [`ASSESSMENT.md`](./ASSESSMENT.md) | The full take-home spec — task, knowledge graphs, ontologies, build steps, deliverable |
| [`data/exercises.json`](./data/exercises.json) | Exercise catalog (50 exercises) |
| [`data/member-context.json`](./data/member-context.json) | One rich synthetic member: profile, goals, injuries, chat history, biomarkers, labs (blood panel + DEXA), adherence, churn signals |

## The gist

Two surfaces in one coach dashboard:

1. **Workout Generator** — a prompt + time form that calls an agentic runtime and renders a structured workout. It reasons over a **movement/clinical knowledge graph** (grounded in ontologies like OPE, COPPER, SNOMED CT, PROV-O, SKOS) to keep recommendations injury-aware, equipment-aware, and explainable.
2. **AI Copilot** — a chat panel with retrieval over a **member-context knowledge graph**: adherence trends, sleep, churn risk, the morning brief, charts, and past conversations.

See [`ASSESSMENT.md`](./ASSESSMENT.md) for the complete spec.

## Submitting

Build in a GitHub repo with a comprehensive README (architecture and tech-choice rationale, how to run locally, how you used AI, and your trade-offs). Use synthetic data only, then share the link.
