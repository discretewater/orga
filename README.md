# ORGA: Deterministic Organization Profiler

**A fast, explainable, non-LLM extraction engine for profiling institutional websites.**

---

## 🎯 What is ORGA?

ORGA is a Python-based profiling engine and microservice suite designed to autonomously navigate an organization's website and extract a highly structured JSON profile. It discovers global locations, extracts clean contact data (phones, emails, social footprints), and determines the organization's primary industry category.

**Crucially, ORGA is not an LLM.** It is built entirely on deterministic rules, semantic heuristics, JSON-LD parsing, and lightweight statistical Bayesian models.

## ⚡ Output Snapshot

*A minimal example of the structured JSON output generated for a hospital website:*

```json
{
  "name": "CHEO",
  "org_type": "Hospital",
  "categories": ["Hospital", "NonProfit"],
  "locations": [
    {
      "address": {
        "raw": "401 Smyth Road, Ottawa ON K1H 8L1",
        "postal_code": "K1H 8L1",
        "city": "Ottawa"
      },
      "confidence": 0.9
    }
  ],
  "phones": [
    { "value": "+16137377600", "kind": "phone" }
  ],
  "social_links": [
    { "value": "https://facebook.com/cheokids", "kind": "social" }
  ]
}
```

## 🧠 Why No LLMs?

In an era of generative AI, why build a deterministic extractor?

1. **Extreme Speed & Cost Efficiency:** ORGA processes a full organization (navigating up to 5 sub-pages like `/about` or `/contact`) in **under 0.7 seconds** per site. It requires negligible CPU/Memory overhead, allowing you to process 10,000 organizations for pennies rather than dollars.
2. **100% Explainability:** Every extracted phone number, every inferred category (e.g., `Hospital` vs. `University`), and every discarded link is fully traceable. The JSON payload includes a `debug_info` block detailing the exact CSS selector, regex match, or weighted rule path that produced the result.
3. **No Hallucinations:** When ORGA fails, it fails predictably (e.g., returning an empty field). It will never invent a phone number or confidently hallucinate an office address.

## ✨ Core Features

* **Intelligent Discovery:** Automatically finds high-value pages (`/contact`, `/locations`, `/about`) from a root URL.
* **Aggressive Noise Filtering:** Employs suppression matrices and page-weighting to strip out UI navigation noise and generic boilerplate text.
* **Layered Classification:** Identifies primary institutional types (e.g., `Government`, `Hospital`, `NonProfit`, `InternationalOrg`) using a two-tier weighted keyword and Bayesian frequency model.
* **Concurrent Microservices:** Includes two Dockerized FastAPI services for real-time single-URL extraction and asynchronous batch processing.

## 🛑 Known Boundaries & Limitations

ORGA operates at the absolute ceiling of what rule-based extraction can achieve. You should understand its limits:

* **Good Fit:** Generating a massive directory of structured contacts and primary categories for standard institutional sites (Hospitals, Universities, NGOs, Government Agencies).
* **Poor Fit:** Open-world semantic reading tasks, analyzing deep PDF reports, or distinguishing nuanced corporate hierarchies (e.g., distinguishing a holding company from its subsidiary if both use identical website templates).
* **Address Parsing:** While highly resilient, extracting perfect Street/City/Region splits from unstructured, conversational footers without NLP remains challenging and will occasionally result in `partially_parsed` raw strings.

---

## 🚀 Quickstart

### 1. Run the Microservices via Docker

Ensure you have Docker and Docker Compose installed.

```bash
git clone https://github.com/discretewater/orga.git
cd orga

# Start the Extractor (8000) and Job Manager (8001) services
docker compose up --build -d
```

### 2. Demo: Single Extraction

Extract a profile for the World Health Organization:

```bash
curl -X POST "http://127.0.0.1:8000/extract" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://www.who.int"}' | jq .
```

*You will receive a rich JSON profile containing the WHO's global contact points, social links, and a primary classification of `InternationalOrg`.*

### 3. Demo: Batch Processing

Submit multiple URLs to the async Job Manager:

```bash
# 1. Submit the Job
curl -s -X POST "http://127.0.0.1:8001/jobs" \
     -H "Content-Type: application/json" \
     -d '{"urls": ["https://www.harvard.edu", "https://www.cheo.on.ca"]}'

# Expected output: {"job_id": "uuid-...", "status": "pending"}

# 2. Poll for Results (Replace UUID with the one from the previous step)
curl -s "http://127.0.0.1:8001/jobs/{job_id}" | jq .
```

---

## 🏗️ Architecture Summary

1. **Fetcher:** Utilizes `httpx` and `aiolimiter` to aggressively fetch HTML while respecting concurrency limits.
2. **Discoverer:** Heuristically scores anchor links to branch out from the root domain into contact/about pages.
3. **Parsers:** `selectolax`-powered extraction targeting DOM zones, JSON-LD schemas, and normalized regex patterns.
4. **Classifier:** A tiered engine scoring terms across zones (`<title>`, `<h1>`, `<body>`) against a weighted taxonomy.
5. **Aggregator:** An institution-level decider that weights page evidence, applies suppression rules (e.g., a strong "Hospital" signal suppresses weak "Association" noise), and yields the final profile.

## 🔮 Roadmap

ORGA M7.1 is currently in a frozen baseline state.

Future enhancements will explore adding a **Lightweight Supervised Post-Calibration Model** (e.g., XGBoost over debug scores) to refine category boundaries without sacrificing the speed and determinism of the core extraction layer. We will not be migrating to an LLM-first architecture.