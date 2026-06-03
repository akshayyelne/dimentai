# DimentAI — Synthetic Clinical Grounding (`mock/`)

> ## ⚠️ SYNTHETIC TEST FIXTURES — NOT CLINICAL GUIDANCE
> Everything in this folder is **fabricated mock data created solely to test the
> RAG ingestion → indexing → retrieval → grounding → reporting pipeline** and to
> drive the hallucination audit. **No number, threshold, or risk tier here is a
> real clinical standard.** Do not deploy, publish, or use any mock value for
> patient triage.

## Why synthetic data?

DimentAI grounds a clinical *decision-support* agent, which carries a TGA
non-diagnostic posture. We deliberately **do not** let an LLM invent
"authoritative" clinical thresholds, because that would create un-traceable
grounding with no provenance. So during prototyping we test the *machinery*
(ingest, retrieve, classify, report, audit) against a clearly-watermarked
synthetic fixture, and defer real clinical values until they can be sourced from
licensed instruments and validated.

## Files

| File | Purpose |
|---|---|
| `clinical_grounding_mock.jsonl` | The grounding corpus. **15 records**, each tagged `data_status` + `not_for_clinical_use: true`. Importable into a **secondary/mock** Vertex AI Search data store. |
| `ingest_mock_grounding.py` | Guarded importer — refuses any record not marked `not_for_clinical_use`; supports `--dry-run`. |
| `clinical_grounding_mock.md` | Human-readable mirror of the fixture. |

## Metric vocabulary (aligned to `main.py`)

Engine thresholds use the same biomarker scores `main.py` produces — **0–10,
higher = healthier**:

| Engine | Metric | Source endpoint |
|---|---|---|
| STRIDE | `gait_score` | `/process-gait` |
| VISTA | `clock_score` | `/process-clock` |
| FOCUS | `oculomotor_score` | `/process-oculomotor` |
| ECHO | `echo_score` | *(no scorer yet → `undefined` at runtime)* |

Per-engine tiers: Low **≥8** · Moderate **5–7.99** · High flag **<5**.

## Record provenance tags

- **`SYNTHETIC`** — fabricated for testing (engine→domain maps and all numeric
  risk tiers, the composite cutoff, and the composite-escalation rule).
  **Must be replaced before any real use.**
- **`SOURCED_REFERENCE`** — drawn from the **RACGP Silver Book 5th edn, Part A: Dementia**
  (exclusion rules, pathology panel, six-step pathway, endorsed tool list). Real
  provenance, safe to keep.
- **`DRAFT_PENDING_REGULATORY_REVIEW`** — the non-diagnostic CDSS wording, pending
  sign-off (Task 4.1).

## Composite-escalation rule (synthetic)

The composite record (`mock-threshold-composite-012`) mirrors `main.py /synthesize`
(`clock_score*0.5 + oculomotor_score*0.3 + gait_score*0.2`, stable ≥ 7) and adds a
safety rule the reporting engine enforces: **if any single engine raises a
high-priority flag (score < 5), the overall composite is forced to
`review_required` regardless of the weighted score.** The numeric cutoffs are
synthetic; the *rule shape* is the part worth keeping.

## Promotion checklist (mock → real)

- [ ] Replace every `provenance: "SYNTHETIC"` record with cited / validated values
      (GPCOG, SMMSE, RUDAS, a named Clock Drawing Test scoring system).
- [x] Metric names reconciled with the live `main.py` biomarkers
      (`clock_score` / `oculomotor_score` / `gait_score`).
- [ ] Add a speech scorer so `echo_score` (ECHO) is produced instead of `undefined`.
- [ ] Remove `data_status: "SYNTHETIC_MOCK_FIXTURE"` only after clinical sign-off.
- [ ] Confirm TGA non-diagnostic wording with a regulatory advisor (Task 4.1).
- [ ] Re-run the hallucination audit (`python hallucination_audit.py`) against the
      promoted store.
