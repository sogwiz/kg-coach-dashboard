# Architecture — Knowledge-Graph-Backed Coach Dashboard

How the system is put together, how a request flows through it, and the
architecture-level decisions behind it. Companion to the deep ontology
write-up in `graph-design-decisions.html` and the requirements in
`requirements.md`.

**One-line thesis:** the **graph does the work the prompt cannot** — concept
resolution and safety are **deterministic graph operations**; the LLM only ever
sees an already-safe candidate set and structures it into a session.

---

## 1. System architecture

```mermaid
graph TB
  subgraph Client["Frontend — React 19 + Vite + Tailwind"]
    UI["Coach Dashboard\n(login, member view, overview hero)"]
    GEN["Generator Panel\n+ Stimulus Gauges + Regenerate"]
    COP["Copilot (chat)"]
    GRAPH["Graph Explorer"]
    CANVAS["Creative Canvas"]
  end

  subgraph API["Backend — FastAPI"]
    AUTH["/api/auth (mock)"]
    MEM["/api/members"]
    INJ["/api/.../injuries (check-in)"]
    GENR["/api/generate (+ regenerate, refine, select, send)"]
    COPR["/api/copilot/chat (streaming)"]
    GRAPHR["/api/graph"]
  end

  subgraph Core["Reasoning core"]
    RES["3-pass Concept Resolver\nexact → fuzzy → embedding"]
    FILT["Conditional Safety Filter\n(deterministic graph traversal)"]
    PIPE["Generator Pipeline\n(single variant)"]
    AGENT["Copilot Agent\nLangGraph + tools + memory"]
    OBS["Observability\nDecision Trace + LangSmith"]
  end

  subgraph Graphs["Knowledge graphs — networkx MultiDiGraph"]
    KG1["KG1 Movement/Clinical\nexercises·muscles·joints·patterns·equipment·injuries"]
    KG2["KG2 Member Context\nprofile·goals·injuries·biomarkers·labs·chat·adherence"]
    CONCEPTS["Shared concept catalog\nSKOS labels · SNOMED part-of"]
  end

  subgraph External["Models"]
    LLM["Anthropic Claude\nclaude-haiku-4-5"]
    EMB["sentence-transformers\nall-MiniLM-L6-v2 (local, CPU)"]
  end

  UI --> AUTH & MEM & INJ
  GEN --> GENR
  COP --> COPR
  GRAPH --> GRAPHR
  CANVAS --> GENR

  GENR --> PIPE
  PIPE --> RES --> CONCEPTS
  PIPE --> FILT --> KG1
  PIPE --> LLM
  PIPE --> OBS
  COPR --> AGENT --> KG2
  AGENT --> LLM
  GRAPHR --> FILT
  RES --> EMB

  KG1 --- CONCEPTS
  KG2 --- CONCEPTS
```

**Key structural fact:** KG1 and KG2 **share the same concept nodes** (e.g.
`joint:knee`, `equipment:barbell`). That shared vocabulary is the join key —
the member's injury and the exercise catalog meet at a canonical graph node, so
there is **no free-text matching at runtime**.

---

## 2. Component responsibilities

| Layer | Component | Responsibility |
|-------|-----------|----------------|
| **Frontend** | Dashboard / hooks (`useGenerator`, `useCopilot`, `useInjury`, `useGraph`) | Render surfaces; typed `fetch` wrappers in `lib/api.ts`; per-member state. |
| **API** | FastAPI routers | Thin HTTP boundary; typed Pydantic request/response; no business logic. |
| **Resolver** | `resolver/` | Free text → canonical concept. 3 passes with confidence thresholds; `low_confidence`/`no_match` degrade gracefully. |
| **Safety** | `graph/safety_filter.py`, `graph/conditional_filter.py` | **Deterministic** exclusion by `part-of` traversal + today's injury state + equipment + dislikes. Runs **once** per generation. |
| **Generator** | `generator/pipeline.py`, `generator/llm.py` | Filter → **single** LLM structuring call (`with_structured_output → WorkoutPlan`) → provenance + decision trace. |
| **Copilot** | `copilot/agent.py` | LangGraph agent; tools retrieve over KG2; `MemorySaver` checkpointer keyed by `member_id`; `current_workout_plan` tool makes it workout-aware. |
| **Graphs** | `graph/movement_kg.py`, `graph/member_kg.py` | `networkx.MultiDiGraph`; traversal helpers (`descendants_by_part_of`, `exercises_stressing`). |
| **Ontology** | `ontology/` | SKOS concept catalog; baked `snomed_anatomy.json` (`part-of` subtree); loaders. |
| **Observability** | `observability/` | In-app `DecisionStep[]` trace (with per-phase timings) + optional LangSmith run links. |
| **Stores** | in-memory dicts | Plan store (per-member current plan), injury check-in store, workout-send store. Process-lifetime. |

---

## 3. Workout-generation workflow

```mermaid
flowchart TD
  A["Coach: prompt + time window"] --> B["Resolve prompt concepts\n(3-pass resolver)"]
  B --> C["Load member constraints\nequipment · dislikes · injuries"]
  C --> D["Conditional Safety Filter — ONE pass"]
  D --> D1["part-of traversal from injured joint\n(SNOMED descendants)"]
  D --> D2["movement-type exclusion\n(today's pain_on + healing phase)"]
  D --> D3["equipment gate"]
  D --> D4["dislikes / explicit excludes"]
  D1 & D2 & D3 & D4 --> E["SAFE candidate set\n(LLM never sees unsafe exercises)"]
  E --> F["LLM structuring — single call\nwarmup/main/cooldown + sets/reps/rest\n+ sequencing + stimulus_distribution"]
  F --> G["WorkoutPlan + Provenance (PROV-O)\n+ Decision Trace (timed)"]
  G --> H["Store as member's current plan"]
  H --> I["Render: plan + gauges + provenance + trace"]
  I --> J{"Regenerate?"}
  J -- "with prior-plan context + optional tweak" --> D
```

**Why one filter, one LLM call.** The safety filter is the load-bearing,
deterministic step and runs exactly once. The coach's prompt already sets the
modality, so the generator makes a **single** structuring call (not three) — the
plan reports its own strength/conditioning/mobility **stimulus distribution**,
shown as thermometer gauges. Regenerate re-enters the same pipeline but feeds
the previous session to the LLM so the result is a fresh, distinct variation.

---

## 4. Data flow (read paths + write paths)

```mermaid
flowchart LR
  subgraph Seed["Seed data (synthetic)"]
    EX["exercises.json"]
    MV["exercise_movements.json"]
    MB["members/*.json"]
    SN["snomed_anatomy.json"]
  end

  EX & MV & SN --> KG1B["Build KG1 at boot"]
  MB --> KG2B["Build KG2 per member"]
  KG1B --> KG1[("KG1")]
  KG2B --> KG2[("KG2")]

  subgraph Runtime
    REQ["Coach request"] --> RESV["Resolver"] --> KG1
    KG1 --> FLT["Safety filter"] --> SAFE["Safe set"]
    SAFE --> STRUCT["LLM structuring"] --> PLAN["WorkoutPlan"]
    PLAN --> STORE[("In-memory plan store")]
    STORE --> COPILOT["Copilot tool: current_workout_plan"]
    KG2 --> COPILOT
    COPILOT --> ANS["Grounded answer"]
  end

  CHECKIN["Injury check-in\n(today's state)"] --> FLT
```

- **Boot:** graphs are constructed from synthetic JSON; the MiniLM embedding
  corpus is precomputed once. SNOMED `part-of` is **baked**, not fetched live.
- **Per request:** resolve → traverse → filter → structure. The only network
  hop is to the LLM.
- **State:** check-ins, the current plan, and sends live in process-lifetime
  in-memory stores (no DB by design — synthetic, single-process, fast to reason
  about).

---

## 5. Use-case flow — "Her left knee is bothering her"

The canonical injury scenario (Jordan Rivera, recovering left-knee PFPS), end to
end:

```mermaid
sequenceDiagram
  participant C as Coach (UI)
  participant API as FastAPI /api/generate
  participant P as Generator Pipeline
  participant KG1 as Movement KG
  participant F as Conditional Safety Filter
  participant L as Claude (Haiku)

  C->>API: prompt "lower body strength", 40 min, member=Jordan
  API->>P: generate_workout(input, kg, member, llm)
  P->>KG1: descendants_by_part_of("knee")
  KG1-->>P: {knee joint, patellofemoral joint, ...} (SNOMED part-of)
  P->>F: conditional_safety_filter(candidates, injury=left-knee, today's state)
  Note over F: exclude exercises that STRESS any knee sub-structure<br/>+ pain_on movement types + equipment (no barbell) + dislikes
  F-->>P: FilterTrace{ safe[], removed[(ex, reason)] }
  P->>L: structure ONLY the safe set → WorkoutPlan (single call)
  L-->>P: warmup/main/cooldown + sequencing + stimulus_distribution
  P-->>API: WorkoutPlan + Provenance(PROV-O) + DecisionTrace(timed)
  API-->>C: plan + gauges + "filtered out: Barbell Back Squat — stresses knee (flexion, load)"
```

**What the coach sees:** a knee-safe session, the **stimulus gauges**, and a
**provenance trace** naming each excluded exercise, the **specific injury** it
was excluded for, and the graph reason (e.g. *"Barbell Back Squat — excluded for
left knee (PFPS): stresses patellofemoral joint via part-of; pain on
flexion+load"*). No part of this is a prompt instruction — it is graph traversal.

---

## 6. Architecture-relevant decisions

Condensed from `graph-design-decisions.html` (full reasoning + trade-offs there).

| Decision | Choice | Why it's an architecture decision |
|----------|--------|-----------------------------------|
| **Graph store** | `networkx.MultiDiGraph` in-process | No external DB; the dataset is ~100 nodes. MultiDiGraph supports parallel typed edges (`stresses`, `targets`, `requires` between the same pair). Traversal is a library call, not a query language. |
| **Two graphs, one vocabulary** | KG1 + KG2 share concept nodes | The join key for member↔catalog reasoning. Injury (KG2) and exercise (KG1) meet at `joint:knee` — no runtime fuzzy join. |
| **Safety = traversal** | `part-of` descent + movement-typed `stresses` | Deterministic, reproducible, auditable. The LLM is structurally prevented from seeing unsafe exercises. |
| **Movement-typed `stresses`** | edges carry `flexion/extension/rotation/load/impact` | Lets the filter exclude by **today's** pain triggers, not just "knee is injured" — state-aware safety. |
| **`contraindicated-for` as a stored edge** | materialized baseline + dynamic filter | Static "textbook" view powers the Graph Explorer; the conditional filter remains the live runtime authority. |
| **SNOMED baked, not live** | `snomed_anatomy.json` snapshot | Determinism + offline + no API dependency on a safety path. |
| **Concept resolution** | 3-pass exact → fuzzy (`rapidfuzz`) → embedding (`all-MiniLM-L6-v2`) | Cheap, local, last-resort ML; low-confidence surfaces ambiguity instead of guessing. |
| **Embedding model** | `all-MiniLM-L6-v2` (local, ~90 MB, CPU) | Keep the safety-critical path local/deterministic/cheap; baked into the image. (See decisions doc for the alternatives table.) |
| **Generator shape** | single variant + stimulus gauges | One filter pass, one LLM call; modality comes from the prompt; gauges report emphasis. Faster + cheaper than the original 3-variant fan-out. |
| **Copilot grounding** | LangGraph agent, tools over KG2, `MemorySaver` per member | Answers come from KG tools (never invented); conversation memory keyed by `member_id`; workout-aware via the plan store. |
| **Observability** | in-app `DecisionStep[]` (timed) + LangSmith | The deterministic graph decisions are inspectable in-app; LLM/agent runs trace to LangSmith. |

---

## 7. Deployment

```mermaid
flowchart LR
  subgraph compose["docker compose (single command)"]
    FE["frontend\nnginx serves built SPA\nproxies /api → backend"]
    BE["backend\nFastAPI + baked seed data\n+ cached MiniLM model"]
  end
  USER["Browser :8080"] --> FE --> BE
  VOL[("hf_cache volume\nMiniLM model")] --- BE
```

- **`docker compose up --build` → http://localhost:8080.** Seed JSON is baked
  into the backend image (no external DB). The MiniLM model is downloaded once
  on first boot into a persistent `hf_cache` volume.
- Local dev alternative: `make dev` (Vite :5173 + FastAPI :8000).

---

## 8. Tech stack & rationale (summary)

| Concern | Choice | One-line why |
|---------|--------|--------------|
| Backend | **FastAPI + Pydantic** | Typed contracts, async, minimal ceremony. |
| Graph | **networkx** | Right-sized in-process graph; traversal as a function call. |
| LLM | **Anthropic Claude `claude-haiku-4-5`** | Fast structured output for plan structuring + copilot. |
| Structured output | **LangChain `with_structured_output`** | LLM emits a valid `WorkoutPlan` directly. |
| Agent | **LangGraph** | Tool-calling + checkpointed conversation memory. |
| Embeddings | **sentence-transformers MiniLM** | Local, cheap, last-resort resolver pass. |
| Frontend | **React 19 + Vite + Tailwind v4** | Fast DX; warm editorial design system. |
| Charts | **Recharts** | Adherence / sleep / biomarker / injury-progress. |
| Graph viz | **react-force-graph** | Provenance + explainability over KG1. |
| Tracing | **LangSmith** (optional) | LLM/agent observability; degrades off when unset. |
