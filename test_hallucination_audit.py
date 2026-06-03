"""Phase 4.4 SIT — tests for the Hallucination Audit.

Includes RED-TEAM cases: planted hallucinations MUST be caught, otherwise the
audit gives false assurance. An audit that only ever passes is worthless.

Metrics aligned to main.py (clock/oculomotor/gait scores, 0-10, higher = healthier).
"""
import copy

import hallucination_audit as audit
import reporting_engine as engine

G = engine.load_grounding()


def _clean_report(measurements=None):
    measurements = measurements or {"clock_score": 3, "oculomotor_score": 3, "gait_score": 3}
    return engine.build_report("pt_audit", measurements, G)


# ---- Positive: legitimate deterministic reports pass ----

def test_clean_report_passes():
    assert audit.audit_report(_clean_report(), G).passed


def test_all_sample_reports_pass():
    for rep in audit._sample_reports(G).values():
        assert audit.audit_report(rep, G).passed


# ---- Red-team: tampered reports MUST fail ----

def test_fabricated_narrative_is_caught():
    rep = _clean_report()
    rep["recommended_next_steps"] = "Start donepezil immediately and skip pathology."
    res = audit.audit_report(rep, G)
    assert not res.passed
    assert any(f["check"] == "verbatim_narrative" for f in res.fails)


def test_tampered_risk_tier_is_caught():
    rep = _clean_report()
    # claim VISTA is low risk when clock_score (3) is a high-priority flag
    rep["engine_findings"]["VISTA"]["tier"] = "low_risk"
    rep["engine_findings"]["VISTA"]["flag"] = False
    res = audit.audit_report(rep, G)
    assert not res.passed
    assert any(f["check"] == "threshold_integrity" for f in res.fails)


def test_tampered_composite_is_caught():
    rep = _clean_report()
    rep["composite_triage"]["triage_level"] = "stable"
    rep["composite_triage"]["score"] = 10.0
    assert any(f["check"] == "composite_integrity"
               for f in audit.audit_report(rep, G).fails)


def test_unescalated_high_flag_is_caught():
    # gait 4 (STRIDE high) with clock/oculo 9 -> base stable but MUST be review_required.
    # Tampering it back to 'stable' (defeating the escalation rule) must be caught.
    rep = _clean_report({"clock_score": 9, "oculomotor_score": 9, "gait_score": 4})
    assert rep["composite_triage"]["triage_level"] == "review_required"  # sanity: escalation happened
    rep["composite_triage"]["triage_level"] = "stable"
    rep["composite_triage"]["escalated"] = False
    res = audit.audit_report(rep, G)
    assert not res.passed
    assert any(f["check"] == "composite_integrity" for f in res.fails)


def test_dropped_disclaimer_is_caught():
    rep = _clean_report()
    rep["disclaimer"] = "All clear, no concerns."
    res = audit.audit_report(rep, G)
    assert not res.passed
    assert any(f["check"] in ("verbatim_narrative", "disclaimer") for f in res.fails)


def test_unlabelled_synthetic_is_caught():
    rep = _clean_report()
    rep["data_status"] = "PRODUCTION"  # lies about synthetic provenance
    assert any(f["check"] == "data_status" for f in audit.audit_report(rep, G).fails)


# ---- Free-text auditor (LLM-path safety net) ----

def test_grounded_free_text_passes():
    txt = ("DimentAI flags patterns that may warrant clinical assessment; "
           "it does not diagnose. A dementia diagnosis cannot be made without "
           "confirmed functional interference.")
    assert audit.audit_free_text(txt, G).passed


def test_diagnostic_language_is_caught():
    txt = "The patient is diagnosed with Alzheimer's disease based on the score."
    res = audit.audit_free_text(txt, G)
    assert not res.passed
    assert any(f["check"] == "diagnostic_language" for f in res.fails)


def test_ungrounded_acronym_is_caught():
    txt = "The MoCA and CDR results indicate severe impairment."  # MoCA/CDR not in fixture
    res = audit.audit_free_text(txt, G)
    assert not res.passed
    assert any(f["check"] == "ungrounded_term" for f in res.fails)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} audit tests passed.")
