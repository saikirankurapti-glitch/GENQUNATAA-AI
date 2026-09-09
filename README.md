# GenQuantaa AI

AI interview and coding copilot workspace.

## Current implementation
- FastAPI backend with session and Gemini chat APIs
- Next.js web workspace with Dashboard, Live Copilot, Coding, Documents and Mock Interview navigation
- Resume/context-ready workspace foundation
- Backend smoke tests and GitHub Actions CI

## Run locally

### Backend
```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Set `GEMINI_API_KEY` in `.env` for live answers.

### Web
```bash
cd apps/web
npm install
npm run dev
```

The web app defaults to `http://localhost:8000` for the backend and can be changed with `NEXT_PUBLIC_API_URL`.

This repository contains an original implementation. It does not copy proprietary source code or implementation details from third-party products.
