---
name: react-presentation-mvi
description: |
  MVI-style presentation layer for React SPAs - the Root/Screen component split, view-model hooks (useXxxViewModel) that combine useReducer UI state with TanStack Query data and expose state plus a single onAction function, State and Action types as discriminated unions, reducers, one-off effects through callbacks, forms with React Hook Form and Zod inside the Screen, mutation pending and error state, and when to skip the view-model hook. Use this skill whenever creating a page or screen, writing a view-model hook or reducer, defining screen state or actions, wiring a form to a mutation, or reviewing how a screen gets its data. Trigger on phrases like "create a screen", "add a page component", "view model", "useViewModel", "MVI", "state", "action", "onAction", "reducer", "useReducer", "Root component", "Screen component", "form", "submit", "React Hook Form", "useForm", or "zodResolver".
---

# React Presentation Layer (MVI)

## Overview

Every page has:

1. **Root component** (`<Page>Root`) — receives plain props from the route file (IDs, search values, navigation callbacks), calls the view-model hook, renders the Screen.
2. **Screen component** (`<Page>Screen`) — receives `state`, `onAction` and direct callbacks. Renders UI. No data fetching.
3. **View-model hook** (`use<Page>ViewModel`, optional) — combines server data from TanStack Query with UI state from a reducer and returns `{ state, onAction }`.
4. **State and Action types** — `State` is what the Screen renders. `Action` is a discriminated union on `type` of everything the user can do.

This is the Android Root/Screen + ViewModel split. The differences come from React: there is no ViewModel object that outlives the component, server data lives in the Query cache instead of the ViewModel, and one-off effects are callbacks instead of an event channel.

---

## Who Owns Which State

| State | Owner |
|---|---|
| Server data (lists, details) | TanStack Query cache (see **react-server-state**). Never copied into the reducer |
| State that must survive a reload or be shareable (filters, selected tab, search text) | URL search params (see **react-routing**) |
| Screen-level UI state that drives behavior (which dialog is open, selection mode, pending delete) | the view-model hook's reducer |
| Form input values and validation | React Hook Form inside a form component |
| Purely visual state (hover, a dropdown being open, which accordion item is expanded) | the component itself, or the Radix primitive that already manages it |

The reducer is not a store for everything. If a value only affects how one component looks, it stays in that component. See **react-screen-architecture**.

---

## State and Action

```ts
// src/features/notes/hooks/noteListReducer.ts
export type NoteListReducerState = {
  pendingDeleteId: string | null
  isSelecting: boolean
  selectedIds: ReadonlySet<string>
}

export type NoteListAction =
  | { type: 'deleteClick'; noteId: string }
  | { type: 'deleteConfirm'; noteId: string }
  | { type: 'deleteDismiss' }
  | { type: 'selectionToggle'; noteId: string }
  | { type: 'queryChange'; query: string }

export const initialNoteListState: NoteListReducerState = {
  pendingDeleteId: null,
  isSelecting: false,
  selectedIds: new Set(),
}

export function noteListReducer(
  state: NoteListReducerState,
  action: NoteListAction,
): NoteListReducerState {
  switch (action.type) {
    case 'deleteClick':
      return { ...state, pendingDeleteId: action.noteId }
    case 'deleteConfirm':
    case 'deleteDismiss':
      return { ...state, pendingDeleteId: null }
    case 'selectionToggle': {
      const selectedIds = new Set(state.selectedIds)
      if (!selectedIds.delete(action.noteId)) selectedIds.add(action.noteId)
      return { ...state, selectedIds, isSelecting: selectedIds.size > 0 }
    }
    case 'queryChange':
      return state
  }
}
```

- The reducer handles **every** action. Actions that don't change UI state return `state` explicitly. Without a `default` branch, TypeScript reports a missing case when a new action is added.
- Reducers are pure: no API calls, no `Date.now()`, no randomness. Anything impure happens in `onAction`.
- State is immutable. Return new objects and collections, never mutate.
- The reducer and its types live in their own file, so they can be unit-tested without React (see **react-unit-testing**).
- Action names describe what the user did, not what should happen: `deleteClick`, not `openDeleteDialog`.

---

## View-Model Hook

```ts
// src/features/notes/hooks/useNoteListViewModel.ts
type Params = {
  filter: NoteFilter
  query: string
  onQueryChange: (query: string) => void
}

export function useNoteListViewModel({ filter, query, onQueryChange }: Params) {
  const { data: notes } = useSuspenseQuery(noteListQueryOptions(filter))
  const deleteNote = useDeleteNoteMutation()
  const [uiState, dispatch] = useReducer(noteListReducer, initialNoteListState)

  const state: NoteListState = {
    ...uiState,
    notes: filterByQuery(notes, query),
    query,
    isDeleting: deleteNote.isPending,
    deleteError: deleteNote.error,
  }

  const onAction = (action: NoteListAction) => {
    dispatch(action)
    switch (action.type) {
      case 'deleteConfirm':
        deleteNote.mutate(action.noteId)
        break
      case 'queryChange':
        onQueryChange(action.query)
        break
    }
  }

  return { state, onAction }
}

export type NoteListState = NoteListReducerState & {
  notes: Note[]
  query: string
  isDeleting: boolean
  deleteError: Error | null
}
```

- `state` is computed on every render from the Query data, the reducer state and the props. Derived values (`filterByQuery`) are computed here, not stored.
- `onAction` is the only entry point for the Screen. It dispatches to the reducer, then runs effects: mutations, callbacks into the route.
- Use `useSuspenseQuery` for data the route loader prefetched. `data` is then always defined, and loading and errors are handled by the route's pending and error components.
- Don't wrap `onAction` or `state` in `useCallback`/`useMemo`. The React Compiler memoizes them (see **react-screen-architecture**).

### One-off effects

There is no event channel. Effects that follow an async result are callbacks the Root passes into the hook:

```ts
export function useNoteEditorViewModel({ noteId, onSaved }: Params) {
  const saveNote = useSaveNoteMutation()

  const onAction = (action: NoteEditorAction) => {
    switch (action.type) {
      case 'submit':
        saveNote.mutate(
          { noteId, values: action.values },
          { onSuccess: (note) => onSaved(note.id) },
        )
        break
    }
  }
  // ...
}
```

- Navigation after success, closing a dialog owned by the parent: callbacks.
- A toast after success: call the toast function from `core/ui` in the mutation's `onSuccess`.
- An error that the screen shows: comes from the mutation's `error` into `state`. Don't copy it into the reducer.

### When to skip the view-model hook

A page that only displays query data and has no UI state of its own doesn't need a reducer or a view-model hook. The Root calls `useSuspenseQuery` and passes the data to the Screen. Add the hook when the first piece of UI state or the first action with an effect shows up.

---

## Root and Screen

Both live in one file, named after the Screen:

```tsx
// src/features/notes/components/NoteListScreen.tsx
type NoteListRootProps = {
  filter: NoteFilter
  query: string
  onSearchChange: (search: { query: string }) => void
}

export function NoteListRoot({ filter, query, onSearchChange }: NoteListRootProps) {
  const { state, onAction } = useNoteListViewModel({
    filter,
    query,
    onQueryChange: (query) => onSearchChange({ query }),
  })
  return <NoteListScreen state={state} onAction={onAction} />
}

type NoteListScreenProps = {
  state: NoteListState
  onAction: (action: NoteListAction) => void
}

export function NoteListScreen({ state, onAction }: NoteListScreenProps) {
  const { t } = useTranslation('notes')
  return (
    <main className="px-4 py-6">
      <h1 className="type-page-title">{t('list.title')}</h1>
      <ul>
        {state.notes.map((note) => (
          <li key={note.id}>
            <Link to="/notes/$noteId" params={{ noteId: note.id }}>
              {note.title}
            </Link>
            <IconButton
              icon={TrashIcon}
              label={t('list.delete')}
              onClick={() => onAction({ type: 'deleteClick', noteId: note.id })}
            />
          </li>
        ))}
      </ul>
      {/* ... */}
    </main>
  )
}
```

**Root**

- Calls exactly one view-model hook (or one query when there is no hook).
- Receives route-level data as props. Never reads route params, search or context itself.

**Screen**

- Props in, JSX out. No `useQuery`, no mutations, no API imports.
- May use `useTranslation`, `<Link>`, and local state for purely visual concerns.
- Plain navigation is a `<Link>` in the Screen, not an action (see **react-routing**).
- Tested with props only, without MSW or a router (see **react-integration-testing**).

---

## Forms

React Hook Form keeps input state outside React state, so typing doesn't re-render the screen. A form is its own component inside the Screen. The view-model only sees validated values on submit.

```ts
// src/features/notes/utils/noteForm.ts
export const noteFormSchema = z.object({
  title: z.string().trim().min(1, 'notes:form.titleRequired').max(120, 'notes:form.titleTooLong'),
  body: z.string().max(10_000, 'notes:form.bodyTooLong'),
})

export type NoteFormValues = z.infer<typeof noteFormSchema>
```

```tsx
// src/features/notes/components/NoteForm.tsx
type NoteFormProps = {
  defaultValues: NoteFormValues
  isSubmitting: boolean
  submitError: Error | null
  onSubmit: (values: NoteFormValues) => void
}

export function NoteForm({ defaultValues, isSubmitting, submitError, onSubmit }: NoteFormProps) {
  const { t } = useTranslation('notes')
  const errorMessage = useErrorMessage()
  const translateError = useTranslatedError()
  const { register, handleSubmit, formState } = useForm({
    resolver: zodResolver(noteFormSchema),
    defaultValues,
  })

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate>
      <TextField
        label={t('form.title')}
        error={translateError(formState.errors.title?.message)}
        {...register('title')}
      />
      {submitError && <FormError>{errorMessage(submitError)}</FormError>}
      <Button type="submit" isLoading={isSubmitting}>{t('form.save')}</Button>
    </form>
  )
}
```

```tsx
// in NoteEditorScreen
<NoteForm
  defaultValues={state.defaultValues}
  isSubmitting={state.isSaving}
  submitError={state.saveError}
  onSubmit={(values) => onAction({ type: 'submit', values })}
/>
```

- The Zod schema is the single definition of the form's rules. Its error messages are translation keys, turned into text with `useTranslatedError()` (see **react-ui-components**).
- `core/ui` input components accept `ref` and the props from `register`, so they work with React Hook Form directly.
- `noValidate` turns off the browser's own validation bubbles, so all messages come from the schema and are translated.
- Field-level errors from the server (a "title already taken" code) are passed in through React Hook Form's `errors` option and shown on the field.
- A form that needs values from other fields while typing uses `useWatch`, not a reducer.

---

## Errors

- Query errors on prefetched data are handled by the route's `errorComponent`.
- Mutation errors come from the mutation into `state` and are shown inline next to what failed, or as a toast for background actions.
- The message comes from `useErrorMessage()(error)`, which maps `DataError.kind` (and known API error codes) to translation keys. Never show `error.message` to users. See **react-error-handling**.

---

## Formatting

There are no separate UI model types with pre-formatted strings by default. Dates, numbers and plurals are formatted where they are rendered, through i18next formatting or `Intl`, so they follow the active language (see **react-ui-components**). Add a dedicated view type only when a Screen needs a really different shape than the domain type.

---

## Naming Conventions

| Thing | Convention | Example |
|---|---|---|
| View-model hook | `use<Page>ViewModel` | `useNoteListViewModel` |
| Reducer | `<page>Reducer` in `<page>Reducer.ts` | `noteListReducer` |
| Reducer state | `<Page>ReducerState` | `NoteListReducerState` |
| Screen state | `<Page>State` | `NoteListState` |
| Action union | `<Page>Action` | `NoteListAction` |
| Action `type` | camelCase, what the user did | `'deleteClick'`, `'queryChange'`, `'submit'` |
| Root component | `<Page>Root` | `NoteListRoot` |
| Screen component | `<Page>Screen` | `NoteListScreen` |
| File holding Root + Screen | `<Page>Screen.tsx` | `NoteListScreen.tsx` |
| Form component | `<Thing>Form` | `NoteForm` |
| Form schema / values | `<thing>FormSchema` / `<Thing>FormValues` | `noteFormSchema`, `NoteFormValues` |

---

## Checklist: Adding a Screen

- [ ] Route file passes params, search values and navigation callbacks to the Root as props
- [ ] Decide whether a view-model hook is needed (UI state or actions with effects). If not, the Root reads the query directly
- [ ] `State`, `Action` union and reducer in `hooks/<page>Reducer.ts`, with every action handled
- [ ] View-model hook uses `useSuspenseQuery` for prefetched data and never copies it into the reducer
- [ ] Screen is props-only, uses `<Link>` for navigation and `onAction` for everything else
- [ ] Forms use React Hook Form + `zodResolver` with translation keys as error messages
- [ ] Errors shown through `useErrorMessage`, never `error.message`
- [ ] Unit tests for the reducer, component tests for the Screen and the Root
