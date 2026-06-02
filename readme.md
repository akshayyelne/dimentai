# DimentAI — Clinical Grounding (Phase 4.2)

> ## ⚠️ SYNTHETIC TEST FIXTURES — NOT CLINICAL GUIDANCE
> Everything under `clinical/mock/` is **fabricated mock data created solely to test the
> RAG ingestion → indexing → retrieval → grounding pipeline** (Phase 4.2) and to feed the
> Phase 4.4 Hallucination Audit. **No number, threshold, or risk tier in the mock files is a
> real clinical standard.** Do not deploy, publish, or use any mock value for patient triage.

## Layout

| Path | Status | Purpose |
|---|---|---|
| `mock/clinical_grounding_mock.jsonl` | **SYNTHETIC** | Importable docs for the *secondary* Vertex AI Search RAG data store. Every record carries `data_status: "SYNTHETIC_MOCK_FIXTURE"` and `not_for_clinical_use: true`. |
| `mock/clinical_grounding_mock.md` | **SYNTHETIC** | Human-readable mirror of the fixture. |
| `mock/ingest_mock_grounding.py` | test utility | Imports the JSONL into a **mock** data store (`--data-store`), with `--dry-run`. |

## Real vs. mock content

- **Real, sourced, safe to keep:** the differential-diagnosis / exclusion logic and the
  6-step assessment pathway are drawn from the **RACGP Silver Book 5th edn, Part A: Dementia**
  and are tagged `provenance: "RACGP_SILVERBOOK_PARTA"`.
- **Mock, must be replaced before any real use:** all per-engine numeric thresholds
  (Echo/Stride/Vista/Focus) and the Low/Moderate/High tiers are invented placeholders tagged
  `provenance: "SYNTHETIC"`. Replace these with values derived from cited instruments
  (GPCOG, SMMSE, RUDAS) **and** your own internal validation study before production.

## Promotion checklist (mock → real)
- [ ] Replace every `provenance: "SYNTHETIC"` record with cited / validated values.
- [ ] Remove `data_status: "SYNTHETIC_MOCK_FIXTURE"` only after sign-off.
- [ ] Confirm TGA non-diagnostic wording with regulatory advisor (Task 4.1).
- [ ] Re-run the Phase 4.4 Hallucination Audit against the promoted store.
