---
name: react-security
description: |
  Client-side security for React SPAs that use token-based auth against their own API - access tokens kept in memory only, session state in core/auth, the fetchWithAuth wrapper with one shared in-flight refresh and a single retry on 401, a rotating refresh token in an httpOnly SameSite=Strict cookie that JavaScript never sees, restoring a session on startup through the refresh endpoint, ending a session (clearing the token, the Query cache and user-scoped storage, notifying other tabs), coordinating refreshes across tabs, route guards as UX only, safe post-login redirects, XSS rules (dangerouslySetInnerHTML, user-provided URLs, target=_blank), public VITE_ variables, CSP compatibility, logging, password-manager-friendly forms, and dependency hygiene. Use this skill whenever touching login, logout, registration, tokens, the session, the auth header, 401 handling, protected routes, redirects after login, rendering user-provided HTML or URLs, environment variables, browser storage, third-party scripts, or security headers. Trigger on phrases like "security", "auth", "cookie", "httpOnly", "SameSite", "CSRF", "login", "logout", "sign in", "session", "access token", "refresh token", "Authorization header", "401", "protected route", "redirect after login", "localStorage", "sessionStorage", "XSS", "dangerouslySetInnerHTML", "sanitize", "DOMPurify", "javascript: URL", "target=_blank", "CSP", "Content Security Policy", "secret", "API key", "VITE_", "password field", or "autocomplete".
---

# React Security (Client Side)

## Principles

- **The backend is the security boundary.** Route guards, hidden buttons and disabled fields are UX. Every authorization decision is enforced by the API. Never treat "the UI doesn't offer it" as protection.
- **XSS is the main threat to an SPA.** Any script that runs on the page can do everything the user can, including reading anything JavaScript can reach. Keep tokens out of JavaScript-readable storage and keep untrusted content from becoming script.
- **The access token lives in memory only.** Never in `localStorage`, `sessionStorage`, IndexedDB or a JavaScript-readable cookie.
- **The refresh token never reaches JavaScript.** The backend sets it as an httpOnly cookie, and the browser sends it with refresh and logout requests.
- **Auth code is security-critical.** Changes to `core/auth` and the HTTP client's auth handling go into their own PR with focused review.

---

## Where Things Live

| Piece | Location |
|---|---|
| Session state, access token, `ensureSession`, `endSession` | `src/core/auth/session.ts` |
| `fetchWithAuth` (auth header, refresh, retry) | `src/core/auth/fetchWithAuth.ts`, used by the HTTP client |
| Auth calls: log in, register, refresh, log out | `src/core/auth/authApi.ts` |
| Reacting to the end of a session (clear cache, redirect) | `src/app` |
| Route guard | `src/app/routes/_authenticated.tsx` (see **react-routing**) |
| Login and registration screens | a feature, for example `src/features/auth/` |

`core/auth` must not import the HTTP client that uses it. Its own calls use `fetch` directly with `apiBaseUrl` from `core/api/config.ts`, so a failing refresh can't trigger another refresh.

---

## Tokens and the Refresh Cookie

| | Access token | Refresh token |
|---|---|---|
| Form | short-lived JWT | opaque random string, rotated on every refresh |
| Arrives in | the JSON body of login and refresh | a `Set-Cookie` header: `HttpOnly`, `Secure`, `SameSite=Strict`, path limited to the auth endpoints |
| Kept in | a module variable in `core/auth` | the browser's cookie jar. JavaScript can't read it |
| Sent as | `Authorization: Bearer <token>` | the cookie, automatically, on refresh and logout |

- The app and the API share one origin (see **react-routing**), so `fetch` sends the cookie with its default `credentials: 'same-origin'`. Don't set `credentials: 'include'`, and don't add CORS handling.
- `SameSite=Strict` on a same-origin API means another site can't make the browser send the cookie, which covers CSRF for the refresh and logout endpoints. Never move these endpoints to another origin.
- Never try to read, set or delete the refresh cookie from JavaScript. Logout clears it on the backend.
- Endpoint paths and response shapes come from the OpenAPI spec (see **react-data-layer**). Don't guess them.

---

## Session State

```ts
// src/core/auth/session.ts
export type SessionStatus = 'unknown' | 'authenticated' | 'anonymous'

let accessToken: string | null = null
let status: SessionStatus = 'unknown'
const listeners = new Set<() => void>()

export function getAccessToken(): string | null {
  return accessToken
}

export function startSession(token: string) {
  accessToken = token
  setStatus('authenticated')
}

export function endSession() {
  accessToken = null
  setStatus('anonymous')
}

export function useSessionStatus(): SessionStatus {
  return useSyncExternalStore(subscribe, () => status)
}

// subscribe, setStatus and onSessionEnded notify listeners
```

- The token is a module variable, not React state and not context. The HTTP client reads it without React.
- A reload loses the token. That is intended. The session is restored on startup (below).
- Nothing outside `core/auth` reads or stores the token.

### Restoring on startup

`ensureSession()` restores the session once per page load and returns whether the user is signed in. Route guards await it, so protected pages never render before the answer is known:

```ts
let restoring: Promise<boolean> | null = null

export function ensureSession(): Promise<boolean> {
  if (status !== 'unknown') return Promise.resolve(status === 'authenticated')
  restoring ??= restoreSession().then((token) => {
    if (token) startSession(token)
    else endSession()
    return token !== null
  })
  return restoring
}
```

`restoreSession()` in `authApi.ts` calls the refresh endpoint. If the browser still has a valid refresh cookie, the response contains a new access token and the session continues. If not (no cookie, expired, revoked), the backend answers `401` and the user is anonymous. This is the same call as `refreshAccessToken()`. Only the caller differs.

---

## fetchWithAuth

```ts
// src/core/auth/fetchWithAuth.ts
let refreshing: Promise<boolean> | null = null

export async function fetchWithAuth(url: string, init: RequestInit): Promise<Response> {
  const token = getAccessToken()
  const response = await fetch(url, withAuthHeader(init, token))
  if (response.status !== 401 || token === null) return response

  const refreshed = await refreshOnce()
  if (!refreshed) {
    endSession()
    return response
  }
  return fetch(url, withAuthHeader(init, getAccessToken()))
}

function refreshOnce(): Promise<boolean> {
  refreshing ??= refreshAccessToken()
    .then((token) => {
      if (token) startSession(token)
      return token !== null
    })
    .finally(() => {
      refreshing = null
    })
  return refreshing
}
```

- **One shared in-flight refresh.** Ten requests failing with `401` at the same time cause one refresh, and all ten wait for it.
- **Retry once.** A request that fails with `401` again after a successful refresh is returned as is. No loops.
- **Requests without a token** (login, public endpoints) never trigger a refresh.
- The retried request must be re-sendable. Bodies are strings or `FormData`, never streams.
- If the refresh fails, the session ends. The original `401` becomes `DataError('unauthorized')`, which the UI doesn't show as an error (see **react-error-handling**).

### Several tabs

Each tab has its own in-memory token and its own refresh.

- The backend rotates the refresh token on every use, and all tabs share one cookie. Two tabs refreshing at the same moment would send the same old token, and the second one would fail. Serialize refreshes across tabs with the Web Locks API: `navigator.locks.request('auth-refresh', refreshAccessToken)`. The second tab then sends the already rotated cookie.
- Logout in one tab ends the session in all tabs. Broadcast it with a `BroadcastChannel`, and call `endSession()` when the message arrives.

---

## Ending a Session

On logout, on a failed refresh, and on a logout broadcast from another tab:

1. `endSession()` clears the token and sets the status to `anonymous`.
2. `src/app` listens (`onSessionEnded`) and calls `queryClient.clear()`, so the next user doesn't see cached data (see **react-server-state**).
3. User-scoped data in browser storage (drafts) is removed.
4. The app navigates to the login page with the current location as `redirect`.
5. On explicit logout, the backend is told (`authApi.logout()`) so it can revoke the refresh token and clear the cookie.
6. A session that ended without an explicit logout (failed refresh) shows the login page in its "session expired" state from Figma.

---

## Redirects After Login

The `redirect` search param is user-controlled. Only follow it to a path inside the app:

```ts
export function safeRedirectPath(value: unknown): string {
  if (typeof value !== 'string') return '/'
  if (!value.startsWith('/') || value.startsWith('//') || value.startsWith('/\\')) return '/'
  return value
}
```

A value like `//evil.example` or `https://evil.example` would otherwise send the freshly signed-in user to another site (open redirect).

---

## XSS

- **React escapes text.** `{note.title}` is safe whatever it contains.
- **No `dangerouslySetInnerHTML`** with content from the API or the user. If rich HTML must be shown, one component in `core/ui` sanitizes it with DOMPurify and is the only place that uses `dangerouslySetInnerHTML`. Translations with markup use the `Trans` component.
- **URLs from data are checked.** An `href` or `src` built from user content only accepts `https:`, `http:` and `mailto:`. A `javascript:` URL in an `href` runs script on click. Use a `safeUrl(value)` helper in `core` that returns `undefined` for anything else. Don't rely on React to block it.
- **`target="_blank"`** gets `rel="noopener noreferrer"`.
- **No `eval`, `new Function`, or `setTimeout` with a string.**
- **No third-party scripts** (analytics, chat widgets, tag managers) without review. They run with the same rights as the app.

---

## Configuration and Secrets

- Every `VITE_` variable is compiled into the bundle and readable by anyone. **No secrets in the frontend.** API keys that must be in the client are public by design (restricted by domain or scope on the provider's side).
- A value that must stay secret belongs in the backend, behind an endpoint.

---

## Browser Storage

| Data | Allowed in `localStorage`/`sessionStorage`? |
|---|---|
| Tokens of any kind | no |
| Personal data, API responses | no |
| UI preferences (a collapsed sidebar) | yes |
| Drafts the user expects to keep | yes, removed on logout |

---

## Hosting Headers

The hosting config (not the app code) sets the security headers. Keep the app compatible with them:

- **Content Security Policy** with `script-src 'self'`: no inline scripts and no `eval` in the app.
- `frame-ancestors 'none'` (or `X-Frame-Options: DENY`) against clickjacking.
- `Referrer-Policy: strict-origin-when-cross-origin`.
- HTTPS only, with HSTS.

---

## Forms and Passwords

- Login and registration forms use the right `autocomplete` values (`username`, `email`, `current-password`, `new-password`), so password managers work and suggest strong passwords.
- Password fields are `type="password"`. Never put a password into the URL or search params.
- Don't block pasting into password fields.
- Login errors say "email or password is wrong", whatever the backend's details are.

---

## Logging and Errors

- Never log tokens, `Authorization` headers, passwords or request bodies of auth calls, also not in development.
- Error reports strip headers and bodies (see **react-error-handling**).

---

## Dependencies

- Commit `package-lock.json`. Install in CI with `npm ci`.
- Run `npm audit` regularly. Check a new package's maintenance and download history before adding it (see **react-project-structure**).
- Prefer fewer dependencies. Every package runs with full access to the page.

---

## Testing

- `fetchWithAuth` against MSW (see **react-integration-testing**):
  - several requests that get a `401` at the same time cause exactly one refresh call
  - a request that still gets a `401` after a refresh is not retried again
  - a failed refresh ends the session
  - requests without a token never trigger a refresh
- `restoreSession` against MSW: a `200` from the refresh endpoint starts the session, a `401` makes the user anonymous without an error.
- The route guard: an anonymous user opening a protected URL lands on login, and is sent back to that URL after signing in.
- Logout clears the Query cache. A test signs in as user A, logs out, signs in as user B, and doesn't see A's data.
- `safeRedirectPath` and `safeUrl` get unit tests with every malicious form you can think of (see **react-unit-testing**).

---

## Checklist: Changing Auth or Rendering Untrusted Content

- [ ] Access token only in memory, refresh token only in the httpOnly cookie, never in browser storage or logs
- [ ] 401 handling goes through `fetchWithAuth`, with one shared refresh and one retry
- [ ] Ending a session clears the token, the Query cache and user-scoped storage, and notifies other tabs
- [ ] Protected pages are under the guard. The backend enforces access on its own
- [ ] Post-login redirects go through `safeRedirectPath`
- [ ] No `dangerouslySetInnerHTML` outside the sanitizing component, URLs from data go through `safeUrl`
- [ ] No secrets in `VITE_` variables
- [ ] Auth changes are in their own PR, with the tests listed above
