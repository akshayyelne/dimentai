"""DimentAI Hallucination Audit (Phase 4.4 / SIT).

Verifies that a triage report contains NO clinical content that isn't traceable
to the grounding fixture, and that the non-diagnostic posture holds. The audit
is deliberately strict and reproducible so it can run in CI as a release gate.

Two entry points:
  * audit_report(report)      - structural/provenance/integrity audit of a
                                deterministic report dict (Phase 4.3 output).
  * audit_free_text(text)     - heuristic auditor for ANY narrative string
                                (e.g. a future LLM-generated summary): flags
                                diagnostic language and ungrounded clinical
                                acronyms.

Exit code is non-zero on FAIL so it gates a pipeline.
"""
from __future__ import annotations

import re
import sys

import reporting_engine as engine

# Report fields whose text MUST be verbatim from a specific fixture record.
VERBATIM_FIELDS = {
    "disclaimer": "real-cdss-024",
    "differential_exclusions_required": "real-exclusion-020",
    "recommended_next_steps": "real-pathway-022",
}

# Assertive diagnostic verbs that violate the non-diagnostic CDSS posture,
# UNLESS negated in the same sentence ("does not diagnose", "cannot be made").
_DIAGNOSTIC = re.compile(
    r"\b(diagnos(?:e|es|ed|is)|confirms?|definitely\s+has|is\s+diagnosed\s+with)\b",
    re.I,
)
_NEGATION = re.compile(r"\b(not|cannot|can't|without|never|no)\b", re.I)
_ACRONYM = re.compile(r"\b[A-Z]{2,6}\b")


class Finding(dict):
    def __init__(self, severity, check, detail):
        super().__init__(severity=severity, check=check, detail=detail)


class AuditResult:
    def __init__(self, findings):
        self.findings = findings

    @property
    def fails(self):
        return [f for f in self.findings if f["severity"] == "FAIL"]

    @property
    def passed(self):
        return not self.fails

    def report(self) -> str:
        if not self.findings:
            return "AUDIT PASS — no findings."
        lines = [("AUDIT PASS" if self.passed else "AUDIT FAIL") + f" — {len(self.findings)} finding(s):"]
        for f in self.findings:
            lines.append(f"  [{f['severity']}] {f['check']}: {f['detail']}")
        return "\n".join(lines)


def _corpus_acronyms(grounding) -> set:
    text = " ".join(
        (r.get("content", "") + " " + r.get("title", "") + " " + r.get("source", ""))
        for r in grounding["by_id"].values()
    )
    return set(_ACRONYM.findall(text))


def _sentences(text: str):
    return [s.strip() for s in re.split(r"(?<=[.!?;])\s+|\n", text) if s.strip()]


def audit_report(report: dict, grounding: dict | None = None) -> AuditResult:
    grounding = grounding or engine.load_grounding()
    by_id = grounding["by_id"]
    findings = []

    # 1. Clinical narrative must be verbatim from the fixture (no paraphrase/fabrication).
    for field, src in VERBATIM_FIELDS.items():
        expected = by_id.get(src, {}).get("content", "")
        if report.get(field, None) != expected:
            findings.append(Finding("FAIL", "verbatim_narrative",
                                    f"'{field}' is not verbatim from fixture record '{src}'"))

    # 2. Non-diagnostic posture.
    if report.get("not_for_clinical_use") is not True:
        findings.append(Finding("FAIL", "non_diagnostic_flag", "not_for_clinical_use must be True"))
    if "does not diagnose" not in (report.get("disclaimer") or "").lower():
        findings.append(Finding("FAIL", "disclaimer", "disclaimer missing 'does not diagnose'"))
    if not report.get("review_gate"):
        findings.append(Finding("FAIL", "review_gate", "review_gate missing"))

    # 3. Per-finding provenance + threshold integrity (recompute from the fixture).
    for eng, f in report.get("engine_findings", {}).items():
        if f.get("tier") == "undefined":
            continue
        if not f.get("provenance"):
            findings.append(Finding("FAIL", "provenance", f"{eng} finding has no provenance"))
        sid = f.get("threshold_source_id")
        if sid not in by_id:
            findings.append(Finding("FAIL", "provenance",
                                    f"{eng} threshold_source_id '{sid}' not in fixture"))
        recomputed = engine.classify(eng, f.get("value"), grounding)
        if recomputed["tier"] != f.get("tier"):
            findings.append(Finding("FAIL", "threshold_integrity",
                                    f"{eng} tier '{f.get('tier')}' not reproducible from fixture "
                                    f"(recomputed '{recomputed['tier']}') — possible fabricated classification"))

    # 4. Composite integrity (must be reproducible from the reported values).
    measurements = {f["metric"]: f["value"]
                    for f in report.get("engine_findings", {}).values()
                    if f.get("value") is not None}
    rc = engine._composite(measurements, grounding, report.get("engine_findings", {}))
    comp = report.get("composite_triage", {})
    if comp.get("score") != rc["score"] or comp.get("triage_level") != rc["triage_level"]:
        findings.append(Finding("FAIL", "composite_integrity",
                                "composite score/level not reproducible from reported values "
                                "(includes composite-escalation rule)"))

    # 5. Synthetic data must be labelled as such.
    used_synthetic = any(
        by_id.get(s, {}).get("data_status") == "SYNTHETIC_MOCK_FIXTURE"
        for s in [f.get("threshold_source_id") for f in report.get("engine_findings", {}).values()]
        if s
    )
    if used_synthetic and report.get("data_status") != "SYNTHETIC_MOCK_FIXTURE":
        findings.append(Finding("FAIL", "data_status",
                                "report uses synthetic grounding but is not marked SYNTHETIC_MOCK_FIXTURE"))

    return AuditResult(findings)


def audit_free_text(text: str, grounding: dict | None = None) -> AuditResult:
    """Heuristic auditor for arbitrary narrative (LLM-path safety net)."""
    grounding = grounding or engine.load_grounding()
    allowed = _corpus_acronyms(grounding)
    findings = []
    for sent in _sentences(text):
        if _DIAGNOSTIC.search(sent) and not _NEGATION.search(sent):
            findings.append(Finding("FAIL", "diagnostic_language",
                                    f"assertive diagnostic claim: {sent!r}"))
        for acro in set(_ACRONYM.findall(sent)) - allowed:
            findings.append(Finding("FAIL", "ungrounded_term",
                                    f"clinical acronym '{acro}' not present in grounding fixture: {sent!r}"))
    return AuditResult(findings)


def _sample_reports(grounding):
    cases = {
        "stable": {"clock_score": 9, "oculomotor_score": 9, "gait_score": 9},
        "high_flag": {"clock_score": 3, "oculomotor_score": 3, "gait_score": 3},
        "review": {"clock_score": 6, "oculomotor_score": 6, "gait_score": 6},
    }
    return {name: engine.build_report(f"audit_{name}", m, grounding)
            for name, m in cases.items()}


def main() -> int:
    grounding = engine.load_grounding()
    ok = True
    for name, rep in _sample_reports(grounding).items():
        res = audit_report(rep, grounding)
        print(f"== report:{name} ==")
        print(res.report())
        ok = ok and res.passed
    print("\nSIT HALLUCINATION AUDIT:", "PASS ✅" if ok else "FAIL ❌")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
