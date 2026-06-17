import os
import unittest
from hallucination_audit import audit_report, audit_free_text

# Reads the URL from GitHub Actions settings; defaults to localhost if testing offline
BACKEND_URL = os.getenv("CLOUD_RUN_URL", "http://127.0.0.1:8000")

class TestDimentAISITScenarios(unittest.TestCase):

    def setUp(self):
        """Set up standard valid data matching our clinical grounding fixtures."""
        self.valid_disclaimer = (
            "DimentAI is a pre-clinical triage risk stratification tool. It does not provide "
            "a autonomous diagnosis. Clinicians must maintain independent diagnostic authority, "
            "perform mandatory pathology screens (B12, Folate, TFTs, FBC), and exclude acute delirium."
        )
        
        self.base_valid_report = {
            "metadata": {"data_environment": "SYNTHETIC_TEST_DATA"},
            "metrics": {
                "ECHO": {"value": 0.85, "tier": "Low Risk Baseline"},
                "STRIDE": {"value": 8.5, "tier": "Low Risk Baseline"}, # DTC < 10%
                "VISTA": {"value": 1.2, "tier": "Low Risk Baseline"},
                "FOCUS": {"value": 0.9, "tier": "Low Risk Baseline"}
            },
            "composite": {"status": "Stable", "summary": "Metrics sit safely within normal baselines."},
            "narrative": {
                "mandatory_disclaimer": self.valid_disclaimer,
                "required_exclusions": ["Delirium", "Depression", "Polypharmacy"]
            }
        }

    # ==========================================
    # 🟢 CATEGORY 1: GREEN-PATH TEST CASES
    # ==========================================

    def test_case_1_1_standard_healthy_baseline(self):
        """SIT 1.1: Verify a completely healthy, grounded report passes cleanly."""
        result = audit_report(self.base_valid_report)
        self.assertTrue(result, "Standard healthy baseline report should pass the audit.")

    def test_case_1_2_valid_high_priority_escalation(self):
        """SIT 1.2: Verify a valid escalated report passes if math and text align."""
        high_risk_report = self.base_valid_report.copy()
        high_risk_report["metrics"]["STRIDE"] = {"value": 24.5, "tier": "High-Priority Triage Flag"} # DTC > 20%
        # Composite escalation fix rule applied
        high_risk_report["composite"] = {
            "status": "review_required",
            "summary": "High-Priority flag triggered by sensor variance."
        }
        
        result = audit_report(high_risk_report)
        self.assertTrue(result, "A correctly calculated high-risk report should pass validation.")


    # ==========================================
    # 🔴 CATEGORY 2: RED-TEAM TEST CASES
    # ==========================================

    def test_case_2_1_risk_smoothing_tamper(self):
        """SIT 2.1: Audit must FAIL if high raw metrics are masked as Low Risk."""
        tampered_report = self.base_valid_report.copy()
        # Raw value is dangerously high (>20% DTC), but tier is falsely logged as low
        tampered_report["metrics"]["STRIDE"] = {"value": 24.5, "tier": "Low Risk Baseline"} 
        
        with self.assertRaises(ValueError, msg="Should fail threshold integrity checking."):
            audit_report(tampered_report)

    def test_case_2_2_silent_danger_bypass(self):
        """SIT 2.2: Audit must FAIL if an engine flags high risk but composite stays 'Stable'."""
        broken_composite_report = self.base_valid_report.copy()
        broken_composite_report["metrics"]["ECHO"] = {"value": 0.12, "tier": "High-Priority Triage Flag"}
        # Coding error bug: overall composite wasn't escalated to review_required
        broken_composite_report["composite"] = {"status": "Stable", "summary": "All clear."}
        
        with self.assertRaises(ValueError, msg="Should fail composite integrity checking."):
            audit_report(broken_composite_report)

    def test_case_2_3_medical_diagnostic_slip(self):
        """SIT 2.3: Audit must FAIL if assertive diagnostic language is used."""
        hallucinated_narrative = (
            "Based on the spatial layout errors in Vista, the patient is diagnosed with "
            "early-stage Alzheimer's Disease."
        )
        
        result = audit_free_text(hallucinated_narrative)
        self.assertFalse(result, "Free-text audit must reject absolute diagnostic claims.")

    def test_case_2_4_ungrounded_assessment_illusion(self):
        """SIT 2.4: Audit must FAIL if ungrounded clinical tracking models are hallucinated."""
        hallucinated_narrative = "Patient performed poorly on the Montreal Cognitive Assessment (MoCA)."
        
        result = audit_free_text(hallucinated_narrative)
        self.assertFalse(result, "Free-text audit must reject tests outside our sensor matrix (MoCA).")

    def test_case_2_5_legal_disclaimer_omission(self):
        """SIT 2.5: Audit must FAIL if the mandatory TGA disclaimer is modified or missing."""
        missing_disclaimer_report = self.base_valid_report.copy()
        missing_disclaimer_report["narrative"]["mandatory_disclaimer"] = "Everything looks fine!"
        
        with self.assertRaises(ValueError, msg="Should fail verbatim narrative disclaimer checking."):
            audit_report(missing_disclaimer_report)

if __name__ == "__main__":
    unittest.main()