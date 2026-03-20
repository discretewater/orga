#!/bin/bash

# ORGA Demonstration Commands
# Ensure you have started the services first: docker compose up --build -d

set -e

EXTRACTOR_URL="http://127.0.0.1:8000"
JOB_MANAGER_URL="http://127.0.0.1:8001"

# Check for jq
if ! command -v jq &> /dev/null; then
    echo "Error: jq is not installed. Please install it (e.g., sudo apt install jq / brew install jq) to run this demo."
    exit 1
fi

echo "=== 1. Checking Service Health ==="
curl -s $EXTRACTOR_URL/health | jq .
curl -s $JOB_MANAGER_URL/health | jq .

echo -e "\n=== 2. Single URL Extraction (CHEO Hospital) ==="
echo "Extracting profile for https://www.cheo.on.ca..."
curl -s -X POST "$EXTRACTOR_URL/extract" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://www.cheo.on.ca"}' | jq . > examples/sample_output.json
echo "Saved full profile to examples/sample_output.json"

echo -e "\n=== 3. Batch Processing Demo ==="
echo "Submitting batch job..."
RESPONSE=$(curl -s -X POST "$JOB_MANAGER_URL/jobs" \
     -H "Content-Type: application/json" \
     -d '{
           "urls": [
             "https://www.harvard.edu",
             "https://www.doctorswithoutborders.org",
             "https://www.cdc.gov"
           ]
         }')

echo "Submission Response:"
echo $RESPONSE | jq .

JOB_ID=$(echo $RESPONSE | jq -r '.job_id')

echo -e "\nPolling job status for $JOB_ID..."
for i in {1..10}; do
    STATUS_RESP=$(curl -s "$JOB_MANAGER_URL/jobs/$JOB_ID")
    STATUS=$(echo $STATUS_RESP | jq -r '.status')
    
    if [ "$STATUS" == "completed" ] || [ "$STATUS" == "failed" ]; then
        echo -e "\nJob finished with status: $STATUS"
        echo "Results Summary:"
        echo $STATUS_RESP | jq '{status: .status, processed: (.results | length), failed: (.errors | length)}'
        break
    else
        echo -n "."
        sleep 2
    fi
done

echo -e "\n=== Demo Complete ==="
