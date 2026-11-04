# Interview checklists

Use these to find what the user didn't mention. Every question here exists because its answer changes the graph. Skip anything already answered by the vision, the repo, or `INTERVIEW.md`.

## Area discovery

Ask about each one the vision leaves open:

| Capability | Why it matters for the graph |
|---|---|
| Which client platforms (Android, iOS, web, desktop) | One set of client chunks per codebase |
| Code sharing across clients (KMP, Flutter, RN, shared web) | Adds a shared-module area, shrinks per-platform chunks |
| Backend: custom server, managed backend (BaaS), or none | Custom server adds a full backend area; BaaS mostly adds integration and rules chunks |
| Real-time features (chat, live updates, presence) | Real-time client and server foundations |
| Offline support | Local persistence and sync foundation per client |
| Authentication method (email/password, social, SSO, magic link) | Size of auth chunks; third-party provider integration |
| Payments or subscriptions | Payment integration chunks per platform plus backend webhooks |
| Push notifications | Push foundation per client and a backend sender |
| Media upload/processing (images, video, files) | Storage infrastructure, processing jobs, upload clients |
| Background jobs / scheduled work | Job-runner foundation on the backend |
| Search | Search infrastructure chunk |
| Admin panel / back-office | A separate client area |
| Third-party integrations (maps, AI APIs, CRM, email) | One integration chunk each, if non-trivial |
| Analytics / observability | Usually folds into scaffolding; standalone if a full pipeline |
| Localization | Usually folds into design system or scaffolding |
| Hosting target and environments (staging, prod) | Shape of the infrastructure chunk |

## Foundation checklist (ask proactively, per codebase)

For each, confirm it's needed and whether it stands alone or folds into another chunk.

**Every codebase**
- Scaffolding and base architecture (build system, module structure, conventions)
- CI (usually folds into scaffolding) and CD (stand-alone only if substantial)
- Logging, error reporting, observability

**Clients**
- Design system and theme (tokens, base components)
- Navigation shell (often folds into scaffolding)
- Networking/HTTP client and error model
- Fake API layer implementing the contract (required whenever a backend is built in this plan)
- Real-time connection client (if real-time is in scope)
- Local persistence / offline sync (if offline is in scope)
- Auth client (session handling, token storage, login flows)
- Push notification handling (if in scope)

**Backend**
- Database setup and migration tooling
- Auth mechanism
- Real-time server infrastructure (if in scope)
- Background job runner (if in scope)
- File/media storage integration (if in scope)

**Cross-cutting**
- API contract
- Infrastructure and deployment (environments, provisioning, secrets)

## Signs you've gone too deep

Stop and park it as an open question when you're asking about:
- request/response payloads, endpoint lists, schema fields
- screen layouts, exact UX flows, copy
- library choices within an already-chosen stack
- error-handling edge cases, retry policies, timeouts
- performance numbers that don't change which chunks exist
