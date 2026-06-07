# Knowledge Graph Schema Reference

This document describes both knowledge graphs in the KG Coach Dashboard system,
every node type and edge type, the ontology grounding (SKOS, SNOMED CT, PROV-O),
and the taxonomy mapping (19 muscles / 9 joints / 36 patterns / 32+ equipment).

---

## Overview: Two Graphs, One Shared Vocabulary

The system uses two NetworkX `MultiDiGraph` instances that **share concept nodes**:

| Graph | Purpose | Primary use |
|---|---|---|
| **KG1 — Movement/Clinical KG** | Canonical exercise ontology | Safety filter, provenance, Graph Explorer |
| **KG2 — Member Context KG** | Per-member context for one member | Copilot agent retrieval |

The shared concept nodes are **joint** and **equipment** nodes — KG2 nodes
like `has_equipment` point to the same equipment concept ids used in KG1's
`requires` edges. This sharing means "Jordan has kettlebell" and "Exercise X
requires kettlebell" resolve to the same graph node, enabling cross-graph queries.

---

## KG1 — Movement/Clinical Knowledge Graph

Built in: `backend/app/graph/movement_kg.py`  
Type: `networkx.MultiDiGraph`

### Node Types

| Node type | Key (id) | Fields | Count | Example |
|---|---|---|---|---|
| `exercise` | Exercise catalog id (UUID) | `name`, `priority_tier` | ~80 (50 base + 30 hybrid) | `"00036a08..."` → Kettlebell Goblet Squat |
| `muscle` | Slug (e.g. `"quads"`) | `pref_label`, `alt_labels`, `snomed_code` | 19 | `"hamstrings"` |
| `joint` | Slug (e.g. `"knee"`) | `pref_label`, `alt_labels`, `snomed_code` | 9 | `"lumbar_spine"` |
| `pattern` | Slug (e.g. `"lower_push_squat"`) | `pref_label`, `alt_labels` | 36 | `"core_anti_extension"` |
| `equipment` | Slug (e.g. `"barbell"`) | `pref_label`, `alt_labels` | 37 | `"kettlebell"` |
| `body_region` | Slug (e.g. `"patellofemoral_joint"`) | `pref_label`, `snomed_code` | 8 | `"lumbar_disc"` |
| `injury` | Slug (e.g. `"pfps"`) | `pref_label`, `alt_labels`, `snomed_code` | 7 | `"low_back_pain"` |
| `injury_concept` | `"injury_concept_{joint_slug}"` | `pref_label`, `joint_slug` | 5 | `"injury_concept_knee"` |

### Edge Types in KG1

| Edge type | Direction | Meaning | Fields on edge |
|---|---|---|---|
| `stresses` | exercise → joint | This exercise loads/stresses the given joint under mechanical demand | `movement_types: list[str]` — which of `{flexion, extension, rotation, load, impact}` the exercise performs at that joint |
| `targets` | exercise → muscle | This exercise is a primary or secondary stimulus for this muscle group | (none beyond `relation`) |
| `requires` | exercise → equipment | This exercise cannot be performed without this equipment | (none beyond `relation`) |
| `uses` | exercise → pattern | This exercise belongs to this movement pattern category | (none beyond `relation`) |
| `part-of` | body_region/joint → parent_region | Anatomical containment from SNOMED CT — `patellofemoral_joint --part-of--> knee_region --part-of--> lower_limb` | `relation: "part-of"` |
| `contraindicated-for` | injury_concept → exercise | Static textbook contraindication: exercises that should be avoided for an injury, based on the movement types that are clinically excluded | `movement_types: list[str]` — the movement types that triggered the edge |

#### Plain-language meanings

- **stresses** — "this exercise puts mechanical stress on this joint." Combined with `movement_types`, the safety filter can exclude exercises that perform `flexion` at the `knee` when the member has pain on flexion.
- **targets** — "this exercise was designed to stimulate this muscle group." Used by the Copilot to explain selection rationale and by the Graph Explorer to show which muscles an exercise works.
- **requires** — "this exercise requires access to this piece of equipment." The safety filter removes exercises whose required equipment is not in the member's available set.
- **uses** — "this exercise belongs to this movement category." Used for concept resolution: when a coach says "I want squats," the resolver maps to `lower_push_squat` and the system returns exercises that use that pattern.
- **part-of** — "this anatomical structure is a component of this parent region." This is the foundational safety traversal edge: given a knee injury, the filter traverses the `part-of` hierarchy to collect all descendant nodes (patellofemoral joint, tibiofemoral joint, medial meniscus, etc.) then removes all exercises that `stresses` any of those nodes.
- **contraindicated-for** — static textbook edges materialised from a built-in clinical rules table. These are the "always avoid" baselines; the runtime authority is the dynamic `conditional_safety_filter` which uses the member's actual injury state (pain triggers, healing phase, load tolerance).

### Taxonomy Mapping: 19/9/36/32

The canonical concept catalog (`backend/app/ontology/catalog.py`) is hand-rolled
from the exercise data files, grounded in ontology vocabularies.

| Family | Count | How the slugs were chosen |
|---|---|---|
| **Muscles** | 19 | Derived from the `muscle_groups` values in `exercises.json`; each slug covers a functional group (e.g. `quads` covers quadriceps femoris, front thigh) |
| **Joints** | 9 | True synovial joints + spinal motion segments that appear as `joints_loaded` in the exercise data |
| **Movement Patterns** | 36 | Derived directly from the `movement_patterns` values in `exercises.json`; slugs use underscores, labels keep the original hyphenated form |
| **Equipment** | 32 base + 5 hybrid | Derived from `equipment_required`; Phase 11 added sled, rower, assault bike, rope, tire for hybrid/HYROX exercises |

---

## KG2 — Member Context Knowledge Graph

Built in: `backend/app/graph/member_kg.py`  
Type: `networkx.MultiDiGraph` (thin — primary value is the query API)

### Node Types in KG2

| Node type | Key | Meaning |
|---|---|---|
| `member` | `"member:{member_id}"` | Root node for the member |
| `injury` | `"injury:{injury_id}"` | An active injury with healing state |
| `equipment_item` | `"equip:{slug}"` | A piece of equipment the member has access to |
| `adherence_week` | `"adherence:{week_of}"` | One week's adherence data point |
| `coach_brief` | `"brief:{member_id}"` | The morning brief tasks and churn risk |
| `biomarker_snapshot` | `"biomarkers:{member_id}"` | RHR, HRV, sleep, weight trend |
| `goal` | `"goal:{goal_id}"` | A member goal with priority and target date |
| `preference` | `"preference:{member_id}"` | Session preferences, dislikes |
| `lab_result` | `"labs:{member_id}"` | Blood panel + DEXA scan results |
| `workout_session` | `"session:{session_id}"` | A completed workout session |
| `chat_message` | `"chat:{message_id}"` | A past chat message (may include image attachment) |

### Edge Types in KG2

| Edge type | Direction | Meaning |
|---|---|---|
| `has_injury` | member → injury | This member has this active injury |
| `has_equipment` | member → equipment_item | This member has access to this equipment |
| `has_adherence` | member → adherence_week | This week's adherence point belongs to this member |
| `has_brief` | member → coach_brief | The morning brief for this member |
| `has_biomarkers` | member → biomarker_snapshot | The current biomarker snapshot |
| `has_goal` | member → goal | This goal belongs to this member |
| `has_preference` | member → preference | This member's session preferences |
| `has_labs` | member → lab_result | This member's lab results (blood panel + DEXA) |
| `has_workout_session` | member → workout_session | A completed workout session |
| `has_chat_message` | member → chat_message | A historical chat message |
| `affects_joint` | injury → equipment_item / joint | (shared concept node) — the injured joint links to its catalog concept |

### How the Two Graphs Share Concept Nodes

- **Equipment**: `equip:{slug}` nodes in KG2 use the same slug as `equipment` nodes in KG1 (e.g. `"kettlebell"`). When a member has a kettlebell, the KG2 equipment node references the same concept. The safety filter receives `member.equipment_available` as a set of slugs that match KG1's `requires` edges.
- **Joints**: `injury.joint` in KG2 is a slug (e.g. `"knee"`, `"lumbar_spine"`) that is also the KG1 joint concept id. The conditional safety filter's `descendants_by_part_of(injury.joint)` call uses KG1 to expand the injury joint to all its SNOMED descendants, then finds all exercises that `stresses` any of those nodes.

This shared vocabulary is the architectural link between member context and the movement graph — the system never needs to join on free text; it joins on canonical concept ids.

---

## Ontology Grounding

### SKOS (Simple Knowledge Organization System)

**What we use:** `prefLabel` and `altLabel` on every concept node.

- `pref_label`: the canonical display name (e.g. `"Quads"`, `"Knee"`)
- `alt_labels`: a curated list of synonyms used by the 3-pass resolver

**Why:** The 3-pass resolver (exact → fuzzy → embedding) uses `alt_labels` as
the match surface. When a coach writes "bad lower back" or "patellofemoral
pain," the resolver finds the right canonical concept. SKOS provides the
right vocabulary for this: `prefLabel` is what we display; `altLabel` is
what we match.

**What we left out:** SKOS's broader/narrower/related/seeAlso relationships
and scheme notation. These are valuable for a full thesaurus but unnecessary
here — the concept hierarchy comes from SNOMED `part-of` edges, not SKOS relations.

### SNOMED CT (via NCI EVS REST API)

**What we use:** A baked snapshot of two anatomy subtrees:

1. **Knee subtree** (rooted at `72696002` — Knee region):
   - Knee region → Knee joint (`49076000`) → Patellofemoral joint (`57714003`) → Tibiofemoral joint (`182204001`) → Medial meniscus → Lateral meniscus
   - Injury codes: PFPS (`57773001`), ACL tear, patellar tendinopathy, IT band syndrome

2. **Lumbar spine subtree** (rooted at `122496007` — Lumbar spine region):
   - Lumbar spine region → Lumbar intervertebral joints (`297179000`) → Lumbar disc (`244944005`)
   - Injury code: Low back pain (`279039007`), lumbar spondylosis

**How stored:** JSON snapshot at `backend/app/ontology/snomed_anatomy.json`,
committed to the repo. Loaded at startup into a dict of `SnomedConcept` objects
keyed by SNOMED code. The `part-of` edges from this snapshot are materialised
into the KG1 `MultiDiGraph` as `part-of` edges, enabling `descendants_by_part_of()`
traversal.

**Why this subset:** The `part-of` traversal is the safety system's anatomical
reasoning. It answers "which joints are part of the knee?" — so that a knee
injury automatically excludes exercises stressing *any* part of the knee complex
(patellofemoral, tibiofemoral, meniscus), not just the knee joint label itself.
SNOMED CT has the best available `part-of` anatomy hierarchy and machine-readable
clinical codes.

**What we left out:** The rest of SNOMED CT. The full SNOMED is 360,000+ concepts;
we need only the anatomy subtrees relevant to our two members' injuries. Pulling more
would add ontology complexity with no safety benefit.

### PROV-O (W3C Provenance Ontology)

**What we use:** `prov:Activity`, `prov:Entity`, `prov:Agent`, `prov:wasAssociatedWith`,
`prov:wasDerivedFrom`, `prov:used`, `prov:startedAtTime`, `prov:endedAtTime`.

Each generated plan carries a `ProvODocument` (built by `backend/app/generator/provenance.py`)
with:
- `prov:Activity` — the generation run (timing, prompt, member, variant)
- `prov:Agent` — `"kg-coach-dashboard:generator"` (the system component)
- `prov:Entity` per planned exercise — `prov:wasDerivedFrom` the safe candidate pool; `prov:used` the structuring call
- `filtered_out` entries — exercise, reason, `graph_path` (the traversal path), `injury_constraint` (the pain_on movement type or phase rule)

**Why:** Assessment requirement R1 requires that every generated plan carries a
provenance trace: *why each exercise was chosen, which graph path justified it,
and what was filtered out for safety*. PROV-O provides a standard vocabulary for
this that can be trivially extended to full JSON-LD if needed.

**What we left out:** Full JSON-LD serialisation with `@context`. The documents
are PROV-O-shaped JSON (not formal JSON-LD) because the frontend renders them
directly and doesn't need RDF inferencing. The term names (prefixed with `prov:`)
preserve the ontology lineage.

### OPE (Open Physical Education Ontology)

**What we borrow:** The *edge vocabulary* — the idea that exercises `targets` muscles,
`stresses` joints, and `requires` equipment. These three edge types map directly
to OPE's relationship notions.

**What we left out:** OPE's full OWL hierarchy. Investigation showed OPE covers
0/36 of our movement pattern categories, has 0 named equipment items matching our
catalog, and its documentation is sparse (undocumented alpha). Hand-rolling the
catalog against our actual data gives better coverage with less inference complexity.

### COPPER (COgnitive-Physical PERformance Ontology)

**What we borrow:** The framing that member context includes adherence, goals, and
behavioral signals (churn risk, morning brief). COPPER's personalization/behaviour-change
perspective informed the KG2 design.

**What we left out:** COPPER's class tree, which focuses on cognitive-physical performance
and has no anatomy component. Our system's safety reasoning is anatomy-first (SNOMED),
so COPPER is an influence on design intent rather than a structural dependency.

---

## How the Graphs Are Built

1. **KG1 build sequence** (at startup):
   - Load `exercises.json` + `exercises.hybrid.json` as Pydantic `Exercise` models
   - Load `exercise_movements.json` joint-movement annotations (flexion/extension/rotation/load/impact per joint per exercise)
   - Load `snomed_anatomy.json` SNOMED snapshot → `SnomedConcept` dict
   - Instantiate `MovementKG(exercises, concepts, snomed)` which:
     a. Adds all 116 concept catalog nodes
     b. Materialises SNOMED `part-of` edges between body_region nodes
     c. Adds exercise nodes + `stresses`/`targets`/`requires`/`uses` edges
     d. Materialises static `contraindicated-for` edges from the clinical rules table

2. **KG2 build sequence** (per Copilot invocation, per member):
   - Load `data/members/{member_id}.json` → `MemberContext`
   - Instantiate `MemberKG(member, shared_concepts)` which adds member-specific nodes linked to shared concept ids

3. **Concept resolution** (at generate/refine time):
   - Free-text prompt terms → 3-pass resolver (exact → fuzzy `rapidfuzz` → embedding `all-MiniLM-L6-v2`)
   - Each resolved term gets a `Resolution(status, concept, confidence, pass_used)`
   - The resolved concept ids are used to filter/rank candidates from KG1

4. **Safety filter** (at generate/refine time, runs ONCE per call):
   - `conditional_safety_filter(candidates, injury, available_equipment, excluded_ids, dislikes, kg)`
   - Returns `ConditionalFilterTrace(safe, removed, substitutions, injury_state_used, phase_restrictions_applied, load_tolerance_pct)`
   - The LLM only sees `trace.safe` — never unsafe exercises

---

## Edge Summary Table

| Edge | Source type | Target type | Semantic meaning |
|---|---|---|---|
| `stresses` | exercise | joint / body_region | Exercise loads this joint with these movement types |
| `targets` | exercise | muscle | Exercise stimulates this muscle group |
| `requires` | exercise | equipment | Exercise needs this equipment to be performed |
| `uses` | exercise | pattern | Exercise belongs to this movement pattern category |
| `part-of` | body_region / joint | body_region / joint | Anatomical containment (SNOMED hierarchy) |
| `contraindicated-for` | injury_concept | exercise | Static textbook: this injury type contraindicates this exercise |
| `has_injury` | member | injury | Member has this active injury |
| `has_equipment` | member | equipment_item | Member has access to this equipment |
| `has_adherence` | member | adherence_week | Member adherence data point for this week |
| `has_brief` | member | coach_brief | Morning brief for this member |
| `has_biomarkers` | member | biomarker_snapshot | Current biomarker readings |
| `has_goal` | member | goal | Member's training / health goal |
| `has_preference` | member | preference | Member's session preferences (dislikes, session length) |
| `has_labs` | member | lab_result | Blood panel + DEXA scan results |
| `has_workout_session` | member | workout_session | Completed workout in history |
| `has_chat_message` | member | chat_message | Historical chat message with optional image |
| `affects_joint` | injury | joint (shared concept) | The injury involves this joint (shared concept node) |
