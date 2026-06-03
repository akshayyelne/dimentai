"""DimentAI Reporting Engine (Phase 4.3).

Deterministic, grounding-driven generation of the "Clinician-Ready Triage Report".

Design rules (Phase 4.3 decisions):
  * Output: structured JSON  +  rendered Markdown.
  * Generation: DETERMINISTIC. Every clinical statement is copied from the
    grounding fixture (mock/clinical_grounding_mock.jsonl) - no LLM, no
    paraphrasing, no fabricated thresholds. This keeps the Phase 4.4
    Hallucination Audit reducible to a provenance/coverage check.

The engine never diagnoses. It classifies measurements against the grounding
fixture's thresholds, attaches provenance to every line, and always emits the
non-diagnostic CDSS disclaimer and the clinician exclusion/next-step mandates.
"""
from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone

# Resolve the grounding fixture across the two layouts we've used
# (repo-root `mock/` on GitHub, `clinical/mock/` in the working branch).
_CANDIDATE_PATHS = [
    "mock/clinical_grounding_mock.jsonl",
    "clinical/mock/clinical_grounding_mock.jsonl",
]

# Which engine reads which measurement, and the human domain label.
# Metrics aligned to main.py biomarker scores (0-10, higher = healthier).
# ECHO has no live scorer in main.py yet -> echo_score is absent at runtime,
# so ECHO classifies as 'undefined' until a speech scorer is added.
ENGINE_METRICS = {
    "ECHO": ("echo_score", "Language"),
    "STRIDE": ("gait_score", "Perceptual-motor"),
    "VISTA": ("clock_score", "Visuospatial / Executive"),
    "FOCUS": ("oculomotor_score", "Complex attention"),
}

_TIER_LABEL = {
    "low_risk": "Low (baseline)",
    "moderate_risk": "Moderate variance",
    "high_priority_flag": "High-priority flag",
    "undefined": "No validated threshold",
}


def default_grounding_path() -> pathlib.Path:
    here = pathlib.Path(__file__).resolve().parent
    for rel in _CANDIDATE_PATHS:
        for base in (pathlib.Path.cwd(), here):
            p = base / rel
            if p.exists():
                return p
    raise FileNotFoundError(
        "clinical_grounding_mock.jsonl not found in: "
        + ", ".join(_CANDIDATE_PATHS)
    )


def load_grounding(path: str | pathlib.Path | None = None) -> dict:
    """Load the fixture and index it by id and doc_type."""
    path = pathlib.Path(path) if path else default_grounding_path()
    by_id, by_type = {}, {}
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            by_id[rec["id"]] = rec
            by_type.setdefault(rec["doc_type"], []).append(rec)
    return {"by_id": by_id, "by_type": by_type, "source_path": str(path)}


def _match(value: float, expr: str) -> bool:
    """Evaluate a threshold expression from the fixture against a value."""
    expr = expr.strip()
    if expr.startswith(">="):
        return value >= float(expr[2:])
    if expr.startswith("<="):
        return value <= float(expr[2:])
    if expr.startswith(">"):
        return value > float(expr[1:])
    if expr.startswith("<"):
        return value < float(expr[1:])
    if "-" in expr:  # inclusive range "a-b"
        lo, hi = (float(x) for x in expr.split("-", 1))
        return lo <= value <= hi
    return value == float(expr)


def classify(engine: str, value: float | None, grounding: dict) -> dict:
    """Classify a single measurement using ONLY the fixture's thresholds."""
    metric, domain = ENGINE_METRICS[engine]
    # find the mock_threshold record for this engine, if any
    thr_rec = next(
        (r for r in grounding["by_type"].get("mock_threshold", [])
         if r.get("engine") == engine),
        None,
    )
    if value is None or thr_rec is None or "thresholds" not in thr_rec \
            or "metric" not in thr_rec["thresholds"]:
        return {
            "engine": engine, "domain": domain, "metric": metric,
            "value": value, "tier": "undefined", "tier_label": _TIER_LABEL["undefined"],
            "flag": False,
            "note": "No validated threshold in grounding fixture; classification deferred.",
            "provenance": (thr_rec or {}).get("provenance", "NONE"),
        }
    t = thr_rec["thresholds"]
    tier = "moderate_risk"  # default if it matches neither extreme band
    for tier_key in ("low_risk", "moderate_risk", "high_priority_flag"):
        if tier_key in t and _match(value, t[tier_key]):
            tier = tier_key
            break
    return {
        "engine": engine, "domain": domain, "metric": metric, "value": value,
        "tier": tier, "tier_label": _TIER_LABEL[tier],
        "flag": tier == "high_priority_flag",
        "provenance": thr_rec.get("provenance", "NONE"),
        "threshold_source_id": thr_rec["id"],
    }


def _composite(measurements: dict, grounding: dict, engine_findings: dict | None = None) -> dict:
    """Composite triage level, mirroring the fixture's composite rule (=> main.py).

    Composite-escalation safety rule: if ANY individual engine raises a
    high-priority flag, the composite is forced to 'review_required' regardless
    of the weighted score — a single high-risk domain must never be averaged
    away into a 'stable' overall result.
    """
    comp_rec = grounding["by_id"].get("mock-threshold-composite-012", {})
    thresholds = comp_rec.get("thresholds", {})
    # Aligned to main.py /synthesize: weighted 0-10 scale, higher = healthier.
    clock = float(measurements.get("clock_score", 0) or 0)
    oculo = float(measurements.get("oculomotor_score", 0) or 0)
    gait = float(measurements.get("gait_score", 0) or 0)
    score = round(clock * 0.5 + oculo * 0.3 + gait * 0.2, 2)
    base_level = "stable" if score >= 7.0 else "review_required"

    flagged = [e for e, f in (engine_findings or {}).items() if f.get("flag")]
    triage_level = "review_required" if flagged else base_level
    escalated = bool(flagged) and base_level != "review_required"

    return {
        "score": score,
        "base_triage_level": base_level,
        "triage_level": triage_level,
        "escalated": escalated,
        "escalated_by": flagged,
        "escalation_rule": thresholds.get("escalation",
                                          "any engine high_priority_flag => review_required"),
        "formula": thresholds.get("formula", "clock_score*0.5 + oculomotor_score*0.3 + gait_score*0.2"),
        "provenance": comp_rec.get("provenance", "SYNTHETIC"),
        "threshold_source_id": comp_rec.get("id"),
    }


def build_report(patient_id: str, measurements: dict, grounding: dict | None = None) -> dict:
    """Assemble the structured triage report deterministically from the fixture."""
    grounding = grounding or load_grounding()
    by_id = grounding["by_id"]

    engines = {e: classify(e, measurements.get(ENGINE_METRICS[e][0]), grounding)
               for e in ENGINE_METRICS}
    composite = _composite(measurements, grounding, engines)

    cdss = by_id.get("real-cdss-024", {})
    exclusion = by_id.get("real-exclusion-020", {})
    pathway = by_id.get("real-pathway-022", {})

    # provenance roll-up: every source actually used in this report
    used_ids = (
        [v.get("threshold_source_id") for v in engines.values()]
        + [composite.get("threshold_source_id"),
           "real-cdss-024", "real-exclusion-020", "real-pathway-022"]
    )
    sources = sorted({by_id[i]["id"] + " :: " + by_id[i].get("data_status", "?")
                      for i in used_ids if i in by_id})

    # if ANY grounding record used is synthetic, the whole report is synthetic
    fixture_is_synthetic = any(
        by_id[i].get("data_status") == "SYNTHETIC_MOCK_FIXTURE"
        for i in used_ids if i in by_id
    )

    return {
        "report_type": "DimentAI Clinician-Ready Triage Report",
        "schema_version": "0.3.0-prototype",
        "patient_id": patient_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_status": "SYNTHETIC_MOCK_FIXTURE" if fixture_is_synthetic else "MIXED",
        "not_for_clinical_use": True,
        "review_gate": "clinician_required",
        "disclaimer": cdss.get("content", ""),
        "engine_findings": engines,
        "composite_triage": composite,
        "differential_exclusions_required": exclusion.get("content", ""),
        "recommended_next_steps": pathway.get("content", ""),
        "grounding_sources": sources,
        "grounding_fixture": grounding["source_path"],
    }


def render_markdown(report: dict) -> str:
    L = []
    L.append(f"# {report['report_type']}")
    L.append("")
    L.append(f"> ⚠️ **{report['data_status']} — NOT FOR CLINICAL USE.** "
             f"Review gate: **{report['review_gate']}**.")
    L.append("")
    L.append(f"- **Patient ID:** {report['patient_id']}")
    L.append(f"- **Generated (UTC):** {report['generated_at']}")
    L.append(f"- **Grounding fixture:** `{report['grounding_fixture']}`")
    L.append("")
    L.append("## Non-diagnostic statement")
    L.append(f"> {report['disclaimer']}")
    L.append("")
    L.append("## Engine findings")
    L.append("| Engine | Domain | Metric | Value | Tier | Flag | Provenance |")
    L.append("|---|---|---|---|---|---|---|")
    for e in report["engine_findings"].values():
        L.append(f"| {e['engine']} | {e['domain']} | `{e['metric']}` | "
                 f"{e['value']} | {e['tier_label']} | "
                 f"{'🚩' if e['flag'] else '—'} | {e['provenance']} |")
    L.append("")
    c = report["composite_triage"]
    L.append("## Composite triage")
    L.append(f"- **Score:** {c['score']}  (`{c['formula']}`)")
    L.append(f"- **Triage level:** **{c['triage_level']}**  "
             f"_(provenance: {c['provenance']})_")
    if c.get("escalated"):
        L.append(f"- **⚠️ Escalated** to `review_required` by high-priority flag(s): "
                 f"**{', '.join(c['escalated_by'])}** (weighted score alone was `{c['base_triage_level']}`).")
    L.append("")
    L.append("## Clinician must exclude first")
    L.append(f"{report['differential_exclusions_required']}")
    L.append("")
    L.append("## Recommended next steps")
    L.append(f"{report['recommended_next_steps']}")
    L.append("")
    L.append("## Grounding provenance (sources used)")
    for s in report["grounding_sources"]:
        L.append(f"- `{s}`")
    return "\n".join(L) + "\n"


# --- Optional FastAPI router (wire into your app: app.include_router(router)) ---
try:
    from fastapi import APIRouter, HTTPException
    from fastapi.responses import PlainTextResponse

    router = APIRouter(prefix="/report", tags=["reporting"])

    @router.get("/{user_id}")
    async def get_report(user_id: str, format: str = "json"):
        """Build a triage report for a patient.

        Pulls measurements from Firestore `assessments/<user_id>.results`
        (same source as main.py /synthesize). Use ?format=markdown for the
        rendered clinician view.
        """
        try:
            from google.cloud import firestore
            db = firestore.Client(project="dimentai1", database="dimentdata")
            doc = db.collection("assessments").document(user_id).get()
            if not doc.exists:
                raise HTTPException(404, f"Document {user_id} not found in dimentdata")
            measurements = doc.to_dict().get("results", {})
        except HTTPException:
            raise
        except Exception as exc:  # firestore unavailable / offline
            raise HTTPException(503, f"Data source unavailable: {exc}")

        report = build_report(user_id, measurements)
        if format == "markdown":
            return PlainTextResponse(render_markdown(report))
        return report
except ImportError:  # FastAPI not installed in this context
    router = None
