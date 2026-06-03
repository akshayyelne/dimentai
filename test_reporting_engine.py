"""Deterministic tests for the Phase 4.3 Reporting Engine.

These double as the seed for the Phase 4.4 Hallucination Audit: a deterministic
report must (a) classify against the fixture, (b) attach provenance to every
finding, and (c) NEVER contain clinical text that isn't present in the grounding
fixture.
"""
import json
import reporting_engine as re


G = re.load_grounding()


def test_low_risk_patient_is_stable():
    # semantic_density 0.95 -> low; dual_task_cost 10 -> low; composite 0.4*10+40*0.95=42 -> stable
    rep = re.build_report("pt_low", {"semantic_density": 0.95, "dual_task_cost": 10}, G)
    assert rep["composite_triage"]["triage_level"] == "stable"
    assert rep["composite_triage"]["escalated"] is False
    assert rep["engine_findings"]["ECHO"]["tier"] == "low_risk"
    assert rep["engine_findings"]["STRIDE"]["tier"] == "low_risk"
    assert rep["engine_findings"]["ECHO"]["flag"] is False


def test_high_risk_patient_flags_and_reviews():
    # semantic_density 0.60 -> high flag; dual_task_cost 35 -> high; composite 0.4*35+40*0.6=38 (<50)
    # base would be 'stable', but the high flags must escalate it to 'review_required'.
    rep = re.build_report("pt_high", {"semantic_density": 0.60, "dual_task_cost": 35}, G)
    assert rep["engine_findings"]["ECHO"]["tier"] == "high_priority_flag"
    assert rep["engine_findings"]["ECHO"]["flag"] is True
    assert rep["engine_findings"]["STRIDE"]["tier"] == "high_priority_flag"
    assert rep["composite_triage"]["score"] < 50
    assert rep["composite_triage"]["base_triage_level"] == "stable"
    assert rep["composite_triage"]["triage_level"] == "review_required"
    assert rep["composite_triage"]["escalated"] is True


def test_composite_escalates_on_single_engine_flag():
    # ECHO low (0.90), STRIDE high (dtc 31). Weighted score 31*0.4+0.90*40=48.4 (<50, base stable),
    # but the single STRIDE high-flag must still force review_required.
    rep = re.build_report("pt_esc", {"semantic_density": 0.90, "dual_task_cost": 31}, G)
    assert rep["engine_findings"]["ECHO"]["flag"] is False
    assert rep["engine_findings"]["STRIDE"]["flag"] is True
    assert rep["composite_triage"]["base_triage_level"] == "stable"
    assert rep["composite_triage"]["triage_level"] == "review_required"
    assert rep["composite_triage"]["escalated"] is True
    assert rep["composite_triage"]["escalated_by"] == ["STRIDE"]


def test_review_required_threshold():
    # push composite >= 50: dual_task_cost 30 (=12) + semantic_density 1.0 (=40) = 52
    rep = re.build_report("pt_rev", {"semantic_density": 1.0, "dual_task_cost": 30}, G)
    assert rep["composite_triage"]["score"] == 52.0
    assert rep["composite_triage"]["triage_level"] == "review_required"


def test_undefined_engines_are_not_fabricated():
    # VISTA/FOCUS have no numeric thresholds in the fixture -> must be 'undefined', not guessed
    rep = re.build_report("pt_x", {"cdt_error_count": 4, "processing_speed_ms": 800}, G)
    assert rep["engine_findings"]["VISTA"]["tier"] == "undefined"
    assert rep["engine_findings"]["FOCUS"]["tier"] == "undefined"
    assert rep["engine_findings"]["VISTA"]["flag"] is False


def test_report_is_marked_synthetic_and_non_diagnostic():
    rep = re.build_report("pt_x", {"semantic_density": 0.8, "dual_task_cost": 22}, G)
    assert rep["not_for_clinical_use"] is True
    assert rep["data_status"] == "SYNTHETIC_MOCK_FIXTURE"
    assert "does not diagnose" in rep["disclaimer"]


def test_no_clinical_text_outside_the_fixture():
    """Hallucination guard: clinical narrative fields must be verbatim from the fixture."""
    rep = re.build_report("pt_x", {"semantic_density": 0.8, "dual_task_cost": 22}, G)
    assert rep["disclaimer"] == G["by_id"]["real-cdss-024"]["content"]
    assert rep["differential_exclusions_required"] == G["by_id"]["real-exclusion-020"]["content"]
    assert rep["recommended_next_steps"] == G["by_id"]["real-pathway-022"]["content"]


def test_every_finding_carries_provenance():
    rep = re.build_report("pt_x", {"semantic_density": 0.8, "dual_task_cost": 22}, G)
    for finding in rep["engine_findings"].values():
        assert finding["provenance"], f"{finding['engine']} missing provenance"
    assert rep["grounding_sources"], "report must list grounding sources used"


def test_markdown_renders_and_warns():
    rep = re.build_report("pt_high", {"semantic_density": 0.60, "dual_task_cost": 35}, G)
    md = re.render_markdown(rep)
    assert "NOT FOR CLINICAL USE" in md
    assert "🚩" in md  # the high flag is rendered
    assert "Non-diagnostic statement" in md


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
        passed += 1
    print(f"\n{passed}/{len(fns)} deterministic tests passed.")

    print("\n--- sample rendered report (high-risk patient) ---\n")
    sample = re.build_report("sit_patient_99", {"semantic_density": 0.62, "dual_task_cost": 33}, G)
    print(re.render_markdown(sample))
