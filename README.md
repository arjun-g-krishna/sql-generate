
# SQL Generate

**SQL Generate** allows users to query databases in plain English. Converts natural language questions into executable SQL queries using LLMs, with a fast FastAPI backend and a Next.js frontend.


<img width="1388" height="720" alt="ezgif-83326aa33588f638" src="https://github.com/user-attachments/assets/2862594e-c4d2-4e90-b5b0-ec84ff770506" />

### Key Features
- **Natural Language to SQL:** Write complex queries in plain English.
- **Dynamic Schema Introspection:** Automatically reflect and onboard your live database schemas using SQLAlchemy.
- **Schema-Aware Context Retrieval:** Uses cosine similarity to retrieve only the most relevant tables and schema descriptions.
- **Frontend:** A Next.js frontend.

### Tech Stack
- **Frontend:** Next.js (React), Tailwind CSS, Framer Motion, Lucide Icons.
- **Backend:** FastAPI, Python 3.11, SQLAlchemy.
- **LLM Integrations:** Support for Claude, GPT-4o, and local models via Ollama.

---

## Folder Structure

```
sql-generate/
├── backend/          # Python/FastAPI backend logic and LLM orchestration
└── frontend/         # Next.js UI application
```

---

## Getting Started

### Prerequisites
- **Node.js** (v18+)
- **Python** (v3.9+)
- A **Live Database** (e.g., PostgreSQL) for dynamic introspection.
- **API Keys** for the LLM of your choice (Anthropic/OpenAI) or Ollama installed locally.

### 1. Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment (recommended):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Environment Configuration:
   Copy `.env.example` to `.env` and fill in your keys:
   ```bash
   cp .env.example .env
   ```
   *Make sure to configure `DATABASE_URL` for live schema introspection and your chosen LLM API keys.*
5. Run the FastAPI server:
   ```bash
   uvicorn app.main:app --reload
   ```
   The backend will be available at `http://localhost:8000`.

### 2. Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install Node.js dependencies:
   ```bash
   npm install
   ```
3. Start the Next.js development server:
   ```bash
   npm run dev
   ```
4. Access the UI: Open `http://localhost:3000` in your browser.

---

## API Endpoints Overview

If you want to interact with the backend directly without the UI:

- **Generate SQL:** 
  `POST /query`
  ```bash
  curl -X POST http://localhost:8000/query \
    -H "Content-Type: application/json" \
    -d '{"question": "Who are the top 5 customers by total revenue this month?"}'
  ```

- **View Current Schema:**
  `GET /schema`
  ```bash
  curl http://localhost:8000/schema
  ```

---

## Docker Deployment

You can deploy the backend via Docker:
```bash
cd backend
docker build -t sql-generate-backend .
docker run -p 8000:8000 --env-file .env sql-generate-backend
```

---

## Notes

Ensure strict API rate limiting, audit logging, and never run generated SQL on write-nodes. AI can make mistakes.
