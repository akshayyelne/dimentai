import os
from fastapi import FastAPI
from google.cloud import firestore
import uvicorn

app = FastAPI()

# Explicitly using your project and database names
db = firestore.Client(project="dimentai1", database="dimentdata")

@app.get("/")
async def health():
    return {"status": "DimentAI Engine Online"}

@app.get("/synthesize")
async def synthesize_biomarkers(user_id: str = "test_user_001"):
    try:
        doc_ref = db.collection("assessments").document(user_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return {"error": f"Document {user_id} not found in dimentdata"}
            
        data = doc.to_dict()
        res = data.get("results", {})
        
        # Clinical weighting
        score = (res.get("dual_task_cost", 0) * 0.4) + (res.get("semantic_density", 0) * 40)
        
        return {
            "user_id": user_id,
            "composite_score": round(score, 2),
            "triage_level": "stable" if score < 50 else "review_required"
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)