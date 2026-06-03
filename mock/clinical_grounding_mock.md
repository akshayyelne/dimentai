# DimentAI — Mock Clinical Grounding (human-readable mirror)

> ## ⚠️ SYNTHETIC — FABRICATED FOR PIPELINE TESTING ONLY
> Mirror of `clinical_grounding_mock.jsonl`. **No threshold below is a clinical standard.**
> `SYNTHETIC` = invented for testing · `SOURCED_REFERENCE` = from RACGP Silver Book Part A.

## 1. Engine → Domain map (`SYNTHETIC` design hypothesis)
Metrics aligned to `main.py` biomarker scores (0–10, **higher = healthier**).

| Engine | Domain (DSM-5) | Live metric (`main.py`) | Endpoint |
|---|---|---|---|
| **ECHO** | Language | `echo_score` *(not yet produced — `undefined` at runtime)* | — |
| **STRIDE** | Perceptual-motor | `gait_score` | `/process-gait` |
| **VISTA** | Visuospatial / Executive | `clock_score` | `/process-clock` |
| **FOCUS** | Complex attention | `oculomotor_score` | `/process-oculomotor` |

## 2. Mock risk tiers (`SYNTHETIC` — 0–10 scale, no clinical meaning)
- Per engine (`echo_score`/`gait_score`/`clock_score`/`oculomotor_score`):
  Low/baseline **≥ 8** · Moderate **5–7.99** · High-priority flag **< 5**
- **Composite** (mirrors `main.py /synthesize`): `clock_score*0.5 + oculomotor_score*0.3 + gait_score*0.2` → **stable ≥ 7**, else **review_required**
- **Composite-escalation:** any engine high-priority flag (**< 5**) forces **review_required** regardless of the weighted score.

## 3. Exclusion & differential (`SOURCED_REFERENCE` — Silver Book Part A)
- Exclude first: **delirium**, **depression (pseudodementia)**, **medication effects** (psychotropics, anticholinergics, incontinence meds, antihistamines), physical/structural disease.
- Panel: **FBC, electrolytes, calcium, glucose, renal & liver function, TFTs, B12 & folate** (± syphilis, HIV); **imaging** to exclude tumour / chronic subdural haematoma.
- No attribution without **confirmed functional interference**.

## 4. Six-step pathway (`SOURCED_REFERENCE`)
1. Cognitive test → 2. Pathology → 3. Imaging → 4. Depression assessment → 5. Medication review → 6. Functional assessment → specialist if symptoms persist.

## 5. CDSS terminology (`DRAFT_PENDING_REGULATORY_REVIEW`)
> "DimentAI **flags** patterns that **may warrant clinical assessment**; it **does not diagnose**. Outputs are **decision support** for a clinician and do not replace DSM-5 evaluation, validated testing, or clinical judgement."
