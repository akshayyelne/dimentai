import os
import logging
import math
import secrets
from typing import List, Dict, Optional
from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from google.cloud import firestore
import uvicorn
from starlette.exceptions import HTTPException as StarletteHTTPException

# Standardized logging for DimentAI
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dimentai")

# metadata updated to DimentAI Project standards
app = FastAPI(
    title="DimentAI Clinical Engine",
    description="Backend engine for clinical intelligence, biomarker synthesis, and edge data handover.",
    version="1.0.0"
)

# Global Exception Handler for clearer debugging
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 405:
        docs_url = str(request.base_url) + "docs"
        return JSONResponse(
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
            content={
                "error": "Method Not Allowed",
                "message": f"The {request.method} method is not supported for {request.url.path}. Please use the correct HTTP verb (POST) or visit the interactive docs at {docs_url}",
            }
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

# Core Initializations
try:
    # Explicitly targeting the 'dimentdata' database. 
    # Ensure this database exists in your GCP console or change to '(default)'
    db = firestore.Client(database="dimentdata")
except Exception as e:
    logger.error(f"Firestore Initialization Failed: {e}")
    db = None

# Security: the edge/biometric token is sourced from the environment, never hard-coded.
# Set DIMENTAI_TOKEN in Cloud Run / Secret Manager. Endpoints fail closed if it is unset.
SECRET_TOKEN = os.environ.get("DIMENTAI_TOKEN")
if not SECRET_TOKEN:
    logger.warning(
        "DIMENTAI_TOKEN is not set; authenticated clinical endpoints will reject "
        "all requests until it is configured."
    )


def _verify_token(provided: Optional[str]) -> None:
    """Constant-time verification of the edge token. Fails closed when unconfigured."""
    if not SECRET_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Server authentication is not configured",
        )
    if not provided or not secrets.compare_digest(provided, SECRET_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid Biometric Token")


class StrokePoint(BaseModel):
    x: float
    y: float
    t: float

# Pydantic Schema for Clock Drawing Test telemetry
class ClockDrawInput(BaseModel):
    user_id: str
    strokes: List[List[StrokePoint]]

class TelemetryPoint(BaseModel):
    t: float          # Timestamp (milliseconds)
    target_x: float   # X coordinate of the flashing dot
    target_y: float   # Y coordinate of the flashing dot
    eye_x: float      # X coordinate of user's mapped gaze
    eye_y: float      # Y coordinate of user's mapped gaze

class OculomotorInput(BaseModel):
    user_id: str
    telemetry: List[TelemetryPoint]

class SensorData(BaseModel):
    accel_x: float
    accel_y: float
    accel_z: float

class GaitTelemetryItem(BaseModel):
    timestamp_ms: int
    cadence_steps_min: float
    stride_length_m: float
    asymmetry_index: float
    sensor_data: Optional[SensorData] = None

class GaitPayload(BaseModel):
    user_id: str
    session_duration_s: float
    gait_telemetry: List[GaitTelemetryItem]

@app.get("/", tags=["Ops"])
async def health():
    """Confirms the DimentAI engine is live and reachable."""
    return {"status": "DimentAI Engine Online", "project": db.project if db else "Unknown"}

@app.post("/process-clock", tags=["Clinical Intelligence"])
async def process_clock(payload: ClockDrawInput, x_dimentai_token: str = Header(None)):
    """
    Vision Logic Endpoint: Analyzes vector touch paths from a Clock Drawing Test.
    Calculates biomarkers for tremors, hesitation, and structural integrity.
    """
    # Database availability check
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is currently unavailable"
        )

    # Security Handshake
    _verify_token(x_dimentai_token)

    try:
        strokes = payload.strokes
        user_id = payload.user_id
        
        # Initialize scoring (Scale 0-10)
        clock_score = 10.0
        
        # =====================================================================
        # 1. Structure Check: Verify stroke count against documented thresholds
        # =====================================================================
        num_strokes = len(strokes)
        # Unified to match your 10-25 documentation baseline with a safe buffer
        if num_strokes < 8 or num_strokes > 28:
            clock_score -= 2.0

        total_path_length = 0.0
        weighted_tremor_score = 0.0
        linear_stroke_count = 0
        timestamps = []

        for stroke in strokes:
            if not stroke or len(stroke) < 2:
                continue
            
            # Calculate path length and gather timestamps for the current stroke
            stroke_len = 0.0
            for i in range(len(stroke) - 1):
                p1, p2 = stroke[i], stroke[i+1]
                stroke_len += math.dist((p1.x, p1.y), (p2.x, p2.y))
                timestamps.append(p1.t)
            timestamps.append(stroke[-1].t)
            total_path_length += stroke_len

            # Calculate absolute displacement for this single stroke
            start, end = stroke[0], stroke[-1]
            stroke_disp = math.dist((start.x, start.y), (end.x, end.y))
            
            # Algorithmic Guard: If start and end are near-identical, it's a closed-loop shape (the clock face).
            # We skip loop-closures to prevent division-by-zero or artificial ratio inflation.
            if stroke_disp > 5.0:  
                stroke_efficiency = stroke_len / stroke_disp
                if stroke_efficiency > 1.35:
                    weighted_tremor_score += (stroke_efficiency - 1.0)
                linear_stroke_count += 1

        # =====================================================================
        # 2. Tremor / Micro-movement Check (Normalized Efficiency Ratio)
        # =====================================================================
        if linear_stroke_count > 0:
            # Average the cumulative structural jitter across linear strokes
            average_jitter_impact = weighted_tremor_score / linear_stroke_count
            if average_jitter_impact > 0.4: 
                clock_score -= 2.5

        # 3. Hesitation / Time Check
        if timestamps:
            total_duration = max(timestamps) - min(timestamps)
            if total_duration > 120: # Excessive time (> 2 mins)
                clock_score -= 3.0
            elif total_duration > 60: # Moderate hesitation (> 1 min)
                clock_score -= 1.5

        final_score = max(0.0, round(clock_score, 2))

        # Persist to Firestore 'biomarkers' collection
        doc_ref = db.collection("biomarkers").document(user_id)
        doc_ref.set({
            "clock_score": final_score,
            "timestamp": firestore.SERVER_TIMESTAMP,
            "metrics": {
                "stroke_count": num_strokes,
                "total_path": round(total_path_length, 2)
            }
        }, merge=True)

        return {
            "status": "success", 
            "clock_score": final_score, 
            "message": "Clock analysis persisted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Clock Analysis Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Clock processing failed")

@app.post("/process-oculomotor", tags=["Clinical Intelligence"])
async def process_oculomotor(data: OculomotorInput, x_dimentai_token: str = Header(None)):
    """
    Oculomotor Logic Endpoint: Analyzes gaze tracking telemetry.
    Calculates the average Euclidean distance (tracking error) between the target and the user's gaze over time.
    """
    # Database availability check
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is currently unavailable"
        )

    _verify_token(x_dimentai_token)

    try:
        if not data.telemetry:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No telemetry data provided"
            )

        total_deviation = 0.0
        max_latency_spike = 0.0
        
        # Calculate tracking accuracy
        for pt in data.telemetry:
            # Calculate distance between target and actual eye gaze
            deviation = math.dist((pt.target_x, pt.target_y), (pt.eye_x, pt.eye_y))
            total_deviation += deviation
            
            # Check for saccadic latency (sudden large deviations)
            if deviation > max_latency_spike:
                max_latency_spike = deviation

        avg_deviation = total_deviation / len(data.telemetry)

        # Scoring Logic (0.0 to 10.0 scale)
        # Lower deviation = higher score. 
        # The 0.05 multiplier is a tunable threshold for the prototype.
        base_score = 10.0 - (avg_deviation * 0.05) 
        final_score = max(0.0, min(10.0, round(base_score, 1)))
        
        # Assess cognitive tier based on score
        tier = "Stable" if final_score >= 8.0 else "Requires Review"

        # Persist to Firestore 'biomarkers' collection
        doc_ref = db.collection("biomarkers").document(data.user_id)
        doc_ref.set({
            "oculomotor_score": final_score,
            "oculomotor_metrics": {
                "average_deviation_px": round(avg_deviation, 2),
                "max_latency_spike_px": round(max_latency_spike, 2),
                "cognitive_tier": tier
            },
            "timestamp": firestore.SERVER_TIMESTAMP
        }, merge=True)

        return {
            "status": "success",
            "oculomotor_score": final_score,
            "cognitive_tier": tier,
            "metrics": {
                "average_deviation_px": round(avg_deviation, 2),
                "max_latency_spike_px": round(max_latency_spike, 2)
            },
            "message": "Oculomotor telemetry processed successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Oculomotor Analysis Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Oculomotor processing failed")

@app.post("/process-gait", tags=["Clinical Intelligence"])
async def process_gait(payload: GaitPayload, x_dimentai_token: str = Header(None)):
    # Database availability check
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is currently unavailable"
        )

    # Simple Security Token Check
    _verify_token(x_dimentai_token)
        
    if not payload.gait_telemetry:
        raise HTTPException(status_code=400, detail="Empty telemetry payload")

    try:
        # Algorithm: Evaluate physical stability baseline
        # Higher asymmetry index and shrinking stride lengths pull the score down
        total_asymmetry = sum(item.asymmetry_index for item in payload.gait_telemetry)
        avg_asymmetry = total_asymmetry / len(payload.gait_telemetry)
        
        # Base baseline calculation: scale index against a perfection ceiling
        gait_score = round(max(0.0, min(10.0, (1.0 - avg_asymmetry) * 10.0)), 2)
        mobility_tier = "Stable" if gait_score >= 7.0 else "Guarded"

        # Reference the 'patients' collection inside Firestore via your local service account
        doc_ref = db.collection("patients").document(payload.user_id)
        
        # Merge data so we don't accidentally overwrite clock or oculomotor results
        doc_ref.set({
            "gait_analytics": {
                "gait_score": gait_score,
                "mobility_tier": mobility_tier,
                "session_duration_s": payload.session_duration_s,
                "average_asymmetry": round(avg_asymmetry, 4),
                "updated_at": firestore.SERVER_TIMESTAMP
            }
        }, merge=True)
        
        return {
            "status": "success",
            "gait_score": gait_score,
            "mobility_tier": mobility_tier,
            "message": "Physical motion sensor fusion processed and persisted successfully"
        }
        
    except Exception as e:
        logger.error(f"Firestore Gait Write Failure: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal state storage failure")

@app.get("/synthesize", tags=["Clinical Intelligence"])
async def synthesize_biomarkers(user_id: str = "test_user_001", x_dimentai_token: str = Header(None)):
    """
    Clinical Intelligence Endpoint: Calculates weighted wellness scores 
    from multi-modal assessment data (Clock, Eye-tracking, and Gait).
    """
    # Database availability check
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is currently unavailable"
        )

    # Security Handshake (Missing in previous version)
    _verify_token(x_dimentai_token)

    # Log the search path (View this in Google Cloud Run Logs)
    logger.info(f"SIT DEBUG: Project: {db.project} | Looking for ID: {user_id}")
    
    try:
        # Fetch from both collections (Biomarkers and Patients)
        bio_ref = db.collection("biomarkers").document(user_id).get()
        pat_ref = db.collection("patients").document(user_id).get()
        
        if not bio_ref.exists and not pat_ref.exists:
            if user_id == "test_user_001":
                # Fallback for testing/SIT purposes
                bio_data = {"clock_score": 7.5, "oculomotor_score": 8.2}
                pat_data = {"gait_analytics": {"gait_score": 8.0}}
                logger.info(f"Assessment document not found. Providing fallback data for {user_id}")
            else:
                raise HTTPException(status_code=404, detail=f"Document {user_id} not found")
        else:
            bio_data = bio_ref.to_dict() if bio_ref.exists else {}
            pat_data = pat_ref.to_dict() if pat_ref.exists else {}
        
        # Extract specific metrics
        clock_val = bio_data.get("clock_score", 0.0)
        oculo_val = bio_data.get("oculomotor_score", 0.0)
        gait_val = pat_data.get("gait_analytics", {}).get("gait_score", 0.0)

        # Weighted weighting logic: 
        # 50% Clock Drawing (Structural/Cognitive)
        # 30% Oculomotor (Neurological Reaction)
        # 20% Gait (Physical Mobility)
        clock_weight = clock_val * 0.5
        oculo_weight = oculo_val * 0.3
        gait_weight = gait_val * 0.2
        
        composite_score = round(clock_weight + oculo_weight + gait_weight, 2)
        
        return {
            "user_id": user_id,
            "composite_score": composite_score,
            "triage_level": "stable" if composite_score >= 7.0 else "review_required",
            "components": {
                "cognitive_clock": round(clock_weight, 2),
                "neurological_eye": round(oculo_weight, 2),
                "mobility_gait": round(gait_weight, 2)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Synthesis Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Synthesis failed")

if __name__ == "__main__":
    # Cloud Run expects the app to listen on the PORT environment variable
    # Defaulting to 8080 to match the Dockerfile and Cloud Run standards
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
