# Code Structure — Intelligent University Course Finder

## Project Root

```
Capstone_Project/
│
├── README.md                   # Main project documentation
├── README.pdf                  # PDF version of README
├── CODE_STRUCTURE.md           # This file
├── CODE_STRUCTURE.pdf          # PDF version of CODE_STRUCTURE
├── design_decisions.md         # Technical design rationale
├── design_decisions.pdf        # PDF version of design_decisions
├── .gitignore                  # Git ignore rules
│
├── Architecture_Diagram.png    # System architecture visualization
├── Data_Flow.png               # AI Agent data flow visualization
├── Data_Ingestion.png          # Data processing pipeline visualization
├── Search Flow.png             # Hybrid retrieval flow visualization
│
├── Source/                      # ALL SOURCE CODE LOCATED HERE
│   ├── .env                    # Environment variables (OPENAI_API_KEY, etc.)
│   ├── config.py               # Centralised configuration
│   ├── logger.py               # Logger factory
│   ├── requirements.txt        # Python dependencies
│   │
│   ├── api/                    # Backend microservice (port 8000)
│   │   ├── main.py             # FastAPI entry point
│   │   ├── schemas.py          # Pydantic models
│   │   └── core/               # recommend_logic.py (Orchestrator)
│   │
│   ├── api_gateway/            # API Gateway (port 8080)
│   │   └── gateway.py          # FastAPI proxy
│   │
│   ├── app_agents/             # AI Agents (OpenAI SDK)
│   │   ├── intent_agent.py
│   │   ├── skill_gap_agent.py
│   │   ├── career_agent.py
│   │   ├── sequencer.py
│   │   ├── advisor_agent.py
│   │   └── tools.py            # Agent function tools
│   │
│   ├── retrieval/              # Hybrid Search logic
│   │   └── hybrid_retriever.py
│   │
│   ├── guardrails/             # Safety & Validation
│   │   └── validator.py        # Presidio + intent check
│   │
│   ├── ingestion/              # Data ingestion pipeline
│   │   └── ingest.py
│   │
│   ├── data/                   # Source datasets
│   ├── storage/                # Persisted vector/keyword indices
│   ├── logs/                   # Runtime log files
│   ├── test/                   # Isolated test scripts
│   │
│   └── frontend/               # React 19 + Vite frontend
│       └── careerguidefrontend/
```

---

## Key Entry Points

All commands should be run from the project root or by navigating into the `Source/` directory.

| Command | Purpose |
|---|---|
| `python Source/ingestion/ingest.py` | One-time data ingestion |
| `cd Source && uvicorn api.main:app --port 8000 --reload` | Start backend microservice |
| `cd Source && uvicorn api_gateway.gateway:app --port 8080 --reload` | Start API Gateway |
| `cd Source/frontend/careerguidefrontend && npm run dev` | Start React frontend |
| `python Source/test/test_intent_agent.py` | Test IntentAgent |
| `python Source/test/test_guardrails.py` | Test PII redaction |

---

## Request Flow (Internal Pathing)

```
Source/frontend/src/App.jsx
  └─ POST http://localhost:8080/recommend
      └─ Source/api_gateway/gateway.py
          └─ POST http://localhost:8000/recommend
              └─ Source/api/main.py
                  └─ Source/api/core/recommend_logic.py
                      ├─ Source/guardrails/validator.py
                      ├─ Source/app_agents/intent_agent.py
                      │     └─ Source/app_agents/tools.py
                      │           └─ Source/retrieval/hybrid_retriever.py
                      ├─ Source/app_agents/skill_gap_agent.py
                      ├─ Source/app_agents/career_agent.py
                      ├─ Source/app_agents/sequencer.py
                      └─ Source/app_agents/advisor_agent.py
```
