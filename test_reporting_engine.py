"""Deterministic tests for the Phase 4.3 Reporting Engine.

Metrics aligned to main.py biomarker scores (clock/oculomotor/gait, 0-10,
higher = healthier). ECHO has no live scorer yet -> 'undefined' at runtime.
"""
import json
import reporting_engine as re


G = re.load_grounding()


def test_low_risk_patient_is_stable():
    # all scores high (healthy) -> low_risk; composite 9.0 (>=7) -> stable
    rep = re.build_report("pt_low", {"clock_score": 9, "oculomotor_score": 9,
                                     "gait_score": 9, "echo_score": 9}, G)
    assert rep["composite_triage"]["triage_level"] == "stable"
    assert rep["composite_triage"]["escalated"] is False
    assert rep["engine_findings"]["VISTA"]["tier"] == "low_risk"
    assert rep["engine_findings"]["STRIDE"]["tier"] == "low_risk"
    assert rep["engine_findings"]["VISTA"]["flag"] is False


def test_high_risk_patient_flags_and_reviews():
    # all scores low (unhealthy) -> high flags; composite 3.0 (<7) -> review_required
    rep = re.build_report("pt_high", {"clock_score": 3, "oculomotor_score": 3, "gait_score": 3}, G)
    assert rep["engine_findings"]["VISTA"]["tier"] == "high_priority_flag"
    assert rep["engine_findings"]["VISTA"]["flag"] is True
    assert rep["engine_findings"]["STRIDE"]["tier"] == "high_priority_flag"
    assert rep["composite_triage"]["triage_level"] == "review_required"


def test_composite_escalates_on_single_engine_flag():
    # clock 9 / oculo 9 (healthy) but gait 4 (STRIDE high flag).
    # composite = 9*0.5+9*0.3+4*0.2 = 8.0 (>=7, base stable) -> escalation forces review.
    rep = re.build_report("pt_esc", {"clock_score": 9, "oculomotor_score": 9, "gait_score": 4}, G)
    assert rep["engine_findings"]["VISTA"]["flag"] is False
    assert rep["engine_findings"]["STRIDE"]["flag"] is True
    assert rep["composite_triage"]["base_triage_level"] == "stable"
    assert rep["composite_triage"]["triage_level"] == "review_required"
    assert rep["composite_triage"]["escalated"] is True
    assert rep["composite_triage"]["escalated_by"] == ["STRIDE"]


def test_review_required_threshold():
    # all moderate (6) -> composite 6.0 (<7) -> review via score, no high flags
    rep = re.build_report("pt_rev", {"clock_score": 6, "oculomotor_score": 6, "gait_score": 6}, G)
    assert rep["composite_triage"]["score"] == 6.0
    assert rep["composite_triage"]["triage_level"] == "review_required"
    assert rep["composite_triage"]["escalated"] is False


def test_undefined_engines_are_not_fabricated():
    # Only clock_score supplied -> engines without a measurement must be 'undefined', not guessed
    rep = re.build_report("pt_x", {"clock_score": 9}, G)
    assert rep["engine_findings"]["ECHO"]["tier"] == "undefined"
    assert rep["engine_findings"]["FOCUS"]["tier"] == "undefined"
    assert rep["engine_findings"]["VISTA"]["tier"] == "low_risk"
    assert rep["engine_findings"]["ECHO"]["flag"] is False


def test_report_is_marked_synthetic_and_non_diagnostic():
    rep = re.build_report("pt_x", {"clock_score": 8, "oculomotor_score": 8, "gait_score": 8}, G)
    assert rep["not_for_clinical_use"] is True
    assert rep["data_status"] == "SYNTHETIC_MOCK_FIXTURE"
    assert "does not diagnose" in rep["disclaimer"]


def test_no_clinical_text_outside_the_fixture():
    """Hallucination guard: clinical narrative fields must be verbatim from the fixture."""
    rep = re.build_report("pt_x", {"clock_score": 8, "oculomotor_score": 8, "gait_score": 8}, G)
    assert rep["disclaimer"] == G["by_id"]["real-cdss-024"]["content"]
    assert rep["differential_exclusions_required"] == G["by_id"]["real-exclusion-020"]["content"]
    assert rep["recommended_next_steps"] == G["by_id"]["real-pathway-022"]["content"]


def test_every_finding_carries_provenance():
    rep = re.build_report("pt_x", {"clock_score": 8, "oculomotor_score": 7, "gait_score": 6}, G)
    for finding in rep["engine_findings"].values():
        assert finding["provenance"], f"{finding['engine']} missing provenance"
    assert rep["grounding_sources"], "report must list grounding sources used"


def test_markdown_renders_and_warns():
    rep = re.build_report("pt_high", {"clock_score": 3, "oculomotor_score": 3, "gait_score": 3}, G)
    md = re.render_markdown(rep)
    assert "NOT FOR CLINICAL USE" in md
    assert "🚩" in md  # a high flag is rendered
    assert "Non-diagnostic statement" in md


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
        passed += 1
    print(f"\n{passed}/{len(fns)} deterministic tests passed.")

    print("\n--- sample rendered report (single-domain escalation) ---\n")
    sample = re.build_report("sit_patient_99", {"clock_score": 9, "oculomotor_score": 9, "gait_score": 4}, G)
    print(re.render_markdown(sample))
