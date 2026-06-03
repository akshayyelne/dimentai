"""DimentAI — SIT Hallucination Audit Scenarios (Phase 4.4).

End-to-end "patient journey" scenarios that exercise the full
build_report -> audit pipeline, plus adversarial cases the audit MUST catch.
This is a system-integration runner (readable PASS/FAIL table + non-zero exit
on any unexpected behaviour), complementary to the unit tests.

Note: depends on the composite-escalation fields (base_triage_level,
escalated, escalated_by) introduced in reporting_engine.py.

Run:  python test_hallucination_audit_scenarios.py
"""
from __future__ import annotations

import sys

import hallucination_audit as audit
import reporting_engine as engine

G = engine.load_grounding()


def _report(measurements):
    return engine.build_report("sit", measurements, G)


# Each scenario returns (ok: bool, detail: str). ok == "behaved as expected".
def s1_healthy_baseline():
    rep = _report({"semantic_density": 0.96, "dual_task_cost": 8})
    res = audit.audit_report(rep, G)
    ok = res.passed and rep["composite_triage"]["triage_level"] == "stable"
    return ok, f"triage={rep['composite_triage']['triage_level']} audit={'PASS' if res.passed else 'FAIL'}"


def s2_single_domain_escalation():
    # STRIDE high (dtc 31), ECHO low (0.90) -> weighted 48.4 (<50) but MUST escalate.
    rep = _report({"semantic_density": 0.90, "dual_task_cost": 31})
    res = audit.audit_report(rep, G)
    c = rep["composite_triage"]
    ok = (res.passed and c["base_triage_level"] == "stable"
          and c["triage_level"] == "review_required" and c["escalated_by"] == ["STRIDE"])
    return ok, f"base={c['base_triage_level']} -> {c['triage_level']} by {c['escalated_by']} audit={'PASS' if res.passed else 'FAIL'}"


def s3_multi_domain_high():
    rep = _report({"semantic_density": 0.62, "dual_task_cost": 33})
    res = audit.audit_report(rep, G)
    flags = [e for e, f in rep["engine_findings"].items() if f["flag"]]
    ok = res.passed and rep["composite_triage"]["triage_level"] == "review_required" and set(flags) == {"ECHO", "STRIDE"}
    return ok, f"flags={flags} triage={rep['composite_triage']['triage_level']} audit={'PASS' if res.passed else 'FAIL'}"


def s4_score_only_review():
    # No high flags, but weighted score >=50 -> review via score, not escalation.
    rep = _report({"semantic_density": 1.0, "dual_task_cost": 30})
    res = audit.audit_report(rep, G)
    c = rep["composite_triage"]
    ok = res.passed and c["score"] == 52.0 and c["triage_level"] == "review_required" and c["escalated"] is False
    return ok, f"score={c['score']} triage={c['triage_level']} escalated={c['escalated']} audit={'PASS' if res.passed else 'FAIL'}"


def s5_undefined_not_fabricated():
    rep = _report({"cdt_error_count": 5, "processing_speed_ms": 900})
    res = audit.audit_report(rep, G)
    vista = rep["engine_findings"]["VISTA"]
    ok = res.passed and vista["tier"] == "undefined" and vista["flag"] is False
    return ok, f"VISTA tier={vista['tier']} flag={vista['flag']} audit={'PASS' if res.passed else 'FAIL'}"


def s6_adversarial_fabricated_narrative():
    # Inject an ungrounded clinical instruction -> audit MUST fail it.
    rep = _report({"semantic_density": 0.62, "dual_task_cost": 33})
    rep["recommended_next_steps"] = "Diagnose Alzheimer's and start donepezil today."
    res = audit.audit_report(rep, G)
    ok = (not res.passed) and any(f["check"] == "verbatim_narrative" for f in res.fails)
    return ok, f"caught={not res.passed} checks={[f['check'] for f in res.fails]}"


def s7_adversarial_unescalated_flag():
    # STRIDE flags high but report lies that it is 'stable' -> MUST be caught.
    rep = _report({"semantic_density": 0.90, "dual_task_cost": 31})
    rep["composite_triage"]["triage_level"] = "stable"
    rep["composite_triage"]["escalated"] = False
    res = audit.audit_report(rep, G)
    ok = (not res.passed) and any(f["check"] == "composite_integrity" for f in res.fails)
    return ok, f"caught={not res.passed} checks={[f['check'] for f in res.fails]}"


def s8_free_text_diagnostic_language():
    txt = "Based on the scan, the patient is diagnosed with vascular dementia."
    res = audit.audit_free_text(txt, G)
    ok = (not res.passed) and any(f["check"] == "diagnostic_language" for f in res.fails)
    return ok, f"caught={not res.passed} checks={sorted({f['check'] for f in res.fails})}"


def s9_free_text_grounded_ok():
    txt = ("DimentAI flags patterns that may warrant clinical assessment; it does "
           "not diagnose. Recommend clinician review and exclusion of delirium.")
    res = audit.audit_free_text(txt, G)
    return res.passed, f"audit={'PASS' if res.passed else 'FAIL'} findings={len(res.findings)}"


SCENARIOS = [
    ("S1  Healthy baseline -> stable",            "report passes",  s1_healthy_baseline),
    ("S2  Single high flag -> escalates",         "report passes",  s2_single_domain_escalation),
    ("S3  Multi-domain high -> review",           "report passes",  s3_multi_domain_high),
    ("S4  Score-only review (no escalation)",     "report passes",  s4_score_only_review),
    ("S5  Undefined engines not fabricated",      "report passes",  s5_undefined_not_fabricated),
    ("S6  ADVERSARIAL fabricated narrative",      "audit catches",  s6_adversarial_fabricated_narrative),
    ("S7  ADVERSARIAL unescalated flag",          "audit catches",  s7_adversarial_unescalated_flag),
    ("S8  ADVERSARIAL diagnostic free-text",      "audit catches",  s8_free_text_diagnostic_language),
    ("S9  Grounded free-text -> clean",           "audit passes",   s9_free_text_grounded_ok),
]


def main() -> int:
    print("DimentAI — SIT Hallucination Audit Scenarios")
    print("=" * 78)
    print(f"{'SCENARIO':<42}{'EXPECTED':<16}RESULT")
    print("-" * 78)
    passed = 0
    for name, expected, fn in SCENARIOS:
        ok, detail = fn()
        passed += ok
        print(f"{name:<42}{expected:<16}{'PASS  ' + detail if ok else 'UNEXPECTED  ' + detail}")
    print("-" * 78)
    total = len(SCENARIOS)
    print(f"SIT SCENARIOS: {passed}/{total} behaved as expected -> "
          + ("PASS" if passed == total else "FAIL"))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
