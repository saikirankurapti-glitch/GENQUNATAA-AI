# GenQuantaa AI

GenQuantaa AI is a company-owned real-time AI interview and meeting copilot.

## Development stack

- Web: Next.js + TypeScript + Tailwind CSS
- Backend: FastAPI + Python
- Database: PostgreSQL + pgvector
- Cache/realtime state: Redis
- Desktop: Electron
- AI: Google Gemini API / Gemini Live API

## Repository structure

```text
apps/
  web/          Web dashboard (planned)
  desktop/      Electron client (planned)
backend/        FastAPI services
  app/
database/     SQL and migration assets
prompts/       Versioned AI prompts
packages/      Shared types/config
infrastructure/ Docker/Azure assets

docs/          Architecture and product documentation
```

## Local development

1. Copy `.env.example` to `.env`.
2. Add your Gemini API key locally.
3. Start PostgreSQL and Redis with `docker compose up -d`.
4. Start the API from `backend/`.
5. Start the web and desktop applications as they are added.

## Security

Never commit API keys, tokens, certificates, or production secrets. `.env` files are ignored by Git.

## Product direction

The product will implement original code and architecture inspired by the public capabilities of modern AI interview copilots. It will not copy proprietary source code, assets, or protected implementation details from third-party products.
