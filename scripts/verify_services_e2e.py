import asyncio
import httpx
import json
import sys
import time
from datetime import datetime
from collections import Counter

BATCH_FILE = "examples/fixtures/batch_urls.txt"
OUTPUT_FILE = "service_test_outcome.txt"
EXTRACTOR_URL = "http://127.0.0.1:8000"
JOB_URL = "http://127.0.0.1:8001"

async def log(f, message, console=True):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    if console:
        print(line)
    f.write(line + "\n")
    f.flush()

async def run_test():
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        await log(f, "=== ORGA M6.1 Service Comprehensive Quality Assessment ===\n")
        
        # 1. Connectivity & Health Check
        await log(f, "--- Phase 1: Service Connectivity Check ---")
        async with httpx.AsyncClient() as client:
            connected = False
            for i in range(10): # Retry for 20 seconds
                try:
                    resp_ext = await client.get(f"{EXTRACTOR_URL}/health", timeout=5)
                    resp_job = await client.get(f"{JOB_URL}/health", timeout=5)
                    
                    if resp_ext.status_code == 200 and resp_job.status_code == 200:
                        await log(f, f"Extractor Service (8000): {resp_ext.status_code} | {resp_ext.json()}")
                        await log(f, f"Job Service (8001):       {resp_job.status_code} | {resp_job.json()}")
                        connected = True
                        break
                except Exception:
                    await log(f, f"Waiting for services... ({i+1}/10)")
                    await asyncio.sleep(2)
            
            if not connected:
                await log(f, f"FATAL: Service connection failed after retries.")
                return

        # Read URLs
        with open(BATCH_FILE, "r") as bf:
            urls = [line.strip() for line in bf if line.strip()]
        await log(f, f"\nLoaded {len(urls)} Validation Targets from {BATCH_FILE}")

        # 2. Detailed Single Extraction Test (CHEO Focus)
        target_url = "https://www.cheo.on.ca"
        await log(f, "\n--- Phase 2: Deep-Dive Single Extraction (Stability Probe) ---")
        await log(f, f"Target: {target_url}")
        
        async with httpx.AsyncClient() as client:
            start_time = time.time()
            try:
                resp = await client.post(
                    f"{EXTRACTOR_URL}/extract", 
                    json={"url": target_url},
                    timeout=60
                )
                duration = time.time() - start_time
                
                if resp.status_code == 200:
                    data = resp.json()
                    await log(f, f"✅ SUCCESS (Time: {duration:.2f}s)")
                    
                    # Extract Quality Metrics
                    name = data.get("name", "N/A")
                    locs = data.get("locations", [])
                    phones = data.get("phones", [])
                    debug = data.get("debug_info", {})
                    
                    await log(f, f"  Name: {name}")
                    await log(f, f"  Locations: {len(locs)}")
                    await log(f, f"  Phones:    {len(phones)}")
                    
                    # Log Debug Info for Quality Review
                    if debug:
                        await log(f, "  [Debug Metrics]:")
                        if "classification_debug" in debug:
                            await log(f, f"    - Classification Steps: {len(debug['classification_debug'])}")
                        if "filtered_social_links" in debug:
                            await log(f, f"    - Filtered Socials: {len(debug['filtered_social_links'])}")
                    
                    # Dump partial JSON for verification
                    snippet = json.dumps(data, indent=2)
                    await log(f, "\n  [Full Response Dump (First 2000 chars)]:")
                    await log(f, snippet[:2000] + "\n... (truncated)", console=False)
                else:
                    await log(f, f"❌ FAILED: {resp.status_code}")
                    await log(f, f"  Error: {resp.text}")
            except Exception as e:
                await log(f, f"❌ EXCEPTION: {str(e)}")

        # 3. Batch Job Processing (Stress Test)
        await log(f, "\n--- Phase 3: Batch Processing Stress Test ---")
        job_id = None
        async with httpx.AsyncClient() as client:
            # Submit
            try:
                resp = await client.post(f"{JOB_URL}/jobs", json={"urls": urls}, timeout=10)
                if resp.status_code == 202:
                    job_id = resp.json()["job_id"]
                    await log(f, f"Job Submitted Successfully. ID: {job_id}")
                else:
                    await log(f, f"Submission Failed: {resp.text}")
                    return
            except Exception as e:
                await log(f, f"Submission Error: {str(e)}")
                return

            # Poll
            await log(f, "Polling job status...")
            start_poll = time.time()
            while True:
                resp = await client.get(f"{JOB_URL}/jobs/{job_id}", timeout=10)
                data = resp.json()
                status = data["status"]
                elapsed = time.time() - start_poll
                
                # Dynamic status line
                sys.stdout.write(f"\rTime: {elapsed:.1f}s | Status: {status} | Done: {len(data.get('results', []))} | Failed: {len(data.get('errors', []))}")
                sys.stdout.flush()
                
                if status in ["completed", "failed"]:
                    print("") 
                    await log(f, f"\nJob Completed in {elapsed:.2f}s")
                    
                    results = data.get("results", [])
                    errors = data.get("errors", [])
                    
                    # --- QUALITY ANALYSIS REPORT ---
                    await log(f, "\n=== QUALITY ANALYSIS REPORT ===")
                    await log(f, f"Total Targets: {len(urls)}")
                    await log(f, f"Success Rate:  {len(results)/len(urls)*100:.1f}% ({len(results)}/{len(urls)})")
                    await log(f, f"Avg Time/URL:  {elapsed/len(urls):.2f}s")
                    
                    # 1. Failure Analysis
                    if errors:
                        await log(f, "\n[FAILURE LOG]")
                        for err in errors:
                            await log(f, f"❌ {err}")
                    else:
                        await log(f, "\n[FAILURE LOG]\n  (None - Perfect Run)")

                    # 2. Result Quality Sampling
                    await log(f, "\n[RESULT QUALITY SAMPLE]")
                    
                    # Collect stats
                    total_locs = sum(len(r.get("locations", [])) for r in results)
                    total_phones = sum(len(r.get("phones", [])) for r in results)
                    
                    await log(f, f"Total Extracted Locations: {total_locs}")
                    await log(f, f"Total Extracted Phones:    {total_phones}")
                    
                    # Detailed dump of each result for file record
                    await log(f, "\n--- Detailed Profile Dumps ---", console=False)
                    for i, res in enumerate(results):
                        name = res.get("name") or "Unknown"
                        url_hint = res.get("website") or "N/A"
                        await log(f, f"\n#{i+1}: {name}", console=False)
                        # Dump full debug info and warnings for assessment
                        debug_section = res.get("debug_info", {})
                        warnings = res.get("warnings", [])
                        
                        if warnings:
                            await log(f, f"  Warnings: {[w['code'] for w in warnings]}", console=False)
                        
                        await log(f, json.dumps(res, indent=2), console=False)
                    
                    await log(f, "\nDetailed profile dumps saved to file.")
                    break
                
                await asyncio.sleep(2)

if __name__ == "__main__":
    try:
        import httpx
    except ImportError:
        print("Installing httpx...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx"])
        import httpx
        
    asyncio.run(run_test())
