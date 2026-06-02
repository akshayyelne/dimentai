# DimentAI Clinical Engine

Backend engine for clinical intelligence, biomarker synthesis, and edge data handover.

## Deployment

To deploy the engine to Google Cloud Run with sufficient memory for processing long transcriptions, use the following command:

```bash
# Single-line command (Recommended for PowerShell and CMD)
gcloud run deploy dimentai-engine --source . --memory 2Gi --region asia-northeast1 --project dimentai1 --allow-unauthenticated
```

*Note: Memory is set to 2Gi to support the `/summarize` endpoint logic for large documents.*
