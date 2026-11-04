---
name: react-data-layer
description: |
  Data layer for React SPAs that talk to a REST API described by an OpenAPI spec - a small fetch-based HTTP client in core/api, a same-origin API base path from validated environment config, Zod schemas and DTO types generated from the committed OpenAPI spec, feature API modules of plain async functions, mappers from DTOs to domain types, request bodies, path and query encoding, file uploads, AbortSignal support, and where each piece lives. Use this skill whenever calling an endpoint, adding an API function, syncing or regenerating the API contract, using a generated DTO schema, mapping API data to domain types, defining domain types, configuring the API base path or other environment variables, or touching the HTTP client. Trigger on phrases like "call the API", "add an endpoint", "API function", "fetch", "HTTP client", "request", "response", "DTO", "Zod schema", "OpenAPI", "spec", "api:sync", "api:generate", "generated", "parse the response", "mapper", "domain type", "base URL", "environment variable", "import.meta.env", "VITE_", "query parameters", "upload a file", "FormData", or "AbortSignal".
---

# React Data Layer

## Principles

- **Plain functions, no repository layer.** A feature's `api/` folder exports async functions like `getNote(noteId)`. Query options call them directly (see **react-server-state**). Tests fake the network with MSW instead of swapping implementations (see **react-integration-testing**).
- **The OpenAPI spec is the contract.** DTO schemas and types are generated from it, never written by hand. A contract change shows up as a diff in the spec and as compile errors in the mappers.
- **Every response is validated.** TypeScript types don't exist at runtime. A response that hasn't been parsed with a Zod schema is `unknown`, and nothing outside the HTTP client may treat it as anything else.
- **DTOs stay in the data layer.** API functions return domain types from `types.ts`. Only `api/` folders and `core/api` import generated code. A change in the API's JSON shape is absorbed in one mapper, not across the UI.
- **Failures are thrown as `DataError`.** The HTTP client converts every failure into a `DataError`. Nothing else is thrown out of the data layer (see **react-error-handling**).
- **`fetch`, not axios.** The HTTP client is a few dozen lines in `core/api`.

---

## Layout

```
api/
  openapi.json        # committed copy of the backend's spec (npm run api:sync)
src/core/api/
  generated/          # generated Zod schemas and DTO types (npm run api:generate). Never edited
  config.ts           # validated environment config (API base path)
  httpClient.ts       # requestJson / requestVoid, auth header, error conversion
  DataError.ts        # see react-error-handling
  queryClient.ts      # see react-server-state
src/features/notes/
  types.ts            # Note, NoteFilter (domain types)
  api/
    noteMapper.ts     # DTO -> domain, domain -> request body
    notesApi.ts       # getNotes, getNote, createNote, ...
    notesQueries.ts   # query keys, queryOptions, mutation hooks (react-server-state)
```

---

## The API Contract

The backend generates its OpenAPI spec from its controllers and DTOs and commits it as a snapshot in `app/src/test/resources/openapi/` of the backend repo at `/Users/philipplackner/IdeaProjects/cardigan`.

| Step | Command | Result |
|---|---|---|
| Copy the backend's snapshot into this repo | `npm run api:sync` | `api/openapi.json` changes |
| Generate schemas and types from the copy | `npm run api:generate` | `src/core/api/generated/` changes |
| Fix what no longer compiles | `npm run typecheck` | mappers and API functions follow the new contract |

- `api/openapi.json` and the generated folder are committed. The spec change and the regenerated code go into one commit.
- **Never edit generated files.** They are excluded from oxlint and Prettier. A wrong schema is fixed in the backend, synced and regenerated.
- **Never invent an endpoint, field, enum value or error code.** If the spec doesn't contain what a screen needs, the backend doesn't offer it yet. Stop and say what's missing.
- The generator is configured so that every component schema `X` in the spec becomes a Zod schema `xSchema` and a type `X`: `NoteDto` → `noteDtoSchema` + `NoteDto`, `CreateNoteRequest` → `createNoteRequestSchema` + `CreateNoteRequest`.
- Generated object schemas strip unknown keys (`z.object`, not `z.strictObject`), so a new field in a response doesn't break the app.
- Kotlin nullability on the backend is the contract: a non-null property is required, a nullable one is `.nullable()`. The generated schema reflects that exactly.
- UUIDs are strings with `format: uuid`. Instants are strings with `format: date-time` in UTC. Both stay strings in DTOs and are turned into domain values in the mapper.

---

## Environment Config

Vite exposes variables prefixed with `VITE_` through `import.meta.env`. They are compiled into the bundle, so every user can read them. Never put a secret there (see **react-security**).

The app and the API share one origin (see **react-routing**), so the API base is a path, `/api/v1`. Tests use an absolute fake origin so MSW handlers match exactly.

```ts
// src/vite-env.d.ts
/// <reference types="vite/client" />

// Module augmentation only works with an interface.
// oxlint-disable-next-line typescript/consistent-type-definitions
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
}
```

```ts
// src/core/api/config.ts
const configSchema = z.object({
  VITE_API_BASE_URL: z.union([z.string().regex(/^\/[^/]/), z.url()]),
})

const env = configSchema.parse(import.meta.env)

export const apiBaseUrl = env.VITE_API_BASE_URL.replace(/\/$/, '')
```

| File | `VITE_API_BASE_URL` |
|---|---|
| `.env` (committed) | `/api/v1` |
| `.env.test` (committed) | `http://api.test/api/v1` |

- Parsing at startup fails fast with a clear error when a variable is missing, instead of requests going to `undefined/notes`.
- A path must start with a single `/`. `//host` would be a protocol-relative URL to another site.
- Local overrides go in `.env.local` (git-ignored).

---

## HTTP Client (`core/api`)

```ts
// src/core/api/httpClient.ts
type QueryParams = Record<string, string | number | boolean | null | undefined>

type RequestOptions = {
  query?: QueryParams
  body?: unknown
  signal?: AbortSignal
}

export function apiUrl(path: string, query?: QueryParams): string {
  // The base is a same-origin path in the app and an absolute URL in tests.
  const url = new URL(apiBaseUrl + path, window.location.origin)
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value != null) url.searchParams.set(key, String(value))
  }
  return url.toString()
}

export async function requestJson<T>(
  method: string,
  path: string,
  schema: z.ZodType<T>,
  options: RequestOptions = {},
): Promise<T> {
  const response = await send(method, path, options)
  const json: unknown = await response.json().catch((cause: unknown) => {
    throw new DataError('serialization', { cause })
  })
  const result = schema.safeParse(json)
  if (!result.success) {
    throw new DataError('serialization', { cause: result.error })
  }
  return result.data
}

export async function requestVoid(
  method: string,
  path: string,
  options: RequestOptions = {},
): Promise<void> {
  await send(method, path, options)
}

async function send(method: string, path: string, options: RequestOptions): Promise<Response> {
  const isFormData = options.body instanceof FormData
  let response: Response
  try {
    response = await fetchWithAuth(apiUrl(path, options.query), {
      method,
      signal: options.signal,
      headers: isFormData || options.body === undefined ? {} : { 'Content-Type': 'application/json' },
      body: isFormData ? options.body : options.body === undefined ? undefined : JSON.stringify(options.body),
    })
  } catch (cause) {
    if (isAbortError(cause)) throw cause
    throw new DataError(isTimeoutError(cause) ? 'timeout' : 'network', { cause })
  }
  if (!response.ok) throw await dataErrorFromResponse(response)
  return response
}
```

- `fetchWithAuth` adds the access token and handles a `401` with one refresh and one retry. Its details depend on the backend (see **react-security**).
- `dataErrorFromResponse` maps the status (and an error code in the body, if the API sends one) to a `DataError` (see **react-error-handling**).
- An aborted request rethrows the original `AbortError`. TanStack Query aborts requests when a query is cancelled and handles that error itself.
- For `FormData`, don't set `Content-Type`. The browser sets it with the multipart boundary.
- Nothing else in the app calls `fetch` for the backend API.

---

## Using Generated Schemas

```ts
// src/core/api/generated/ (generated from api/openapi.json)
export const noteDtoSchema = z.object({
  id: z.uuid(),
  title: z.string(),
  body: z.string(),
  color: noteColorDtoSchema,
  updatedAt: z.iso.datetime({ offset: true }),
  archivedAt: z.iso.datetime({ offset: true }).nullable(),
})
export type NoteDto = z.infer<typeof noteDtoSchema>

export type CreateNoteRequest = {
  title: string
  body: string
}
```

- **Response schemas** are passed to `requestJson`. A list endpoint uses `z.array(noteDtoSchema)` in the API function.
- **Request bodies** use the generated request types. They're built by our own code from typed values, so they aren't validated at runtime.
- **Enums from the API** are strict in the generated schema, so an unknown value fails as `serialization`. The backend treats enum changes as contract changes. If a field must survive an unknown value, extend the schema in the feature's API function, for example `noteDtoSchema.extend({ color: noteColorDtoSchema.catch('BLUE') })`, and say why in a short comment.
- **Never copy a generated schema** into a feature to change it. Extend it where it's used, or fix the spec.

---

## Domain Types and Mappers

```ts
// src/features/notes/types.ts
export type NoteColor = 'red' | 'green' | 'blue'

export type Note = {
  id: string
  title: string
  body: string
  color: NoteColor
  updatedAt: Date
  archivedAt: Date | null
}

export type NoteFilter = 'all' | 'archived'
```

```ts
// src/features/notes/api/noteMapper.ts
export function toNote(dto: NoteDto): Note {
  return {
    id: dto.id,
    title: dto.title,
    body: dto.body,
    color: dto.color,
    updatedAt: new Date(dto.updatedAt),
    archivedAt: dto.archivedAt === null ? null : new Date(dto.archivedAt),
  }
}

export function toCreateNoteRequest(values: NoteFormValues): CreateNoteRequest {
  return { title: values.title.trim(), body: values.body }
}
```

- Domain types use the forms the UI wants: `Date` instead of ISO strings, discriminated unions instead of several optional fields, one name per concept even if the API uses another.
- Mappers are plain exported functions named `to<Target>`. They are pure and unit-tested (see **react-unit-testing**).
- Domain types never import from `api/`.
- Keep the mapper even when the shapes are identical today. It's the place a future API change gets absorbed.

---

## API Functions

```ts
// src/features/notes/api/notesApi.ts
export async function getNotes(filter: NoteFilter, signal?: AbortSignal): Promise<Note[]> {
  const dtos = await requestJson('GET', '/notes', z.array(noteDtoSchema), {
    query: { archived: filter === 'archived' },
    signal,
  })
  return dtos.map(toNote)
}

export async function getNote(noteId: string, signal?: AbortSignal): Promise<Note> {
  const dto = await requestJson('GET', `/notes/${encodeURIComponent(noteId)}`, noteDtoSchema, { signal })
  return toNote(dto)
}

export async function createNote(values: NoteFormValues): Promise<Note> {
  const dto = await requestJson('POST', '/notes', noteDtoSchema, {
    body: toCreateNoteRequest(values),
  })
  return toNote(dto)
}

export async function deleteNote(noteId: string): Promise<void> {
  await requestVoid('DELETE', `/notes/${encodeURIComponent(noteId)}`)
}
```

- One function per endpoint, named after what it does: `getX`, `getXs`, `createX`, `updateX`, `deleteX`, or a domain verb (`archiveNote`).
- **Every value interpolated into a path goes through `encodeURIComponent`.** An ID with a `/` or `?` must not change which endpoint is called.
- Query parameters go through `query`, never string-built.
- Read functions accept an optional `AbortSignal` and pass it on. Query functions forward the signal TanStack Query provides.
- API functions take and return domain types or form values, never DTOs.

---

## Naming Conventions

| Thing | Convention | Example |
|---|---|---|
| Response schema (generated) | `<model>DtoSchema` | `noteDtoSchema` |
| Response type (generated) | `<Model>Dto` | `NoteDto` |
| Request body type (generated) | `<Verb><Model>Request` | `CreateNoteRequest` |
| Mapper | `to<Target>` | `toNote`, `toCreateNoteRequest` |
| API module | `<feature>Api.ts` | `notesApi.ts` |
| API function | verb + model | `getNote`, `createNote`, `archiveNote` |
| Domain type | plain name, no suffix | `Note`, `NoteFilter` |

---

## Checklist: Adding an Endpoint

- [ ] The endpoint exists in the backend's spec. If not, stop and say what's missing
- [ ] `npm run api:sync` and `npm run api:generate` run, spec and generated code committed together
- [ ] Domain type in the feature's `types.ts` (or reuse an existing one)
- [ ] Mapper in `api/<model>Mapper.ts` from the generated DTO type, with unit tests for null values and edge cases
- [ ] API function in `api/<feature>Api.ts` using `requestJson`/`requestVoid`, path params encoded, signal forwarded
- [ ] Query options or mutation in `api/<feature>Queries.ts` (see **react-server-state**)
- [ ] MSW handler for the endpoint in the feature's tests (see **react-integration-testing**)
