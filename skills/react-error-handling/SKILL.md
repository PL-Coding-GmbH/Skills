---
name: react-error-handling
description: |
  Error handling for React SPAs with a REST backend and TanStack Query/Router - the DataError class with a kind discriminant (string literal union, no enum), mapping HTTP statuses, network failures, timeouts and Zod parse failures to DataError in the HTTP client, letting AbortError through, API error codes, turning errors into translated messages with useErrorMessage, route error components with retry, notFound() for missing resources, mutation errors in screen state, validation with Zod instead of a Result type, typed failure unions for domain logic, and error reporting. Use this skill whenever defining or handling errors, mapping an HTTP status, showing an error message, adding an error page or retry, handling 404/409/401 cases, writing validation, or deciding whether to throw or return. Trigger on phrases like "error handling", "DataError", "error kind", "catch", "throw", "try/catch", "error message", "show an error", "retry", "error boundary", "errorComponent", "notFound", "404", "409", "conflict", "status code", "API error code", "problem details", "validation error", "safeParse", "Result type", or "error reporting".
---

# React Error Handling

## Principles

- **The data layer throws, it doesn't return errors.** TanStack Query needs a thrown error to mark a query or mutation as failed, so a `Result` type would have to be unwrapped in every query function.
- **One error type leaves the data layer: `DataError`.** The HTTP client converts every failure into a `DataError` with a `kind`. Components never look at HTTP statuses, `fetch` exceptions or Zod issues.
- **Expected failures vs bugs.** A `DataError` is an expected failure the UI handles. Anything else (a `TypeError` in a mapper, a failed `JSON.parse` of our own data) is a bug. It goes to the nearest error boundary and gets reported.
- **Users see translated messages, never `error.message`.**
- **Validation is Zod, not a custom `Result`.** `safeParse` already returns a success/failure union, and React Hook Form consumes Zod schemas directly.

---

## DataError (`core/api`)

```ts
// src/core/api/DataError.ts
export type DataErrorKind =
  | 'network'
  | 'timeout'
  | 'badRequest'
  | 'unauthorized'
  | 'forbidden'
  | 'notFound'
  | 'conflict'
  | 'payloadTooLarge'
  | 'tooManyRequests'
  | 'server'
  | 'serialization'
  | 'unknown'

type DataErrorOptions = {
  status?: number
  code?: string
  cause?: unknown
}

export class DataError extends Error {
  readonly kind: DataErrorKind
  readonly status: number | undefined
  /** Stable error code from the API body, if the API sends one. */
  readonly code: string | undefined

  constructor(kind: DataErrorKind, options: DataErrorOptions = {}) {
    super(options.code ? `${kind} (${options.code})` : kind, { cause: options.cause })
    this.name = 'DataError'
    this.kind = kind
    this.status = options.status
    this.code = options.code
  }
}

export function isDataError(error: unknown): error is DataError {
  return error instanceof DataError
}
```

- `kind` is a string literal union, not an `enum`. A `switch` over it is checked for exhaustiveness like a Kotlin `when` over an enum.
- No constructor parameter properties (`constructor(readonly kind ...)`). They aren't erasable syntax and fail with `erasableSyntaxOnly`.
- Always pass the original error as `cause`. It shows up in the console and in error reports.

### Mapping responses

```ts
// src/core/api/dataErrorFromResponse.ts
// ProblemDetail (RFC 9457) with the backend's `code` extension.
const errorBodySchema = z.object({ code: z.string().optional() })

export async function dataErrorFromResponse(response: Response): Promise<DataError> {
  const body = errorBodySchema.safeParse(await response.json().catch(() => null))
  return new DataError(kindForStatus(response.status), {
    status: response.status,
    code: body.success ? body.data.code : undefined,
  })
}

function kindForStatus(status: number): DataErrorKind {
  switch (status) {
    case 400:
    case 422:
      return 'badRequest'
    case 401:
      return 'unauthorized'
    case 403:
      return 'forbidden'
    case 404:
      return 'notFound'
    case 408:
      return 'timeout'
    case 409:
      return 'conflict'
    case 413:
      return 'payloadTooLarge'
    case 429:
      return 'tooManyRequests'
  }
  return status >= 500 ? 'server' : 'unknown'
}
```

The backend returns every error as ProblemDetail with a stable `code` property. Each operation in the OpenAPI spec lists the codes it can return. The schema stays this small on purpose: the HTTP client only needs `code`, and a malformed error body must never hide the status.

- Map only codes that the spec lists for that operation. Never invent a code.
- A `429` (code `RATE_LIMIT_EXCEEDED`) comes with a `Retry-After` header. When a screen needs it, read the header in `dataErrorFromResponse` and store it on the `DataError`.

### What the HTTP client converts

| Failure | Becomes |
|---|---|
| `fetch` rejects (offline, DNS, CORS) | `network` |
| `AbortSignal.timeout(...)` fires (`TimeoutError`) | `timeout` |
| Non-2xx response | the kind for its status, with `status` and `code` |
| Response body isn't JSON, or fails the Zod schema | `serialization` |
| `AbortError` (query cancelled) | **not converted**, rethrown as is |

The `AbortError` exception is the web version of rethrowing `CancellationException`. TanStack Query cancels queries through the signal and expects to see its own abort.

---

## Turning Errors into Messages

```ts
// src/core/i18n/useErrorMessage.ts
export function useErrorMessage() {
  const { t } = useTranslation('common')

  return (error: unknown, messagesByCode: Partial<Record<string, string>> = {}): string => {
    if (!isDataError(error)) return t('errors.unknown')
    const byCode = error.code === undefined ? undefined : messagesByCode[error.code]
    if (byCode) return byCode
    switch (error.kind) {
      case 'network':
        return t('errors.network')
      case 'timeout':
        return t('errors.timeout')
      case 'notFound':
        return t('errors.notFound')
      case 'forbidden':
        return t('errors.forbidden')
      case 'conflict':
        return t('errors.conflict')
      case 'tooManyRequests':
        return t('errors.tooManyRequests')
      case 'payloadTooLarge':
        return t('errors.payloadTooLarge')
      case 'server':
        return t('errors.server')
      case 'badRequest':
      case 'unauthorized':
      case 'serialization':
      case 'unknown':
        return t('errors.unknown')
    }
  }
}
```

Feature-specific messages for known API error codes are passed in by the feature:

```tsx
const errorMessage = useErrorMessage()
const { t } = useTranslation('notes')

errorMessage(state.saveError, { NOTE_TITLE_TAKEN: t('errors.titleTaken') })
```

- The hook takes `unknown`, so it works with any caught value.
- `DataError` is not registered as TanStack Query's global `defaultError` type. That would claim every query error is a `DataError`, but a bug in a mapper throws a plain `TypeError`. State types use `Error | null`, and code narrows with `isDataError` when it needs the `kind`.
- To react to a specific case in logic (not just show text), narrow first: `isDataError(error) && error.kind === 'conflict'`.

---

## Where Errors Are Handled

| Error source | Handled by |
|---|---|
| Route loader / `useSuspenseQuery` on the page's main data | the route's `errorComponent` (full-page error with retry) |
| Missing resource on a detail page | `throw notFound()` in the loader, rendered by `notFoundComponent` |
| `useQuery` for secondary data | inline in that section, with a retry button |
| Mutation | the mutation's `error` in screen state, shown next to the action or as a toast |
| Background refetch of data already on screen | a global toast from the `QueryCache` `onError` (see **react-server-state**) |
| `unauthorized` after the refresh failed | not shown as an error. The session ends and the user goes to login (see **react-security**) |
| Bug during render | the nearest route `errorComponent`, plus error reporting |

### Route error component

```tsx
// src/app/PageError.tsx
export function PageError({ error }: ErrorComponentProps) {
  const router = useRouter()
  const { t } = useTranslation()
  const errorMessage = useErrorMessage()
  const queryErrorResetBoundary = useQueryErrorResetBoundary()

  useEffect(() => {
    queryErrorResetBoundary.reset()
  }, [queryErrorResetBoundary])

  return (
    <main className="px-4 py-8">
      <h1 className="type-page-title">{t('errors.title')}</h1>
      <p>{errorMessage(error)}</p>
      <Button onClick={() => router.invalidate()}>{t('errors.retry')}</Button>
    </main>
  )
}
```

Resetting the query error boundary lets `useSuspenseQuery` fetch again when the route reloads after "retry".

### Not found from a loader

```ts
loader: ({ context, params }) =>
  context.queryClient.ensureQueryData(noteQueryOptions(params.noteId)).catch(notFoundOn404),
```

```ts
// src/app/notFoundOn404.ts
export function notFoundOn404(error: unknown): never {
  if (isDataError(error) && error.kind === 'notFound') throw notFound()
  throw error
}
```

---

## Validation and Domain Failures

- **Input validation** is a Zod schema: `safeParse` for plain values, `zodResolver` for forms (see **react-presentation-mvi**).
- **Domain logic with a typed failure** returns a discriminated union written for that case. There is no generic `Result` type:

```ts
export type MoveNoteResult =
  | { ok: true; notes: Note[] }
  | { ok: false; reason: 'sameFolder' | 'folderFull' }
```

- Only one failure per result. Callers `switch` on `reason`.

---

## Reporting

- Report unexpected errors (anything that isn't a `DataError`, plus `DataError` of kind `serialization` and `server`) from two places: the route error component and the `QueryCache`/`MutationCache` `onError`. Don't add `try/catch` blocks just to report.
- Never put tokens, request bodies or personal data into error reports or `console` output.

---

## Anti-patterns

| Anti-pattern | Instead |
|---|---|
| `catch (e) {}` or catching only to log | let it propagate to the boundary that handles it |
| Showing `error.message` | `useErrorMessage()(error)` |
| Components checking `error.status === 404` | the HTTP client sets `kind`, components check `kind` |
| `throw 'something went wrong'` or throwing plain objects | throw `Error` subclasses |
| Converting `AbortError` into `network` | rethrow it |
| A generic `Result<T, E>` type for everything | thrown `DataError` in the data layer, Zod for validation, small unions for domain logic |
| `enum DataErrorKind` | string literal union |
| Copying `mutation.error` into reducer state | read it from the mutation |

---

## Checklist: Handling a New Failure Case

- [ ] The HTTP client produces the right `kind` for it (and `code`, if the API sends one)
- [ ] There is a translated message for the kind, or for the feature's error code
- [ ] It is handled at the right level: route error component, inline section, mutation state, or toast
- [ ] A missing resource on a detail page renders not-found, not an error page
- [ ] A test covers the failure, with MSW returning that status (see **react-integration-testing**)
