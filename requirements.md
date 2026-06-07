# Requirements — Knowledge-Graph-Backed Coach Dashboard

> Distilled from the take-home brief (`ASSESSMENT.md`, `README.md`). This is the
> normative requirements list the implementation is held against. Each item has
> a stable ID so the architecture doc, README worked-examples, and tests can
> reference it.

**Project:** a coach-facing dashboard that generates **safe, personalized,
explainable** workouts and lets a coach retrieve member context through an AI
copilot. The defining constraint: **recommendations are driven by a knowledge
graph, not by the language model alone.** Safety must be enforced
**deterministically through graph traversal**, never as a prompt instruction.

- **Time budget:** 1 day · **Stack:** free choice, must be justified · **Data:** synthetic only — never real member data.

---

## 1. Functional requirements

### 1.1 Workout Generator (Surface A)

| ID | Requirement |
|----|-------------|
| **FR-G1** | Accept a coach **free-text prompt** (e.g. "full-body with pec isolation", "lower-body that avoids aggravating a knee injury") **and a time window**. |
| **FR-G2** | Call an **agentic workout-generation runtime** and render a **structured workout** in the browser: **warmup / main / cooldown**, each with **sets, reps, and rest**. |
| **FR-G3** | Support **interactive, graph-driven adjustment**: |
| FR-G3a | "Exclude deadlifts" → no deadlift variations appear. |
| FR-G3b | "Her left knee is bothering her" → exclude/down-rank exercises that stress the knee **via the anatomy hierarchy** (sub-structures count too). |
| FR-G3c | "She has no barbell, only dumbbells and a kettlebell" → drop barbell-only exercises and **find equivalent alternatives**. |
| **FR-G4** | Every generated plan ships with a **provenance trace**: why each exercise was chosen, which graph path justified it, and what was filtered out for safety. |

### 1.2 Coach AI Copilot (Surface B)

| ID | Requirement |
|----|-------------|
| **FR-C1** | A **chat panel with retrieval over the member's context** (Member KG) — answers grounded in the member's actual data, **not invented**. |
| **FR-C2** | Support a **quick-prompt palette** (e.g. *Show me the brief*, *How's adherence trending?*, *Sleep this week*, *What changed since last week?*). |
| **FR-C3** | Render **charts** (e.g. adherence trend, sleep, message pattern, last-4-weeks comparison). |
| **FR-C4** | Surface the **morning brief** and **churn risk** for the active member. |
| **FR-C5** | Show **past chat history and images**; support **follow-up questions** (conversation memory). |

### 1.3 Dashboard (shell)

| ID | Requirement |
|----|-------------|
| **FR-D1** | **Coach login** (mock auth is acceptable). |
| **FR-D2** | A **member view**, the **generator panel**, and the **copilot panel**, with chart rendering and chat history/images. |

---

## 2. Knowledge-graph requirements

### 2.1 KG1 — Movement / Clinical Domain graph

| ID | Requirement |
|----|-------------|
| **KG1-N** | **Nodes:** exercises, muscles, joints / body regions, movement patterns, equipment, injuries / conditions. |
| **KG1-E** | **Edges:** `targets` (muscle), `stresses` (joint/region), `requires` (equipment), `part-of` (anatomy hierarchy), `contraindicated-for` (injury → unsafe movements). |
| **KG1-T** | Map the catalog taxonomy (**19 muscle groups, 9 joints, 36 movement patterns, 32 equipment types**) onto ontology concepts via **SKOS** mappings. |
| **KG1-P** | Record **why each exercise was selected** with **PROV-O** provenance. |
| **KG1-S** | **Document the schema** — node types, edge types, and what each means. |

### 2.2 KG2 — Member Context graph

| ID | Requirement |
|----|-------------|
| **KG2-I** | Ingest the synthetic member (`data/member-context.json`): profile, goals, preferences, injuries, **chat history**, **biomarkers** (resting HR, HRV, sleep), **lab results** (blood panel + DEXA), workout history, adherence, churn signals. |
| **KG2-R** | This graph is **what the copilot retrieves over**. |

---

## 3. Reasoning & pipeline requirements

| ID | Requirement |
|----|-------------|
| **RR-1 · Concept resolution** | Map free text → canonical graph concepts ("knee" → Knee joint, "kettlebell" → Kettlebell equipment, "bad lower back" → lumbar region). A **3-pass resolver** is encouraged: **exact → fuzzy → embedding/vector fallback**, with **explicit confidence thresholds** and **graceful degradation** when nothing matches. |
| **RR-2 · Safety from traversal** | Filter/down-rank the catalog by **walking edges**: injured joint (through `part-of`), available equipment, explicit exclusions, preferences. The safety decision **must be a graph traversal, not a prompt sentence**. |
| **RR-3 · Agentic runtime** | Turn the form (prompt + time) into a structured plan **plus the provenance trace**. |
| **RR-4 · Tests** | At minimum the **concept resolver** and the **safety filter**; pick the critical paths and **explain why**. |

---

## 4. Ontology grounding requirements

Ground the domain graph in real ontologies — **a small, well-justified subset used meaningfully beats wiring up everything shallowly.**

| Ontology | Use for |
|----------|---------|
| **OPE** (Ontology of Physical Exercises) | Exercises, musculoskeletal systems, equipment, injuries. |
| **COPPER** | Personalization / behaviour-change concepts. |
| **SNOMED CT** (via NCI EVS) | Clinical anatomy, joints, injuries / conditions. |
| **PROV-O** | Provenance — why a recommendation was made. |
| **SKOS** | Concept mapping (catalog/free-text terms ↔ ontology concepts). |

**Required reasoning (documented):** *what to pull* from each ontology and *what to leave out*; *why* those concepts matter for safe, personalized recommendations; *how to store it* (graph-store choice, schema, catalog↔concept mapping); *how the two graphs relate*.

---

## 5. Non-functional requirements

| ID | Requirement |
|----|-------------|
| **NFR-1 · Determinism** | Safety constraints enforced by graph traversal — reproducible, auditable, never probabilistic. |
| **NFR-2 · Performance** | Aim for AI responses **under ~5s**; be reasonable about token efficiency. |
| **NFR-3 · One-command run** | The system should run locally, ideally with one command. |
| **NFR-4 · Typed contracts** | Clean component boundaries, typed request/response contracts, sane data flow. |
| **NFR-5 · Synthetic data only** | No real member or personal data, ever. |
| **NFR-6 · Auditability** | Recommendations must be explainable and auditable (provenance + decision trace). |

---

## 6. Deliverables

| ID | Deliverable |
|----|-------------|
| **DEL-1** | Runnable **GitHub repo**. |
| **DEL-2** | **Comprehensive README** (staff-level), defending the work in review. |
| **DEL-3** | **High-level architecture diagram** — components + data flow (dashboard → agentic runtime → KG(s) → LLM/vector store). |
| **DEL-4** | **Architecture & tech-choice rationale** — what and **why** (defend the stack). |
| **DEL-5** | **How to run locally** — ideally one command. |
| **DEL-6** | **How AI was used** to build the project. |
| **DEL-7** | **Challenges, trade-offs, technical decisions** — articulated explicitly. |
| **DEL-8** | **How you'd evaluate in production** — metrics, failure modes, safety monitoring. |
| **DEL-9** | **2–3 example inputs with generated plans** — including **one injury case** and **one limited-equipment case** — showing plan + provenance/filtering trace. |
| **DEL-10** | **Schema documentation** for both knowledge graphs (node/edge types and meanings). |

---

## 7. Evaluation criteria (what's being judged)

- **Graph & ontology modeling** — edge semantics; is the graph doing real work, or "semantic search with extra steps"?
- **Concept resolution** — quality on messy input; graceful degradation.
- **Safety from traversal** — constraints that actually come from the graph, not the prompt.
- **Full-stack product thinking** — does the dashboard help a coach do their job?
- **System design & API** — clean boundaries, typed contracts, sane data flow.
- **Developer experience** — one-command run; clear README.
- **Communication** — articulation of trade-offs and decisions.
- **Working in ambiguity** — where the spec is open, make a decision and explain it.

---

## 8. Nice-to-haves (optional, additive)

Graph visualization · multi-agent orchestration · streaming responses · evaluation pipeline (retrieval relevance, recommendation quality) · observability/tracing of LLM calls, tools, and graph queries · deeper SNOMED grounding · longitudinal reasoning (progression and adherence over time).

---

## 9. Provided data

- **`data/exercises.json`** — 50 exercises. Key fields: `muscle_groups`, `joints_loaded`, `movement_patterns`, `equipment_required`, `priority_tier`, `is_bilateral`, `bilateral_pair_id`.
- **`data/member-context.json`** — one rich synthetic member (**Jordan Rivera**): `profile`, `goals`, `preferences`, `equipment_available`, `injuries`, `workout_history`, `adherence`, `biomarkers`, `labs` (blood panel + DEXA), `chat_history`, `coach_brief`. Set up for the canonical scenarios: a recovering **left-knee** injury, **no barbell** at home, a **declining adherence** trend, and a workout to celebrate.

> All additional data must be generated synthetically.
