---
name: react-integration-testing
description: |
  Component, integration and end-to-end testing for React SPAs - Vitest with jsdom, React Testing Library queries by role and label, user-event, a renderWithProviders helper (fresh QueryClient, i18n, memory router), Screen tests with props only, Root and route tests that run the real API functions and HTTP client against MSW handlers, asserting requests and error states, slow and out-of-order responses, and Playwright E2E tests in e2e/ that run against the local backend and are not a merge gate. Use this skill whenever writing or reviewing a test that renders a component, uses MSW, tests a page or route, tests a form submission, tests the HTTP client or an API function, or writes a Playwright test. Trigger on phrases like "component test", "integration test", "test the screen", "test the page", "test the form", "Testing Library", "render", "screen.getByRole", "findByRole", "userEvent", "MSW", "mock the API", "http.get", "HttpResponse", "setupServer", "renderWithProviders", "renderAppAt", "E2E", "end-to-end", "Playwright", or "e2e test".
---

# React Integration and E2E Testing

## Test Types

| Type | What runs for real | What is faked | Where |
|---|---|---|---|
| **Screen test** | Screen + its child components + i18n | everything else: state and `onAction` are props | next to the Screen, `NoteListScreen.test.tsx` |
| **Feature test** | Root + view-model hook + queries + API functions + HTTP client + mappers | the network (MSW) | next to the Root or in the feature's `components/` |
| **Route test** | the whole router at a URL, loaders, guards, not-found, plus a feature | the network (MSW) | `src/app/*.test.tsx` |
| **API test** | HTTP client or an API function | the network (MSW) | next to the module |
| **E2E** | the built app and the local backend in a browser | nothing | `e2e/` |

Like Ktor `MockEngine` on Android, MSW replaces only the network. The HTTP client, the Zod schemas, the mappers and TanStack Query all run for real. There are no fake repositories and no `vi.mock` of project modules.

The adversarial method from **react-unit-testing** applies here too: enumerate how the screen could break before writing tests. Typical component-level break vectors: empty, one item and many items; very long text; every error kind the screen can get; double submit; a slow response; keyboard-only use.

---

## Setup

```ts
// src/testSetup.ts
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  cleanup()
  server.resetHandlers()
})
afterAll(() => server.close())
```

```ts
// src/core/testing/mswServer.ts
export const server = setupServer()
```

- **`onUnhandledRequest: 'error'`** fails a test that makes a request nobody declared. An unexpected request is a bug, or a missing handler.
- The server starts with **no default handlers**. Each test declares exactly the endpoints it uses with `server.use(...)`.
- `.env.test` sets `VITE_API_BASE_URL` to a fixed fake origin (`http://api.test`). Handlers build URLs with `apiUrl(...)` from the HTTP client, so they match exactly.

### Render helper

```tsx
// src/core/testing/renderWithProviders.tsx
type Options = {
  queryClient?: QueryClient
}

/** Renders [ui] inside a memory router with a fresh QueryClient and English i18n. */
export async function renderWithProviders(ui: ReactNode, { queryClient = createTestQueryClient() }: Options = {}) {
  const rootRoute = createRootRoute({ component: () => <>{ui}</> })
  const router = createRouter({ routeTree: rootRoute, history: createMemoryHistory() })
  await router.load()
  const user = userEvent.setup()
  const result = render(
    <I18nextProvider i18n={createTestI18n()}>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </I18nextProvider>,
  )
  return { user, queryClient, router, ...result }
}
```

- Components that render `<Link>` need a router. The helper wraps the component in a one-route memory router and loads it before rendering, so the first query can be synchronous.
- `userEvent.setup()` is created before rendering and returned, so each test uses one `user` instance.
- For full routes, use `renderAppAt(path)` (see **react-routing**), which uses the real route tree.

---

## Screen Tests

The Screen gets state and `onAction` as props. No MSW, no QueryClient data.

```tsx
describe('NoteListScreen', () => {
  it('asks for confirmation before deleting', async () => {
    const onAction = vi.fn()
    const { user } = await renderWithProviders(
      <NoteListScreen state={aNoteListState({ notes: [aNote({ id: 'n1', title: 'Groceries' })] })} onAction={onAction} />,
    )

    await user.click(screen.getByRole('button', { name: 'Delete Groceries' }))

    expect(onAction).toHaveBeenCalledWith({ type: 'deleteClick', noteId: 'n1' })
  })

  it('shows the empty state when there are no notes', async () => {
    await renderWithProviders(<NoteListScreen state={aNoteListState({ notes: [] })} onAction={vi.fn()} />)

    expect(screen.getByRole('heading', { name: 'No notes yet' })).toBeInTheDocument()
  })
})
```

- Cover every distinct state the Screen can render: empty, loaded, long content, each error, pending mutation, open dialog. These tests replace previews for Screens.
- Assert the action sent, with its payload. That's the Screen's output.

---

## Feature Tests (Root + MSW)

```tsx
describe('NoteListRoot', () => {
  it('removes a note after the delete is confirmed', async () => {
    let notes = [aNoteDto({ id: 'n1', title: 'Groceries' }), aNoteDto({ id: 'n2', title: 'Ideas' })]
    server.use(
      http.get(apiUrl('/notes'), () => HttpResponse.json(notes)),
      http.delete(apiUrl('/notes/n1'), () => {
        notes = notes.filter((note) => note.id !== 'n1')
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const { user } = await renderWithProviders(
      <NoteListRoot filter="all" query="" onSearchChange={vi.fn()} />,
    )

    await user.click(await screen.findByRole('button', { name: 'Delete Groceries' }))
    await user.click(screen.getByRole('button', { name: 'Delete' }))

    await waitForElementToBeRemoved(() => screen.queryByText('Groceries'))
    expect(screen.getByText('Ideas')).toBeInTheDocument()
  })

  it('shows a conflict message when the note was changed elsewhere', async () => {
    server.use(
      http.get(apiUrl('/notes'), () => HttpResponse.json([aNoteDto({ id: 'n1', title: 'Groceries' })])),
      http.delete(apiUrl('/notes/n1'), () => HttpResponse.json({ code: 'NOTE_CHANGED' }, { status: 409 })),
    )
    // ...
    expect(await screen.findByRole('alert')).toHaveTextContent('This note was changed by someone else.')
  })
})
```

- Handlers return **DTO-shaped JSON** built with DTO fixtures (`aNoteDto`), not domain objects. The real schema and mapper then run, and a schema that rejects realistic data fails the test.
- Keep handler state in the test (`let notes`) when a mutation should change what the next `GET` returns. That's how invalidation is tested.
- A feature can collect handler factories in `src/features/<feature>/testing/<feature>Handlers.ts` once several test files need the same endpoints.

### Asserting what was sent

```ts
let receivedBody: unknown
server.use(
  http.post(apiUrl('/notes'), async ({ request }) => {
    receivedBody = await request.json()
    return HttpResponse.json(aNoteDto({ id: 'new' }), { status: 201 })
  }),
)
// ... fill the form, submit
await waitFor(() => expect(receivedBody).toEqual({ title: 'Groceries', body: '' }))
```

Assert the request body when the mapping from form values to request matters (trimming, defaults, field names). Otherwise assert what the user sees.

### Failure and timing cases

| Case | Handler |
|---|---|
| Error status | `HttpResponse.json({ code: 'X' }, { status: 409 })` |
| Network failure | `HttpResponse.error()` |
| Invalid response shape | `HttpResponse.json({ unexpected: true })` |
| Slow response (pending state, double submit) | `await delay(500)` before returning, or `delay('infinite')` |
| Out-of-order responses (search as you type) | different `delay` per request, assert the latest query's results win |

Double submit: click submit twice quickly and assert the handler ran once.

---

## Queries and Interaction

- **Query by role and accessible name first** (`getByRole('button', { name: 'Save' })`), then by label (`getByLabelText`), then by text. A test that can't find an element by role often found an accessibility bug.
- `data-testid` only when nothing a user can perceive identifies the element.
- **`findBy*` for anything that appears after async work.** `getBy*` for what is already there. `queryBy*` only to assert absence.
- `waitFor` only for assertions that aren't about the DOM appearing (a request body, a callback). Never put a `user` action inside `waitFor`.
- Use `user.click`, `user.type`, `user.keyboard`, never `fireEvent`. `user-event` runs the full event sequence a browser would.
- Test keyboard paths for important flows: `await user.tab()`, `await user.keyboard('{Enter}')`.
- Scope with `within(screen.getByRole('dialog'))` when the same text exists twice.
- Assert on English text from the real translation files. Tests render with `createTestI18n()`, which is isolated from the app instance.
- With fake timers, create the user with `userEvent.setup({ advanceTimers: vi.advanceTimersByTime })`.

---

## API Tests

The HTTP client's error mapping, auth header and refresh behavior are tested against MSW:

```ts
it('turns a non-JSON 502 into a server error', async () => {
  server.use(http.get(apiUrl('/notes'), () => new HttpResponse('Bad gateway', { status: 502 })))

  await expect(getNotes('all')).rejects.toMatchObject({ kind: 'server', status: 502 })
})
```

---

## E2E Tests (Playwright)

E2E tests run the built app in real browsers against the **backend running locally** from `/Users/philipplackner/IdeaProjects/cardigan`. They don't use MSW and don't intercept backend requests. They never run against Supabase or any deployed environment.

```
e2e/
  playwright.config.ts
  fixtures.ts          # test user creation, authenticated page fixture
  notes.spec.ts
```

- **Scope: critical user journeys only.** Signing in, the main create/edit/delete flows, anything involving several features. Edge cases belong in component tests, which are faster and more precise.
- **Not a merge gate.** Run them (`npm run e2e`) only when the user asks, or before a release.
- **Setup:** the local backend runs on `http://localhost:8080`. Playwright's `webServer` builds the app and starts `vite preview`, whose `/api` proxy forwards to that backend (see **react-routing**). If the backend isn't running, the tests fail fast with a clear message instead of timing out.
- **Auth in fixtures** goes through the real flow: register → login, with a unique email per test. There is no email verification step. The refresh cookie then lives in the Playwright browser context like in a real browser.
- **Each test creates its own data** through the API in a fixture (a fresh user, its own notes) and doesn't depend on other tests or on existing data. Tests can then run in parallel.
- **When the backend is built in parallel with the frontend**, a flow gets its E2E test once its endpoints exist in the local backend. Until then, the flow is covered by feature tests with MSW handlers that follow the OpenAPI spec. When the E2E test is added and the real API disagrees with those handlers, sync and regenerate the spec, then fix the handlers.
- Locators like Testing Library: `page.getByRole`, `page.getByLabel`.
- Use web-first assertions (`await expect(locator).toBeVisible()`). Never `page.waitForTimeout`.
- Keep traces and screenshots on failure (`trace: 'retain-on-failure'`).
- Run against Chromium, Firefox and WebKit, plus one mobile viewport.

---

## Anti-patterns

| Anti-pattern | What to do instead |
|---|---|
| `vi.mock` of an API module or a hook | MSW handler, real API function |
| A Context that provides fake repositories | MSW |
| Handlers returning domain objects | DTO-shaped JSON from DTO fixtures |
| Default handlers for every endpoint in the global server | `server.use` per test, `onUnhandledRequest: 'error'` |
| `getByTestId` as the first choice | `getByRole` with an accessible name |
| `fireEvent.click` | `await user.click` |
| `await new Promise((r) => setTimeout(r, 100))` | `findBy*`, `waitFor`, MSW `delay` |
| A QueryClient shared between tests | `createTestQueryClient()` per test |
| Playwright tests against MSW, a mocked backend or a deployed environment | the local backend, or a feature test instead |
| E2E tests for edge cases | component tests |

---

## Checklist: Testing a Feature

- [ ] Screen tests for every distinct state and for the actions each control sends
- [ ] Feature tests with MSW for loading, each mutation, each error kind the user can hit, and double submit where it matters
- [ ] Request bodies asserted where the form-to-request mapping matters
- [ ] A route test that the page loads at its URL (and redirects when it needs a session)
- [ ] Handlers use DTO fixtures and `apiUrl`
- [ ] An E2E test for the feature's main journey once the endpoints exist in the local backend
