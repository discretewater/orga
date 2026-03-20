from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import Optional, Dict, Any
from orga.pipeline import OrgaPipeline
from orga.model import OrgaConfig, OrganizationProfile

app = FastAPI(title="ORGA Extractor Service")

class ExtractRequest(BaseModel):
    url: HttpUrl
    config: Optional[Dict[str, Any]] = None

# Initialize pipeline globally
# In production, config might come from env vars
pipeline = OrgaPipeline(OrgaConfig())

@app.on_event("startup")
async def startup_event():
    print("INFO:  ORGA SERVICE v0.1.2 - READY")

@app.post("/extract", response_model=OrganizationProfile)
async def extract_profile(request: ExtractRequest):
    """
    Extract organization profile from a given URL.
    """
    try:
        # If per-request config is needed, we might need a new pipeline instance
        # or update the existing one's context. For MVP, we use shared pipeline.
        # But wait, OrgaPipeline holds state (fetcher semaphores)? Yes, shared fetcher.
        # But OrgaConfig is immutable-ish.
        
        # For strict correctness with custom config, we'd need new pipeline:
        if request.config:
            custom_config = OrgaConfig(**request.config)
            local_pipeline = OrgaPipeline(custom_config)
            profile = await local_pipeline.run_from_url(str(request.url))
        else:
            profile = await pipeline.run_from_url(str(request.url))
            
        return profile
    except Exception as e:
        import traceback
        print(f"ERROR processing {request.url}:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "ok"}
