# Atlas — Demo Script

A presenter's walkthrough of the knowledge-graph–backed AI coach dashboard.
Optimised for an **8–10 minute live demo** (or screen recording) that lands the
**five key differentiators** and defends the **architecture & ontology** choices —
including *why our NetworkX knowledge graph instead of Neo4j, from an ontology
standpoint*.

> **Format:** each beat has a **DO** (what to click) and a **SAY** (the talking
> point). Verbatim lines are a starting point — make them yours. Times are
> cumulative targets, not a stopwatch.

---

## 0 · Pre-flight (before you hit record)

**DO**
```bash
# One command, from the repo root. Bakes seed data + caches the MiniLM model.
docker compose up --build        # → http://localhost:8080
```
- Open `http://localhost:8080` in a clean, full-width browser window (the
  cinematic login + Insights graph want ≥ 1280px).
- Sign in: **any** email + password (e.g. `coach@atlas.studio` / `atlas`) — demo
  auth accepts anything.
- Confirm the active member is **Jordan Rivera** (the member card sits under the
  header; the switcher toggles **Jordan ⇄ Mico**).
- Have a second tab on `docs/SCHEMA.md` and the README **Ontology Reasoning**
  section in case of deep questions.

**Reset between takes:** state is in-memory — `docker compose restart backend`
returns every member to their seeded check-in and clears copilot threads.

---

## The thesis (say this in the cold open — 0:00–0:30)

> "Most AI fitness tools ask a model to *promise* it won't hurt you. We don't
> trust a language model with safety. Atlas enforces safety **deterministically,
> in a knowledge graph** — the LLM is *physically incapable* of recommending a
> contraindicated exercise, because it never sees one. Everything you'll watch
> generate is **safe by construction, explainable by provenance, and personal to
> the athlete's body** — not a template."

**Keep these five differentiators in your back pocket — every beat ladders to one:**

| # | Differentiator | The one-liner |
|---|----------------|---------------|
| 1 | **Deterministic safety gate** | The graph removes unsafe movements *before* the LLM is called. Safety is a pure function, not a prompt. |
| 2 | **Ontology-grounded reasoning** | A knee injury excludes the *whole knee complex* via SNOMED `part-of` traversal — anatomy, not string-matching. |
| 3 | **Hybrid generation** | The graph makes the decisions (~5s); the model only narrates them. A toggle exposes the full-LLM path for contrast. |
| 4 | **Explainable everywhere** | Stimulus gauges, a phase-timed decision trace, and PROV-O provenance for every kept/removed exercise. |
| 5 | **Grounded copilot** | Trainer↔AI, bound to the active member's graph + brief + inbox. It never asks "what's the member ID," and it cites its sources. |

---

## 1 · The front door & orientation (0:30–1:15)

**DO** — Land on the login; scroll the left column once, then sign in.

**SAY**
> "Quick taste of the product surface — the athlete footage stays pinned while
> the brand story scrolls. Then we're in the coach's studio."

**DO** — Point at the **member card** (Jordan, 41, *Rebuilding Strength*) and the
tab row: **Overview · Generate · Analytics · Insights · Studio**. Note the
floating **copilot bubble** (bottom-right).

**SAY**
> "One coach, many athletes. The card is the active member; every tab and the
> copilot are scoped to *this* person. Jordan is recovering a left knee and
> trains in a home gym — dumbbells, kettlebell, bands. No barbell, no rack. Hold
> that constraint."

---

## 2 · Differentiator #1 + #2 — the safety gate, visualized (1:15–3:00)

> This is the most important 90 seconds of the demo. Slow down here.

**DO** — Open the **Insights** tab (the graph explorer). Toggle the
**"show safety filtering"** view for Jordan.

**SAY**
> "This is the movement-and-clinical knowledge graph: exercises connected to the
> muscles, joints and movement patterns they stress, the equipment they require,
> and the injuries they're contraindicated for. The greyed-out, struck-through
> nodes are **excluded for Jordan**, and each exclusion is **attributed to the
> specific injury** that caused it."

**DO** — Hover an excluded exercise so the attribution shows *"excluded by:
left knee — patellofemoral pain"*.

**SAY** — land the structural point:
> "Here's the part people miss. We are **not** string-matching the word 'knee.'
> Jordan's injury joint is `knee`, and we walk SNOMED CT's `part-of` anatomy
> hierarchy from the knee structure down to **every component** — patellofemoral
> joint, tibiofemoral joint, medial and lateral meniscus. Then we remove every
> exercise that stresses *any* of those nodes **with a movement type Jordan can't
> tolerate today** — flexion, load. A deep lunge never mentions 'patellofemoral
> joint,' but the ontology knows it lives inside the knee, so it's gone."

> "And it's a **pure function** — no network, no LLM, no side effects. It runs
> once per generation, it's unit-tested as a safety invariant, and it's the
> *only* thing standing between the athlete and harm. The model downstream is a
> writer, not a gatekeeper."

**Anticipated question — "what if there's no movement-type annotation?"**
> "We fail safe. Watch Mico later: exercises that stress the lumbar spine but
> *lack* a movement annotation are removed anyway — conservative exclusion. We'd
> rather drop a safe exercise than keep a risky one."

---

## 3 · Differentiator #3 + #4 — generate a session (3:00–5:00)

**DO** — Open the **Generate** tab. Note the **session intent** field is
**pre-filled from Jordan's morning brief**. Leave the **Engine** toggle on
**Hybrid**. Click **Generate session**.

**SAY** (while it streams)
> "The intent is seeded from this morning's coach brief, so the coach starts from
> a recommendation, not a blank box. Notice the stream: it reports
> **resolve → safety → structuring → plan**. The safety counts land in about a
> second — for Jordan, **17 exercises safe, 54 removed** — so you *see* the gate
> fire before any prose exists."

**DO** — When the plan lands, point to the **stimulus gauges**.

**SAY**
> "Differentiator: the modality isn't a label the model claimed — these gauges are
> **measured from the actual plan** — how much strength, conditioning, and
> mobility stimulus the prescribed exercises, sets and reps actually deliver."

**DO** — Read the **"Why this session"** rationale, then expand the
**Decision Trace**.

**SAY**
> "Every plan explains itself. The decision trace shows each pipeline phase
> **timed** — resolve, safety filter, assembly, narration — and the provenance
> records, per exercise, *why it was kept* and, for the 54, *why it was removed*,
> with the SNOMED path that justified it. That's PROV-O — auditable lineage, not
> vibes."

**DO** — Now flip **Engine → Full LLM** and regenerate (or just explain).

**SAY**
> "Same safe set, two engines. **Hybrid** — the default — lets the *graph* assemble
> the structure and the model write only ~four sentences of narration: ~5
> seconds. **Full LLM** hands the whole structuring job to the model: richer
> per-exercise prose, ~20 seconds. The toggle exists because the right answer is
> 'depends,' and we wanted to *measure* it, not guess. Critically — **both engines
> only ever see the post-filter safe set.** The engine choice changes speed and
> prose, never safety."

---

## 4 · Differentiator #5 — the grounded copilot (5:00–6:30)

**DO** — Click the **copilot bubble**. With Jordan active, type:
> `what kind of workout would be good for today?`

**SAY**
> "Watch what it does **not** do — it doesn't ask 'which member?' It's bound to
> Jordan and to the tab I'm on. It already knows the knee, the remodeling phase,
> today's check-in, and this morning's brief, and it answers in that context."

**DO** — Ask a **general-knowledge** question the member file can't answer:
> `how does a 5x5 program differ from HYROX conditioning?`

**SAY**
> "Now it reaches into a **retrieval corpus** — a small library of training
> methodologies: StrongLifts 5×5, Wendler 5/3/1, Zone 2, CrossFit, HYROX,
> Tactical Games, TB12, RPE/RIR autoregulation, deloads, nutrition. It searches
> by embedding similarity with a keyword fallback and answers from sources. But
> note: **this corpus is an *enrichment* surface — it is never on the safety
> path.** Safety is structural graph traversal; retrieval is just knowledge."

**DO** — Ask something that references a client message, e.g.:
> `did Jordan mention anything about the knee this week?`
Show the copilot **deep-linking** to the relevant inbox message.

**SAY**
> "And it's wired to the client inbox — it can cite and **jump you straight to**
> the message it's referring to. The copilot is the coach's analyst; it reads the
> same context the coach has."

---

## 5 · Copilot vs. client chat — a deliberate separation (6:30–7:00)

**DO** — Click the **mail** button on the member card to open the **Client Inbox**
(trainer↔client). Contrast it with the copilot drawer (trainer↔AI).

**SAY**
> "Two different conversations, deliberately separate. The **inbox** is what you
> say to the athlete. The **copilot** is what you ask the AI *about* the athlete —
> and it's *aware* of the inbox without ever being mistaken for it. We never blur
> 'message my client' with 'ask my assistant.'"

---

## 6 · Studio — intended vs. actual stimulus (7:00–7:45)

**DO** — Open the **Studio** tab (Creative Canvas). Show the calendar-style grid:
**Warmup / Mobility · Main · Cooldown**. Drag an exercise or two, then click
**Synthesize**.

**SAY**
> "This is the manual bench for a coach who wants to build by hand. The grid is a
> session — warmup and mobility, main work, cooldown. The differentiator is
> **Synthesize**: it reads the actual exercises, sets, reps and loads and tells
> the coach what the session will *actually* do. The classic failure it catches:
> 'I *meant* to write strength, but my scheme is really hypertrophy / strength-
> endurance.' Intended stimulus vs. delivered stimulus, made explicit."

---

## 7 · Prove it generalizes — switch to Mico (7:45–8:30)

**DO** — Switch the member to **Mico** (lumbar spine, *full* gym). Open
**Generate** — note the intent is pre-filled to *avoid loaded lumbar flexion*
from his brief — and generate.

**SAY**
> "Different athlete, opposite constraints — managing mechanical low-back pain,
> and a *fully* stocked gym. Same generation, and **40 safe / 31 removed**. The
> exact same `conditional_safety_filter` function ran — only the injured joint,
> its SNOMED `part-of` subtree, and today's check-in changed. The knee logic
> wasn't special-cased; the design is **anatomy-agnostic.** And you'll see the
> **conservative-exclusion** behavior here — lumbar-stressing exercises without a
> movement annotation are dropped anyway."

---

## 8 · Architecture & ontology — *why our graph, not Neo4j* (8:30–9:45)

> This is the segment for a technical audience. If pressed for time, deliver the
> three **bolded** sentences and move on.

**SAY — the shape of the system**
> "Under the hood there are **two knowledge graphs**. **KG1** is the
> movement/clinical graph — exercises, muscles, joints, patterns, equipment,
> injuries, and the `stresses / targets / requires / part-of / contraindicated-for`
> edges. **KG2** is member context — goals, history, adherence, check-ins. The
> generator resolves the coach's words to graph concepts, KG1's safety filter
> produces the safe set, and only then does an LLM structure or narrate it."

**SAY — the ontology grounding (this is the substance reviewers ask about)**
> "The reasoning is grounded in real ontologies, and we were deliberate about
> what we pulled in versus left out:
> - **SNOMED CT** gives us the load-bearing `part-of` **anatomy hierarchy** — the
>   reason a knee injury reaches the patellofemoral joint and the menisci. We bake
>   just the two injury subtrees we need from the NCI EVS API; we don't ship
>   360,000 concepts.
> - **OPE** (physical-education ontology) inspired the **movement vocabulary**
>   — exercise→muscle→joint→equipment — but its OWL was alpha-quality, so we
>   hand-rolled the catalog against the real data and kept the *concept*.
> - **SKOS** `altLabel` synonyms feed the concept **resolver** so 'bad lower back'
>   resolves to `lumbar_spine`.
> - **PROV-O** is the vocabulary for the **provenance trace** — derived-from, used,
>   and the `graph_path` that justifies each exclusion."

**SAY — the question you came for: why NetworkX and not Neo4j**

> **"Neo4j is a *storage and query engine*; it is not an ontology. The ontology
> lives in our *schema and our edges*, not in the database we keep them in — so
> switching to Neo4j would buy us zero additional semantics."** Then the specifics:

- **Category fit.** Our ontology lineage is **RDF/OWL-flavored** — SNOMED, SKOS,
  PROV-O. Neo4j is a **labeled-property-graph** store; it doesn't do OWL
  subsumption or `part-of` transitive *inference* natively. **If** we wanted true
  ontological reasoning, the right tool is an RDF triplestore + reasoner
  (RDFLib / owlready2), **not** Neo4j. So "use Neo4j because it's a graph DB" is a
  category error — it's a *graph store*, not a *reasoner*.

- **The reasoning we actually need is a bounded traversal, baked.** The safety
  invariant is one operation: `descendants_by_part_of(joint)` over a **single
  edge type**, on a **read-only** graph of ~200–400 nodes. We compute the
  transitive closure we need from SNOMED **once, at build time**, and commit the
  snapshot. There is no query workload that needs index-free adjacency at scale,
  no Cypher, no second source of truth.

- **Determinism & testability win.** Safety must be **100% deterministic and
  unit-tested**. A pure-Python traversal over an in-memory `MultiDiGraph` is
  trivially reproducible and lives inside the test suite — no fixture database,
  no eventual consistency, no DB state to seed in CI. A network hop to a graph
  server would make the *safety gate* depend on infrastructure. That's the wrong
  place to add a moving part.

- **The usual reason to adopt Neo4j — built-in search — we don't need for safety.**
  A competing approach reaches for Neo4j's full-text/vector index to do RAG.
  But **safety is structural traversal, not search**, and for the *enrichment*
  RAG we run MiniLM cosine in-process over a 12-document corpus. Neither path
  benefits from a graph database.

- **Operational honesty.** NetworkX keeps the deliverable to **one
  `docker compose up`** with the data baked in. Neo4j would add a container,
  drivers, an index-build step, and a provisioning story — real operational
  surface, for **no capability we're missing** at this scale.

> "The rule of thumb: **reach for Neo4j when the graph is large, write-heavy, and
> the queries are deep, multi-hop, and ad-hoc.** Ours is small, read-only, and the
> one traversal that matters is bounded and precomputed. The honest engineering
> answer is the in-process graph — and the ontology rigor is *unchanged* either
> way, because it was never the database's job."

---

## 9 · Close (9:45–10:00)

**SAY**
> "So: **safe by construction** — the graph filters before the model speaks;
> **explainable by provenance** — gauges, a phase-timed trace, and PROV-O lineage;
> **personal to the body** — driven by real anatomy via SNOMED; and a **copilot
> that's actually grounded** in the athlete in front of you. The ontology does the
> reasoning; the language model does the writing; and we kept the architecture as
> simple as the problem actually is."

> *(For production:)* "Hardening from here is the boring, right stuff — persist
> state, add authn/z and audit logging, expand the SNOMED subtrees and the
> clinical rules table, multi-injury union, and evaluation harnesses for plan
> quality and safety-filter recall. The safety boundary stays exactly where it is:
> in the graph, deterministic, and tested."

---

## Appendix A · Click-path cheat sheet

| Beat | Tab / control | Action |
|------|---------------|--------|
| Safety gate | **Insights** | Toggle "show filtering"; hover an excluded node for injury attribution |
| Generate | **Generate** | Intent pre-filled → keep **Hybrid** → *Generate session* → read gauges, trace |
| Engine contrast | **Generate** | Engine toggle → **Full LLM** → regenerate |
| Copilot (context) | **bubble** | "what kind of workout would be good for today?" |
| Copilot (corpus) | **bubble** | "how does a 5x5 program differ from HYROX conditioning?" |
| Copilot (deep-link) | **bubble** | "did Jordan mention anything about the knee this week?" |
| Client chat | member card **✉** | open inbox; contrast with copilot |
| Synthesize | **Studio** | arrange grid → *Synthesize* |
| Generalize | member switch → **Mico** | Generate; note 40 safe / 31 removed, conservative exclusion |

## Appendix B · Numbers worth quoting

- **Jordan (knee + home gym):** 17 safe / **54 removed** — injury *and* equipment
  gates firing at once; SNOMED knee traversal `49076000 → 57714003 / 182204001 /
  59440001 / 64927001`.
- **Mico (lumbar, full gym):** 40 safe / **31 removed** — same filter, conservative
  exclusion fallback for un-annotated lumbar-stressing movements.
- **Hybrid ≈ 5s** vs **Full-LLM ≈ 20s**; safety counts visible in **~1s** via the
  stream.
- **Corpus:** 12 methodology documents; embedding search + keyword fallback.
- **Graph scale:** ~200–400 nodes, read-only after build — *why NetworkX is
  right-sized*.

## Appendix C · Anticipated Q&A

- **"Is the LLM ever a safety risk?"** No — it only receives the post-filter safe
  set. An unsafe exercise can't appear because it isn't in the input. The gate is
  a tested pure function.
- **"Why not Neo4j?"** See §8 — Neo4j is an LPG *store*, not an ontology or a
  reasoner; our traversal is bounded, read-only, and precomputed; determinism and
  one-command deploy win at this scale.
- **"Multi-injury?"** The filter unions exclusion sets across injuries; the demo
  data carries one injury per member for clarity. It's a data scope choice, not a
  design limit.
- **"What if a check-in is stale?"** Handled — stale check-ins fall back to a
  conservative load tolerance; covered by the test suite.
- **"Why two engines?"** To make the latency/quality trade-off *measurable* rather
  than assumed. Default hybrid; full-LLM is a toggle.

## Appendix D · If something misbehaves on stage

- **Login stuck on "Loading…":** that's the auth bootstrap (~1s). If it persists,
  the backend is still coming up — `docker compose ps` should show backend
  *healthy*.
- **Copilot says it needs an API key:** `ANTHROPIC_API_KEY` isn't set in the
  backend env. The graph/safety/Insights/Studio beats are fully deterministic and
  demo without it; only the LLM narration and copilot need the key.
- **Generation feels slow:** confirm the **Hybrid** engine is selected; Full LLM
  is intentionally ~20s.
- **Reset everything:** `docker compose restart backend`.
