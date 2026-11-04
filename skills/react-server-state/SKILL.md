---
name: react-server-state
description: |
  Server state for React SPAs with TanStack Query v5 - the QueryClient and its defaults (staleTime, retry only for transient errors, background error toasts), one queries file per feature with a query key factory, queryOptions shared by route loaders and components, useSuspenseQuery vs useQuery, select for derived data, keeping previous data while filters change, mutation hooks, invalidation vs setQueryData, optimistic updates with rollback, infinite queries, data shared by several features, clearing the cache on logout, and test QueryClients. Use this skill whenever fetching or caching server data, writing a query or mutation, choosing a query key, invalidating or updating cached data, adding pagination or infinite scrolling, prefetching, or configuring TanStack Query. Trigger on phrases like "TanStack Query", "React Query", "useQuery", "useSuspenseQuery", "useMutation", "queryOptions", "query key", "invalidate", "invalidateQueries", "setQueryData", "optimistic update", "refetch", "staleTime", "cache", "prefetch", "ensureQueryData", "infinite scroll", "pagination", "useInfiniteQuery", "QueryClient", or "server state".
---

# React Server State (TanStack Query)

## Principles

- **Server data lives only in the Query cache.** Never copy it into `useState`, a reducer or a context. Derive from it during render instead (see **react-screen-architecture**).
- **One place per feature defines its queries.** `api/<feature>Queries.ts` holds the key factory, every `queryOptions` and every mutation hook. Route loaders and components use the same definitions, so a key is never typed twice.
- **Mutations update the cache explicitly.** Every mutation states which cached data it changes, by invalidating it or by writing the new value.
- **No fetching in `useEffect`.**

---

## QueryClient (`core/api`)

```ts
// src/core/api/queryClient.ts
const retryableKinds: ReadonlySet<DataErrorKind> = new Set(['network', 'timeout', 'server', 'tooManyRequests'])

export function createQueryClient() {
  return new QueryClient({
    queryCache: new QueryCache({
      onError: (error, query) => {
        // Data is already on screen, so the page doesn't show an error. Tell the user the refresh failed.
        if (query.state.data !== undefined) showBackgroundErrorToast(error)
      },
    }),
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        retry: (failureCount, error) =>
          failureCount < 2 && isDataError(error) && retryableKinds.has(error.kind),
      },
      mutations: {
        retry: false,
      },
    },
  })
}

export const queryClient = createQueryClient()
```

- **`staleTime`** is the project default for how long data counts as fresh. The library default of `0` refetches on every mount. Override per query when data changes much more or much less often.
- **Retry only transient errors.** Retrying a `404` or `403` only delays the error page.
- **Mutations don't retry.** A retried `POST` can create something twice.
- `refetchOnWindowFocus` stays on (the default). Users switching back to the tab get fresh data.
- The app creates one QueryClient. Tests create a new one per test (see [Testing](#testing)).

---

## Queries File

```ts
// src/features/notes/api/notesQueries.ts
export const notesKeys = {
  all: ['notes'] as const,
  lists: () => [...notesKeys.all, 'list'] as const,
  list: (filter: NoteFilter) => [...notesKeys.lists(), filter] as const,
  details: () => [...notesKeys.all, 'detail'] as const,
  detail: (noteId: string) => [...notesKeys.details(), noteId] as const,
}

export function noteListQueryOptions(filter: NoteFilter) {
  return queryOptions({
    queryKey: notesKeys.list(filter),
    queryFn: ({ signal }) => getNotes(filter, signal),
  })
}

export function noteQueryOptions(noteId: string) {
  return queryOptions({
    queryKey: notesKeys.detail(noteId),
    queryFn: ({ signal }) => getNote(noteId, signal),
  })
}
```

- **Keys are hierarchical** and start with the feature name. Invalidating `notesKeys.lists()` hits every list, `notesKeys.all` hits everything of the feature.
- **The key contains every variable the `queryFn` uses.** A filter that isn't in the key returns the cached result of another filter.
- **Keys contain plain values** (strings, numbers, plain objects). No `Date` objects or class instances.
- **`queryOptions`** makes `queryKey`, `queryFn` and the data type travel together. `getQueryData(noteQueryOptions(id).queryKey)` is then typed.
- **Forward `signal`** to the API function, so navigating away cancels the request.

---

## Reading Data

| Situation | Use |
|---|---|
| The page's main data, prefetched by the route loader | `useSuspenseQuery(options)`, where `data` is always defined |
| Secondary data in one section of a page | `useSuspenseQuery` inside its own `<Suspense>`, or `useQuery` with inline loading and error |
| Query that depends on user input and must not suspend (search as you type, a filter that changes in place) | `useQuery` with `placeholderData: keepPreviousData` |
| Query that must wait for something | `useQuery` with `enabled` |

```ts
const { data: notes } = useSuspenseQuery(noteListQueryOptions(filter))

const { data: archivedCount } = useQuery({
  ...noteListQueryOptions('archived'),
  select: (notes) => notes.length,
})
```

- **`select`** derives data per component without changing the cache. The component re-renders only when the selected value changes.
- Don't call API functions directly from components. They are only called from `queryFn` and `mutationFn`.
- Prefetch in the route loader with `queryClient.ensureQueryData(options)` (see **react-routing**). For data the user will probably need next, use `queryClient.prefetchQuery(options)` on hover or focus.

---

## Mutations

Mutation hooks live in the same queries file:

```ts
export function useCreateNoteMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: createNote,
    onSuccess: (note) => {
      queryClient.setQueryData(noteQueryOptions(note.id).queryKey, note)
      return queryClient.invalidateQueries({ queryKey: notesKeys.lists() })
    },
  })
}

export function useDeleteNoteMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteNote,
    onSuccess: (_result, noteId) => {
      queryClient.removeQueries({ queryKey: notesKeys.detail(noteId) })
      return queryClient.invalidateQueries({ queryKey: notesKeys.lists() })
    },
  })
}
```

- **Invalidate by default.** It's correct even when the server changes more than the client knows (sort order, counters, timestamps).
- **`setQueryData` in addition** when the response contains the new entity. The detail page then shows it immediately, without another request.
- **Return the invalidation promise** from `onSuccess`. The mutation then stays pending until the lists have refetched, so the UI doesn't show the old list for a moment.
- **Cache updates go in the hook's `onSuccess`, UI effects go in the call's `onSuccess`.** `mutate(values, { onSuccess: (note) => onSaved(note.id) })` (see **react-presentation-mvi**). The hook's callbacks run even if the component unmounted. The call's callbacks don't.
- Use `mutate`, not `mutateAsync`, in event handlers. `mutateAsync` throws on failure and needs its own `try/catch`.

### Optimistic updates

Only when the user needs instant feedback, like toggles, reordering or marking as done. Everything else waits for the server.

```ts
export function useArchiveNoteMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: archiveNote,
    onMutate: async (noteId) => {
      const { queryKey } = noteQueryOptions(noteId)
      await queryClient.cancelQueries({ queryKey })
      const previous = queryClient.getQueryData(queryKey)
      if (previous) queryClient.setQueryData(queryKey, { ...previous, archivedAt: new Date() })
      return { previous }
    },
    onError: (_error, noteId, context) => {
      if (context?.previous) {
        queryClient.setQueryData(noteQueryOptions(noteId).queryKey, context.previous)
      }
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: notesKeys.all }),
  })
}
```

- Always cancel outgoing queries first, so a slower refetch doesn't overwrite the optimistic value.
- Always roll back on error and invalidate when settled.
- When only one component shows the pending change, rendering the mutation's `variables` while `isPending` is simpler than touching the cache.

---

## Pagination and Infinite Lists

- Page-numbered lists: the page is part of the key and the search params. Use `placeholderData: keepPreviousData` so the old page stays visible while the next one loads.
- Infinite scrolling: `infiniteQueryOptions` + `useInfiniteQuery` (or `useSuspenseInfiniteQuery`), with `getNextPageParam` reading the cursor from the last page.

---

## Data Shared by Several Features

A feature can't import another feature's keys (see **react-project-structure**). When two features read or change the same server data, move its API function, schemas and query definitions to `core/api`, and both features use them from there. Don't invalidate another feature's data with a hand-typed key like `['notes']`.

---

## Session Changes

- On logout or when the session ends, call `queryClient.clear()`. The next user must not see the previous user's cached data (see **react-security**).
- On login, nothing needs to be cleared, because the cache was cleared on logout.

---

## Testing

```ts
export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: Infinity },
      mutations: { retry: false },
    },
  })
}
```

- A new QueryClient for every test. A shared client leaks cached data between tests.
- `retry: false`, so error tests fail immediately instead of waiting through retries.
- Tests go through MSW and the real API functions (see **react-integration-testing**).

---

## Naming Conventions

| Thing | Convention | Example |
|---|---|---|
| Queries file | `api/<feature>Queries.ts` | `notesQueries.ts` |
| Key factory | `<feature>Keys` | `notesKeys` |
| Query options | `<thing>QueryOptions` | `noteQueryOptions`, `noteListQueryOptions` |
| Mutation hook | `use<Verb><Thing>Mutation` | `useCreateNoteMutation` |

---

## Checklist: Adding a Query or Mutation

- [ ] Key from the feature's key factory, containing every variable the `queryFn` uses
- [ ] `queryOptions` in the feature's queries file, `signal` forwarded
- [ ] Prefetched in the route loader if it's the page's main data, read with `useSuspenseQuery`
- [ ] Mutation hook states what it invalidates or writes, and returns the invalidation promise
- [ ] UI effects (navigation, closing a dialog) in the call's `onSuccess`, cache updates in the hook's
- [ ] Optimistic updates only with cancel, rollback and invalidate
- [ ] Tested with a fresh QueryClient and MSW
