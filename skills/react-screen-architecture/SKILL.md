---
name: react-screen-architecture
description: |
  Screen-level architecture for React SPAs - re-render behavior, state placement and co-location, derived state, when useEffect is allowed and what to use instead, Suspense boundaries, lists and keys, state that survives a reload, leaving a page with unsaved changes, responsive layout through the Figma breakpoints, keyboard-accessible drag and drop, automatic memoization by the React Compiler, hover and touch, focus and keyboard handling, document titles, and animations. This skill is about HOW screens are structured, not how individual components are built (see react-ui-components) or how the Root/Screen/view-model split works (see react-presentation-mvi). Use this skill whenever structuring a screen, deciding where state lives, adding a useEffect, fixing unnecessary re-renders, adding memoization, rendering lists, making a layout responsive, or adding animations. Trigger on phrases like "React Compiler", "drag and drop", "dnd-kit", "re-render", "performance", "useEffect", "useMemo", "useCallback", "memo", "derived state", "lift state", "Suspense", "key prop", "long list", "virtualize", "responsive", "breakpoint", "mobile layout", "matchMedia", "hover", "focus", "keyboard", "document title", "unsaved changes", "animation", "transition", or "prefers-reduced-motion".
---

# React Screen Architecture

## Core Principle

Components render state and forward user input. Logic lives in reducers, view-model hooks, `utils/` and the API layer. A Screen contains no business rules, no data transformation beyond formatting for display, and as few effects as possible.

---

## Re-renders

A component re-renders when its state changes, when its parent re-renders, or when a context it reads changes. Re-rendering is cheap. What makes it expensive is a large subtree re-rendering on every keystroke or on every frame.

- **Keep state as low in the tree as possible.** State used by one component lives in that component. Lift it only as far as the nearest component that needs it.
- **No manual memoization.** The project runs the React Compiler, which memoizes components, values and callbacks automatically. Don't write `useMemo`, `useCallback` or `memo`. The one exception is a value that a non-React library compares by identity and the compiler can't see. Add a short comment saying why.
- If the compiler skips a component (it bails out on code that breaks the Rules of React), fix the code instead of adding manual memoization.
- **Inputs don't re-render the screen.** Forms use React Hook Form's uncontrolled inputs (see **react-presentation-mvi**). A controlled input is only for a value the rest of the screen reacts to, like a search box.
- **Context is not a state store.** A context value that changes often re-renders every consumer. App-wide contexts hold stable objects (the QueryClient, i18n), not changing UI state.

---

## Derived State

If a value can be computed from props, state or query data, compute it during render:

```tsx
// Good
const visibleNotes = filterByQuery(notes, query)

// Bad: an extra render, and a frame where the two values disagree
const [visibleNotes, setVisibleNotes] = useState(notes)
useEffect(() => setVisibleNotes(filterByQuery(notes, query)), [notes, query])
```

Use TanStack Query's `select` option for derivations of server data that several components share (see **react-server-state**).

---

## Effects

`useEffect` is for synchronizing with something outside React. Before writing one, check this table:

| You want to | Use instead of an effect |
|---|---|
| Fetch data | TanStack Query (`useSuspenseQuery`, `useQuery`) and route loaders |
| Compute a value from other values | compute it during render |
| React to a click or a submit | the event handler, or `onAction` |
| Navigate after a mutation | the mutation's `onSuccess` calling a callback |
| Reset state when an ID changes | `key={id}` on the component |
| Notify a parent about a change | call the parent's callback in the event handler |

Valid uses: subscribing to a browser API (`resize`, `online`/`offline`, `matchMedia`), setting `document.title`, managing focus after something appears, integrating a non-React library.

- Extract every effect into a named custom hook (`useDocumentTitle`, `useOnlineStatus`) in `core` or the feature's `hooks/`, so Screens don't contain raw effects.
- Every subscription has a cleanup.
- For subscribing to an external store, prefer `useSyncExternalStore` over `useEffect` + `useState`.
- `StrictMode` runs effects twice in development. If that breaks something, the effect is missing a cleanup.

---

## Suspense Boundaries

- The route is the default boundary. Its `pendingComponent` shows while the loader and the code chunk load (see **react-routing**).
- A secondary section that loads on its own (a sidebar, a "related items" panel) gets its own `<Suspense fallback={...}>` around a component that calls `useSuspenseQuery`, so it doesn't block the page.
- Don't wrap every component in its own `Suspense`. Several spinners that appear and disappear one by one look worse than one.
- Fallbacks are skeletons sized like the content, so the layout doesn't jump when data arrives.

---

## Lists

```tsx
{state.notes.map((note) => (
  <NoteCard key={note.id} note={note} />
))}
```

- `key` is a stable ID from the data. Never the array index for lists that can be reordered, filtered or edited, because React then reuses the wrong component state.
- Long lists (hundreds of rows or more) are virtualized with TanStack Virtual. Don't virtualize short lists. It breaks the browser's find-in-page and adds complexity.
- Lists that load more pages use `useInfiniteQuery` (see **react-server-state**).

---

## Reloads and Leaving a Page

The web has no process death, but every reload, every new tab and every shared link starts from the URL.

- **Survives a reload:** path and search params. Put filters, sort order, the selected tab and the open item there.
- **Doesn't survive a reload:** reducer state, form input, scroll position within the page. That's fine for most state.
- **Unsaved changes:** a form with significant user input uses TanStack Router's `useBlocker` to ask before navigating away, including on tab close.
- Writing to the URL on every keystroke (a search box) uses `navigate({ search, replace: true })`, so each keystroke doesn't become a history entry.
- Don't use `localStorage` to keep screen state unless the user expects it to persist (like a draft). Never store tokens or personal data there (see **react-security**).

---

## Responsive Layout

Layout differences are CSS, not JavaScript:

```tsx
<div className="grid grid-cols-1 gap-4 tablet:grid-cols-2 desktop:grid-cols-3">
```

The layouts come from the Figma frames at the three sizes: phone 390, tablet 834, desktop 1440. Compare all three before building a screen. Tablet landscape uses the desktop layout.

- Tailwind is mobile-first: unprefixed classes are for the smallest size, and breakpoint prefixes add to them.
- Use the breakpoints from the theme, `tablet` (640 px) and `desktop` (1024 px), which come from Figma Foundations. Never Tailwind's defaults, and never a width in a media query or `matchMedia` call outside the theme.
- Read the window size in JavaScript (`matchMedia` through `useSyncExternalStore`) only when the component tree itself differs, for example a side navigation on large screens vs a bottom bar on small ones. Put that hook in `core/ui`.
- Every interaction works with touch, mouse and keyboard. Nothing is only reachable on hover.
- **Drag & drop** uses dnd-kit with its pointer, touch and **keyboard** sensors, plus screen reader announcements for pick up, move, drop and cancel. Keyboard users move items with Space, the arrow keys and Escape. Don't add another way to move items (like a "Move to…" menu) unless Figma designs it. Hover styles use the `hover:` variant, which Tailwind v4 already limits to devices that can hover.
- Test layouts at the breakpoint boundaries (one pixel below and at each breakpoint).

---

## Focus, Keyboard and Page Title

- Use semantic elements (`main`, `nav`, `h1`–`h3`, `button`, `a`, `ul`) so keyboard and screen reader navigation work without extra code. Each page has exactly one `h1`.
- Interactive elements are `button` or `a`, never a `div` with `onClick`.
- Dialogs, menus and popovers come from `core/ui` (Radix underneath), which handles focus trapping, Escape and returning focus.
- Each page sets a translated `document.title` through a shared hook.
- After a destructive action removes the focused element (deleting a row), move focus somewhere sensible, such as the list heading.

---

## Animations

- Animate `transform` and `opacity` with CSS transitions or Tailwind's `transition-*` classes. They run on the compositor without layout or re-renders, like `graphicsLayer` in Compose.
- Don't animate `width`, `height`, `top` or `left`.
- Don't drive animations with React state updated every frame.
- Respect reduced motion: use the `motion-safe:` and `motion-reduce:` variants.

---

## Checklist: Structuring a Screen

- [ ] Each piece of state has one owner: Query cache, URL, reducer, form, or local component
- [ ] No state that can be computed during render
- [ ] Every `useEffect` syncs with something outside React, sits in a named custom hook, and has a cleanup
- [ ] No manual memoization (the React Compiler handles it)
- [ ] Lists keyed by stable IDs
- [ ] Shareable and reload-relevant state in search params
- [ ] Responsive through the theme's `tablet`/`desktop` classes, matching the Figma frames, works with touch and keyboard (drag & drop included)
- [ ] One `h1`, semantic elements, a translated page title
- [ ] Animations use `transform`/`opacity` and respect reduced motion
