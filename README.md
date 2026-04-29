# LeadAI

LeadAI is an AI-powered lead enrichment and sales intelligence tool built for EliseAI-style inbound GTM workflows. It takes basic lead inputs, enriches them with public APIs and agentic research, scores each lead, explains the score, generates sales insights, and drafts personalized outreach for SDRs.

The project was built for a GTM Engineer practical assignment: automate or augment the inbound lead process using public APIs, scoring assumptions, and outreach generation.

## What It Does

- Accepts lead inputs: name, email, company, property address, city, state, and country.
- Enriches leads with public and web data sources.
- Runs a multi-agent research pipeline for identity, company, market, property, values, scoring, and outreach.
- Scores each lead and assigns a tier.
- Explains the reasoning behind qualification and prioritization.
- Generates sales insights, recommended next action, talking points, and draft outreach email.
- Streams live pipeline events to the frontend using Server-Sent Events.
- Supports single lead submission, batch CSV upload, queued processing, and scheduler controls.

## Tech Stack

| Layer | Choice |
| --- | --- |
| Frontend | React, Vite |
| Styling | Tailwind CSS |
| Frontend data | React Query |
| Backend | FastAPI |
| Database | PostgreSQL via SQLAlchemy async |
| Task flow | Background worker queue, scheduler hooks |
| Streaming | Server-Sent Events |
| AI | Claude Sonnet |
| HTTP client | httpx |
| Public APIs | Census, FRED, HUD, News, SEC EDGAR, job/news/web research tools |

## Project Structure

```text
.
├── backend/
│   ├── agents/          # Agentic pipeline nodes
│   ├── api/             # FastAPI routes and API errors
│   ├── db/              # SQLAlchemy models and database setup
│   ├── scheduler/       # Scheduler controls
│   ├── services/        # External API and pipeline services
│   ├── tests/           # API contract tests
│   └── main.py          # FastAPI app entrypoint
├── frontend/
│   ├── src/
│   │   ├── components/  # Dashboard and pipeline UI components
│   │   ├── lib/         # API client and helpers
│   │   └── pages/       # App pages
│   └── package.json
├── data/                # Sample lead input data
├── docker/              # Docker compose and backend Dockerfile
└── docs/                # Supporting project plan material
```

## Core Workflow

1. An SDR submits a lead or uploads a CSV.
2. The backend creates lead records immediately.
3. A background worker runs the lead through the pipeline.
4. Agents emit live reasoning and status events over SSE.
5. Agent outputs are saved to the database.
6. The dashboard updates with score, tier, insights, email draft, and recommended action.

## Sample Outputs

- [First batch enriched lead outputs](docs/first_batch_outputs.csv) - CSV export from a 16-lead batch run, including lead status, score, tier, recommended action, email draft, and serialized agent outputs.

## API Overview

Key backend routes:

- `POST /api/leads` - create a lead and enqueue pipeline work.
- `GET /api/leads` - list recent leads with status and enrichment summary.
- `GET /api/leads/{id}` - fetch full lead and all enrichment outputs.
- `GET /api/leads/{id}/stream` - stream live pipeline events.
- `POST /api/leads/batch` - upload a CSV batch.
- `POST /api/leads/{id}/regenerate-email` - regenerate outreach from saved enrichment.
- `GET /api/scheduler` - read scheduler status.
- `POST /api/scheduler/toggle` - enable or disable scheduler behavior.
- `POST /api/scheduler/run-now` - process queued leads.
- `POST /api/scheduler/schedule` - update scheduler timing.

## Local Setup

### Backend

```bash
cd backend
python3 -m venv ../leadOSenv
source ../leadOSenv/bin/activate
pip install -r requirements.txt
```

Create `backend/.env` from `.env.example` and fill in the required API keys and database URL.

Run the backend:

```bash
cd backend
../leadOSenv/bin/uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend expects the backend API to be running locally.

## Verification

Backend tests:

```bash
cd backend
../leadOSenv/bin/pytest tests -q
```

Frontend build:

```bash
npm --prefix frontend run build
```

## Notes

This is a production-minded MVP. It includes a DB-backed queue, live SSE pipeline updates, scheduler controls, and persisted enrichment outputs. For a production deployment, the next hardening steps would be formal Alembic migrations, auth, distributed queue workers, richer observability, and stricter retry/cancellation behavior.
