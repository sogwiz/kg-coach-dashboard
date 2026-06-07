"""
Concept catalog — the canonical nodes for the Movement / Anatomy KG.

Builds Concept nodes for all four primary families:
  - 19 muscles / muscle groups
  - 9 joints / spinal segments
  - 36 movement patterns
  - 32 equipment items

Each node carries:
  - id          : stable slug used as the graph node key
  - pref_label  : canonical display name (SKOS prefLabel)
  - alt_labels  : synonyms used by the 3-pass resolver (SKOS altLabel)
  - snomed_code : SNOMED CT code where applicable

The catalog is intentionally data-driven (not auto-generated) so that
alt_labels are hand-curated for high resolver coverage.
"""

from __future__ import annotations

from app.ontology.concepts import Concept

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _c(
    id: str,
    type: str,
    pref_label: str,
    alt_labels: list[str] | None = None,
    snomed_code: str | None = None,
) -> Concept:
    return Concept(
        id=id,
        type=type,  # type: ignore[arg-type]
        pref_label=pref_label,
        alt_labels=alt_labels or [],
        snomed_code=snomed_code,
    )


# ---------------------------------------------------------------------------
# Muscles (19)
# Sourced directly from exercises.json muscle_groups values.
# ---------------------------------------------------------------------------

MUSCLES: list[Concept] = [
    _c("biceps", "muscle", "Biceps", ["bicep", "biceps brachii", "arm flexors"], "14403001"),
    _c("calves", "muscle", "Calves", ["calf", "gastrocnemius", "soleus", "lower leg"], "9209005"),
    _c("chest", "muscle", "Chest", ["pecs", "pectorals", "pectoralis major", "pectoralis"], "78904004"),
    _c("core", "muscle", "Core", ["abs", "abdominals", "trunk", "midsection", "abdominal muscles"], "39607008"),
    _c("deltoids", "muscle", "Deltoids", ["delts", "shoulders", "deltoid", "shoulder muscles"], "5757007"),
    _c("forearms", "muscle", "Forearms", ["forearm", "wrist flexors", "wrist extensors", "grip muscles"], "14975008"),
    _c("glutes", "muscle", "Glutes", ["gluteus", "glute", "gluteal", "gluteus maximus", "butt"], "78333006"),
    _c("hamstrings", "muscle", "Hamstrings", ["hamstring", "posterior chain", "biceps femoris", "ham"], "88225001"),
    _c("hip_adductors", "muscle", "Hip Adductors", ["adductors", "groin", "inner thigh", "hip adductor"], "77298005"),
    _c("hip_flexors", "muscle", "Hip Flexors", ["hip flexor", "iliopsoas", "psoas", "iliacus"], "16543007"),
    _c("lats", "muscle", "Lats", ["lat", "latissimus", "latissimus dorsi", "back width"], "72414004"),
    _c("lower_back", "muscle", "Lower Back", ["lumbar", "lumbar muscles", "erectors", "erector spinae"], "46467000"),
    _c("middle_back", "muscle", "Middle Back", ["mid back", "rhomboids", "mid-back", "thoracic muscles"], "87424002"),
    _c("obliques", "muscle", "Obliques", ["oblique", "internal oblique", "external oblique", "side abs"], "65440009"),
    _c("quads", "muscle", "Quads", ["quad", "quadriceps", "quadriceps femoris", "front thigh"], "71341001"),
    _c("rotator_cuff", "muscle", "Rotator Cuff", ["rotator cuff", "SITS", "shoulder stabilizers", "infraspinatus"], "77736006"),
    _c("traps", "muscle", "Traps", ["trap", "trapezius", "upper traps", "neck muscles"], "81704003"),
    _c("triceps", "muscle", "Triceps", ["tricep", "triceps brachii", "back of arm"], "76261009"),
    _c("upper_back", "muscle", "Upper Back", ["upper back", "thoracic back", "scapular muscles", "rear delts"], "51283005"),
]

# ---------------------------------------------------------------------------
# Joints (9)
# Covers both true synovial joints and spinal motion segments.
# ---------------------------------------------------------------------------

JOINTS: list[Concept] = [
    _c("ankle", "joint", "Ankle", ["ankle joint", "talocrural", "subtalar", "mortise"], "70258002"),
    _c("cervical_spine", "joint", "Cervical Spine", ["neck", "cervical", "C-spine", "cervical vertebrae"], "122494008"),
    _c("elbow", "joint", "Elbow", ["elbow joint", "humeroulnar", "cubital fossa"], "16953009"),
    _c("hip", "joint", "Hip", ["hip joint", "coxofemoral", "acetabulum", "hip socket"], "24136001"),
    _c("knee", "joint", "Knee", ["knee joint", "tibiofemoral", "patellofemoral", "stifle", "knee cap"], "49076000"),
    _c("lumbar_spine", "joint", "Lumbar Spine", ["lower back", "lumbar", "L-spine", "lumbar vertebrae"], "122496005"),
    _c("shoulder", "joint", "Shoulder", ["shoulder joint", "glenohumeral", "GH joint", "AC joint"], "16982005"),
    _c("thoracic_spine", "joint", "Thoracic Spine", ["thoracic", "T-spine", "mid back", "thoracic vertebrae"], "122495006"),
    _c("wrist", "joint", "Wrist", ["wrist joint", "radiocarpal", "carpal", "wrist complex"], "74670003"),
]

# ---------------------------------------------------------------------------
# Movement Patterns (36)
# Sourced directly from exercises.json movement_patterns values.
# Slugs use underscores; pref_labels keep the original hyphenated form.
# ---------------------------------------------------------------------------

PATTERNS: list[Concept] = [
    _c("arms_accessory", "pattern", "arms - accessory", ["arm isolation", "arm accessory", "bicep curl", "tricep extension"]),
    _c("balance", "pattern", "balance", ["stability", "single-leg balance", "proprioception"]),
    _c("car", "pattern", "car", ["CARs", "controlled articular rotations", "mobility CARs", "joint circles"]),
    _c("cardio", "pattern", "cardio", ["cardiovascular", "aerobic", "conditioning", "cardio training"]),
    _c("cardio_locomotion", "pattern", "cardio - locomotion", ["locomotion", "cardio locomotion", "running", "walking", "stepping"]),
    _c("cardio_plyometric", "pattern", "cardio - plyometric", ["plyometric", "plyo", "explosive cardio", "jumping", "power cardio"]),
    _c("core_anti_extension", "pattern", "core - anti-extension", ["anti-extension", "plank", "core anti-extension", "ab bracing"]),
    _c("core_anti_lateral_flexion", "pattern", "core - anti-lateral flexion", ["anti-lateral flexion", "side plank", "lateral stability"]),
    _c("core_anti_rotation", "pattern", "core - anti-rotation", ["anti-rotation", "Pallof press", "rotational stability"]),
    _c("core_carry", "pattern", "core - carry", ["carry", "loaded carry", "farmer carry", "suitcase carry"]),
    _c("core_extension", "pattern", "core - extension", ["core extension", "back extension", "hyperextension"]),
    _c("core_flexion", "pattern", "core - flexion", ["core flexion", "crunch", "ab crunch", "sit-up", "spinal flexion"]),
    _c("core_rotation", "pattern", "core - rotation", ["rotation", "core rotation", "twist", "rotational power"]),
    _c("isometric", "pattern", "isometric", ["iso hold", "static hold", "isometric contraction"]),
    _c("legs_accessory", "pattern", "legs - accessory", ["leg isolation", "leg accessory", "leg curl", "leg extension"]),
    _c("lower_abduction", "pattern", "lower - abduction", ["abduction", "hip abduction", "lateral raise lower", "hip out"]),
    _c("lower_adduction", "pattern", "lower - adduction", ["adduction", "hip adduction", "inner thigh", "hip in"]),
    _c("lower_pull_hip_lift", "pattern", "lower pull - hip lift", ["hip lift", "hip hinge", "Romanian deadlift", "RDL", "hip dominant"]),
    _c("lower_push_calf_raise", "pattern", "lower push - calf raise", ["calf raise", "heel raise", "plantarflexion"]),
    _c("lower_push_lunge", "pattern", "lower push - lunge", ["lunge", "forward lunge", "reverse lunge", "walking lunge"]),
    _c("lower_push_split_squat", "pattern", "lower push - split squat", ["split squat", "Bulgarian split squat", "BSS", "rear foot elevated"]),
    _c("lower_push_squat", "pattern", "lower push - squat", ["squat", "squat pattern", "bilateral squat", "back squat", "front squat", "goblet squat"]),
    _c("lower_push_step_up", "pattern", "lower push - step-up", ["step-up", "step up", "box step-up"]),
    _c("massage", "pattern", "massage", ["soft tissue", "foam roll", "myofascial release", "trigger point"]),
    _c("mobility_dynamic", "pattern", "mobility - dynamic", ["dynamic mobility", "dynamic warm-up", "dynamic stretch"]),
    _c("mobility_static", "pattern", "mobility - static", ["static mobility", "static stretch", "flexibility", "static hold"]),
    _c("quadruped", "pattern", "quadruped", ["four-point", "all-fours", "table-top", "quadruped position"]),
    _c("regen", "pattern", "regen", ["regeneration", "recovery", "cooldown", "restoration"]),
    _c("shoulders_accessory", "pattern", "shoulders - accessory", ["shoulder isolation", "shoulder accessory", "lateral raise", "face pull"]),
    _c("total_body", "pattern", "total body", ["full body", "total body movement", "compound total body"]),
    _c("upper_adduction", "pattern", "upper - adduction", ["horizontal adduction", "chest fly", "cable fly", "pec fly"]),
    _c("upper_pull_horizontal", "pattern", "upper pull - horizontal", ["horizontal pull", "row", "rowing", "horizontal back"]),
    _c("upper_pull_vertical", "pattern", "upper pull - vertical", ["vertical pull", "pull-up", "chin-up", "lat pulldown", "pull down"]),
    _c("upper_push_horizontal", "pattern", "upper push - horizontal", ["horizontal push", "bench press", "push-up", "chest press"]),
    _c("upper_push_vertical", "pattern", "upper push - vertical", ["vertical push", "overhead press", "shoulder press", "OHP"]),
    _c("yoga", "pattern", "yoga", ["yoga pose", "asana", "yoga flow"]),
]

# ---------------------------------------------------------------------------
# Equipment (32)
# Sourced directly from exercises.json equipment_required values.
# ---------------------------------------------------------------------------

EQUIPMENT: list[Concept] = [
    _c("adjustable_bench_decline", "equipment", "Adjustable Bench - Decline", ["decline bench", "adjustable bench decline", "decline adjustable bench"]),
    _c("adjustable_bench_incline", "equipment", "Adjustable Bench - Incline", ["incline bench", "adjustable bench incline", "incline adjustable bench"]),
    _c("barbell", "equipment", "Barbell", ["BB", "bar", "Olympic bar", "straight bar"]),
    _c("bosu", "equipment", "BOSU", ["BOSU ball", "balance trainer", "BOSU trainer"]),
    _c("box", "equipment", "Box", ["plyo box", "step box", "jump box", "plyometric box"]),
    _c("cable_resistance_machine", "equipment", "Cable Resistance Machine", ["cable machine", "cable station", "functional trainer", "cable pulley"]),
    _c("chest_supported_row_machine", "equipment", "Chest Supported Row Machine", ["chest support row", "supported row machine", "rowing machine"]),
    _c("dumbbell", "equipment", "Dumbbell", ["DB", "dumbbells", "free weights", "hand weights"]),
    _c("ez_bar", "equipment", "EZ Bar", ["EZ curl bar", "cambered bar", "curl bar"]),
    _c("flat_bench", "equipment", "Flat Bench", ["bench", "flat bench press", "weight bench"]),
    _c("handle_attachment", "equipment", "Handle Attachment", ["cable handle", "D-handle", "single handle"]),
    _c("horizontal_leg_press_machine", "equipment", "Horizontal Leg Press Machine", ["leg press", "horizontal leg press", "leg press machine"]),
    _c("jump_rope", "equipment", "Jump Rope", ["skipping rope", "speed rope", "jump rope"]),
    _c("kettlebell", "equipment", "Kettlebell", ["KB", "bell", "kettlebells"]),
    _c("lacrosse_ball", "equipment", "Lacrosse Ball", ["lax ball", "massage ball", "trigger point ball"]),
    _c("medicine_ball", "equipment", "Medicine Ball", ["med ball", "slam ball", "wall ball"]),
    _c("miniband", "equipment", "Miniband", ["mini band", "loop band small", "hip circle", "glute band"]),
    _c("plate", "equipment", "Plate", ["weight plate", "bumper plate", "Olympic plate"]),
    _c("preacher_curl_bench", "equipment", "Preacher Curl Bench", ["preacher bench", "Scott bench"]),
    _c("pull_up_bar", "equipment", "Pull-Up Bar", ["chin-up bar", "pull-up station", "overhead bar"]),
    _c("rack", "equipment", "Rack", ["squat rack", "power rack", "barbell rack", "cage"]),
    _c("resistance_band_loop", "equipment", "Resistance Band - Loop", ["loop band", "resistance loop", "rubber band loop", "long band"]),
    _c("resistance_band_with_handles", "equipment", "Resistance Band - With Handles", ["band with handles", "tube band", "resistance tube", "handled band"]),
    _c("sandbag", "equipment", "Sandbag", ["sand bag", "heavy bag", "Husafell stone"]),
    _c("seated_lat_pulldown_machine", "equipment", "Seated Lat Pulldown Machine", ["lat pulldown machine", "lat pulldown", "pulldown machine"]),
    _c("skier", "equipment", "SkiErg", ["ski erg", "Concept2 SkiErg", "ski machine", "SkiErg machine"]),
    _c("slant_board", "equipment", "Slant Board", ["wedge board", "incline board", "heel elevation board"]),
    _c("stability_ball", "equipment", "Stability Ball", ["Swiss ball", "exercise ball", "physio ball", "yoga ball"]),
    _c("stair_climber", "equipment", "Stair Climber", ["stairmaster", "step mill", "step climber"]),
    _c("suspension_trainer", "equipment", "Suspension Trainer", ["TRX", "suspension system", "suspension straps"]),
    _c("wall", "equipment", "Wall", ["wall surface", "wall support"]),
    _c("yoga_mat", "equipment", "Yoga Mat", ["exercise mat", "gym mat", "training mat", "floor mat"]),
]

# ---------------------------------------------------------------------------
# Body regions (for SNOMED anatomy — not directly in exercises.json)
# ---------------------------------------------------------------------------

BODY_REGIONS: list[Concept] = [
    _c("knee_region", "body_region", "Knee Region", ["knee area", "knee complex", "patellofemoral region"], "72696002"),
    _c("patellofemoral_joint", "body_region", "Patellofemoral Joint", ["kneecap joint", "PF joint", "patella joint"], "57714003"),
    _c("tibiofemoral_joint", "body_region", "Tibiofemoral Joint", ["knee articulation", "TF joint"], "182204001"),
    _c("medial_meniscus", "body_region", "Medial Meniscus", ["inner meniscus", "medial cartilage"], "59440001"),
    _c("lateral_meniscus", "body_region", "Lateral Meniscus", ["outer meniscus", "lateral cartilage"], "64927001"),
]

# ---------------------------------------------------------------------------
# Injury concepts
# ---------------------------------------------------------------------------

INJURIES: list[Concept] = [
    _c("pfps", "injury", "Patellofemoral Pain Syndrome",
       ["PFPS", "runner's knee", "chondromalacia", "anterior knee pain", "patellofemoral syndrome"],
       "57773001"),
    _c("acl_tear", "injury", "ACL Tear",
       ["anterior cruciate ligament tear", "ACL rupture", "ACL injury"],
       "444798002"),
    _c("meniscus_tear", "injury", "Meniscus Tear",
       ["meniscal tear", "torn meniscus", "meniscal injury", "meniscus injury"],
       "444798002"),
    _c("patellar_tendinopathy", "injury", "Patellar Tendinopathy",
       ["jumper's knee", "patellar tendinitis", "patellar tendon pain"],
       "36117003"),
    _c("it_band_syndrome", "injury", "IT Band Syndrome",
       ["ITBS", "iliotibial band syndrome", "runner's knee lateral", "IT band friction"],
       "43208000"),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_concept_catalog() -> dict[str, Concept]:
    """
    Return the full concept catalog as a dict keyed by concept id.

    Total expected count: 19 muscles + 9 joints + 36 patterns + 32 equipment
                          + 5 body_regions + 5 injuries = 106 nodes.
    """
    all_concepts: list[Concept] = (
        MUSCLES + JOINTS + PATTERNS + EQUIPMENT + BODY_REGIONS + INJURIES
    )
    return {c.id: c for c in all_concepts}


def count_by_type(catalog: dict[str, Concept]) -> dict[str, int]:
    """Convenience helper for tests and debugging."""
    from collections import Counter

    counts: Counter[str] = Counter(c.type for c in catalog.values())
    return dict(counts)
