# ClimateGPT Performance Enhancement

**Grounding a climate-focused language model in real satellite and water-risk data — so its answers are backed by evidence, not just fluency.**

Ask a plain-English climate question in the chat interface and get a response grounded in live environmental datasets: active-fire and thermal readings from NASA's VIIRS instrument, and global water-risk indicators from the WRI Aqueduct dataset. Instead of relying on the model's memory alone, the system retrieves the relevant real-world data first and lets the model reason over it.

---

## Why this exists

Large language models are fluent, but on specialized, fast-moving domains like climate and environmental risk they hallucinate — confidently stating figures that are outdated or simply wrong. A model asked "what's the water-stress outlook for this basin?" has no way to know the current answer unless it can look it up.

This project closes that gap. It augments a climate language model with structured, authoritative external data through a retrieval layer, so the model's answers trace back to actual measurements and published indicators rather than its training data.

---

## What it does

- **Chat interface for climate questions** — a web UI where you ask natural-language questions about thermal activity and water risk and get grounded, readable answers.
- **Live data grounding** — the system pulls from two real environmental data sources before answering:
  - **VIIRS** — NASA's Visible Infrared Imaging Radiometer Suite, supplying active-fire and thermal-anomaly data.
  - **WRI Aqueduct 4.0** — the World Resources Institute's global water-risk indicators (baseline water stress, drought risk, and related measures).
- **Tool-based retrieval (MCP)** — data access is exposed as callable tools through the Model Context Protocol, so the model can request exactly the data a question needs.
- **Validation suite** — dedicated query scripts check that the data served for VIIRS and Aqueduct matches the source of truth.

---

## Architecture
The design keeps a clean separation: the data layer (DuckDB + MCP tools) is deterministic and verifiable, while the model only reasons and writes — it never invents the underlying numbers.

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.10+ |
| Web / API | Flask (async) |
| Tool protocol | Model Context Protocol (MCP) via FastMCP |
| Data store | DuckDB |
| Data processing | pandas, Jupyter (EDA notebooks) |
| Containerization | Docker |
| Data sources | NASA VIIRS, WRI Aqueduct 4.0 |

---

## Data sources

- **NASA VIIRS** — active-fire and thermal-anomaly satellite data.
- **WRI Aqueduct 4.0** — global water-risk indicators. Technical documentation is included in `Docs/` for reference.

---

## Getting started

### Prerequisites
- Python 3.10+
- Docker (optional)
- A running MCP server endpoint for the data tools

### Setup

```bash
git clone https://github.com/Mkatika37/climategpt-performance-enhancement.git
cd climategpt-performance-enhancement
pip install -e .
cp .env.example .env   # supply model endpoint, MCP URLs, optional API key
bash run_adapters.sh   # start the MCP data adapters
bash run_servers.sh    # launch the app
```

Then open the chat UI in your browser and start asking questions.

### Configuration

The app reads its settings from environment variables (never hard-coded), including the MCP tool endpoints and an optional bearer token. See `.env.example` for the full list.

---

## Validation

```bash
python tests/VIIRS_Thermal_Validation_queries.py
python tests/Aqueduct_Validation_Queries.py
```

---

## Roadmap

- Expand coverage to additional environmental datasets
- Cache frequently requested queries for lower latency
- Richer visualizations of thermal and water-risk data in the chat UI
- Deployment guide for a hosted environment

---

## License

MIT
