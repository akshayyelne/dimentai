# DimentAI — Mock Clinical Grounding (human-readable mirror)

> ## ⚠️ SYNTHETIC — FABRICATED FOR PIPELINE TESTING ONLY
> Mirror of `clinical_grounding_mock.jsonl`. **No threshold below is a clinical standard.**
> `SYNTHETIC` = invented for testing · `SOURCED_REFERENCE` = from RACGP Silver Book Part A.

## 1. Engine → Domain map (`SYNTHETIC` design hypothesis)
| Engine | Domain (DSM-5) | Mock markers |
|---|---|---|
| **ECHO** | Language | semantic_density, anomia_rate, syntactic_complexity |
| **STRIDE** | Perceptual-motor | gait_speed_variability, step_asymmetry, dual_task_cost |
| **VISTA** | Visuospatial / Executive | cdt_error_count, dyspraxia_index |
| **FOCUS** | Complex attention | fixation_stability, scanning_efficiency, processing_speed_ms |

## 2. Mock risk tiers (`SYNTHETIC` — aligned to `main.py`, no clinical meaning)
- **ECHO** `semantic_density`: Low **≥0.90** · Moderate **0.70–0.89** · High-flag **<0.70**
- **STRIDE** `dual_task_cost` (arbitrary test unit, *not* a real DTC %): Low **≤20** · Moderate **21–30** · High-flag **>30**
- **Composite** (mirrors `main.py`): `dual_task_cost*0.4 + semantic_density*40` → **stable <50**, else **review_required**

## 3. Exclusion & differential (`SOURCED_REFERENCE` — Silver Book Part A)
- Exclude first: **delirium**, **depression (pseudodementia)**, **medication effects** (psychotropics, anticholinergics, incontinence meds, antihistamines), physical/structural disease.
- Panel: **FBC, electrolytes, calcium, glucose, renal & liver function, TFTs, B12 & folate** (± syphilis, HIV); **imaging** to exclude tumour / chronic subdural haematoma.
- No attribution without **confirmed functional interference**.

## 4. Six-step pathway (`SOURCED_REFERENCE`)
1. Cognitive test → 2. Pathology → 3. Imaging → 4. Depression assessment → 5. Medication review → 6. Functional assessment → specialist if symptoms persist.

## 5. CDSS terminology (`DRAFT_PENDING_REGULATORY_REVIEW`)
> "DimentAI **flags** patterns that **may warrant clinical assessment**; it **does not diagnose**. Outputs are **decision support** for a clinician and do not replace DSM-5 evaluation, validated testing, or clinical judgement."
