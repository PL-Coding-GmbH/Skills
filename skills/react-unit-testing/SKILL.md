---
name: react-unit-testing
description: |
  Unit testing for React/TypeScript SPAs - an adversarial "how would I break this?" methodology first, then Vitest, it.each, fake timers with a fixed system time and time zone, no vi.mock of the project's own modules, and an optional Stryker mutation-testing pass (only when explicitly requested). Every suite starts by enumerating break vectors - JavaScript-specific ones like UTF-16 string length and emoji, locale-sensitive case and sorting, Number('') === 0, floating point and unsafe integers, Date parsing and time zones, falsy 0 and '', mutating sort - plus boundaries, impossible state transitions and malformed API data, and keeps only distinct, non-overlapping test angles. A unit test renders nothing and does no I/O - no DOM rendering, no network, no MSW, no storage, no real clock. Use this skill whenever writing or reviewing tests for reducers, mappers, Zod schemas, search param schemas, validators, formatters, utils, error mapping, or any pure function. Trigger on phrases like "unit test", "test the reducer", "test the mapper", "test the schema", "test this function", "test this logic", "Vitest", "it.each", "fake timers", "vi.useFakeTimers", "setSystemTime", "edge cases", "break this", "mutation testing", "Stryker", or "write tests for".
---

# React Unit Testing

## Core methodology — test as someone who wants to break the code

**Read this before anything else in this skill. It applies to every test you write, and it comes before any question of setup, libraries, or syntax.**

Before writing a single test for a unit, switch roles. You are not the author demonstrating that the code works. You are an adversary who has been handed this code and paid to make it produce a wrong answer, show the wrong thing, or accept input it should reject. Assume a bug is in there. Your job is to find the input, ordering, or state that exposes it.

Three rules govern everything below:

1. **Adversary first.** Enumerate break vectors *in writing* before you write any test code. The happy path is one line item in the list, not the starting point.
2. **Creative exhaustion.** The obvious edge cases are the ones the author already handled. The bugs live in the cases nobody imagined: an emoji in a title limit, a date that lands on a DST change, an API that sends `null` where the type says `string`, the same action dispatched twice. Hunt those deliberately.
3. **One angle per test.** Every test must attack the unit from an angle no other test covers. Twenty tests that all fail for the same reason are one test with nineteen copies.

### Step 1 — Map the attack surface

List, explicitly:

- Every exported function and every parameter it takes.
- Every outcome: each return shape, each thrown error, each state a reducer can reach.
- Every input that comes from outside the code: API JSON, URL search params, form input, `navigator.languages`.
- Every implicit input: the current time, the time zone, the active language, default parameter values.

### Step 2 — For each item, ask: "How would I break this?"

Write the break vectors down as a plain list first, in prose. Keep asking until the list stops growing. Only then write `it(...)` blocks, one per surviving vector.

Useful adversary prompts:

- What input makes this function's assumption about its argument false?
- What value is legal for the TypeScript type but illegal for the domain?
- What does the API send that the type doesn't admit (`null`, a missing key, an unknown enum value)?
- What happens exactly at the boundary, and one step past it?
- What if this action arrives twice? In a state where it makes no sense?
- What would a user typing into this field, or editing this URL by hand, send?

### Step 3 — The break-vector catalogue

Walk this every time. Not every category applies to every unit, but you must *consider* each one and consciously skip it, not forget it.

**Text and string input**

- Empty string; whitespace-only; leading/trailing whitespace. Is it trimmed before validation *and* before sending?
- **Length is UTF-16 units.** `'👍🏽'.length === 4`, `'👨‍👩‍👧‍👦'.length === 11`. Every max length, truncation or "characters left" counter is a break vector. Does it match how the backend counts? What the user sees as one character is a grapheme (`Intl.Segmenter`).
- Truncating with `slice` can cut an emoji or surrogate pair in half.
- Non-Latin scripts, right-to-left text, combining characters (`'é'` as one code point vs `e` + U+0301; `normalize('NFC')` wherever equality or search matters).
- **Case is locale-sensitive.** `'I'.toLocaleLowerCase('tr') === 'ı'`, `'ß'.toUpperCase() === 'SS'`. Case-insensitive comparisons use `localeCompare` with `sensitivity: 'accent'` or a fixed approach on both sides.
- **Sorting text** with `<` or default `sort()` orders by code unit (`'Z' < 'a'`, `'é'` after `'z'`). User-visible sorting uses `Intl.Collator`.
- Whitespace `trim()` doesn't remove: zero-width space (U+200B). Bidi override (U+202E).
- Strings that end up in a URL: `/`, `?`, `#`, `%`, spaces.

**Numbers**

- `Number('') === 0`, `Number(' ') === 0`, `Number(null) === 0`, `parseInt('12abc') === 12`, `Number('1e3') === 1000`. Every place that parses user input or search params.
- `NaN` passes `typeof x === 'number'` and fails every comparison.
- Floating point: `0.1 + 0.2 !== 0.3`. Money and percentages are a break vector.
- Integers above `Number.MAX_SAFE_INTEGER` (2^53 − 1) lose precision. IDs from the API that might be that large must stay strings.
- `0` and `-0`, `Infinity` from division by zero, negative values where only positive make sense.

**Truthiness and nullish values**

- `0`, `''` and `false` are falsy. `if (count)` and `value || fallback` are bugs when `0` or `''` are valid. Use `??` and explicit checks.
- `null` vs `undefined` vs a missing key: three different things from an API, often handled as one.

**Dates and time**

- `new Date('2026-03-29')` is UTC midnight, `new Date('2026-03-29T00:00')` is local midnight. In time zones west of UTC the first one is the previous day.
- DST changes: a day with 23 or 25 hours, a local time that doesn't exist (02:30 on the spring change).
- `new Date('garbage')` doesn't throw. It returns an Invalid Date whose `getTime()` is `NaN`.
- Months are 0-based in `new Date(y, m, d)`.
- "Today", "yesterday", relative times: midnight exactly, one millisecond before and after. Year boundaries.
- Formatting depends on the active language. Test with the language the test sets, not the machine's.

**Collections**

- Empty; one element; exactly at a limit; limit + 1.
- Duplicates, including duplicates that only differ by case or normalization.
- `sort()`, `reverse()` and `splice()` mutate the input. Did the unit just change its caller's array (or the Query cache)? Use `toSorted`, `toReversed`, `toSpliced`.
- IDs that don't exist in the list; a mix of existing and missing IDs.

**Reducers and state machines**

- Every action from every state where it can arrive, including states where it makes no sense (confirm a delete when no delete is pending).
- The same action twice in a row.
- The input state is not mutated. Freeze it (`Object.freeze`, deep for nested values) and run the reducer on it.
- The transitions that must be impossible.

**Data from outside (schemas, mappers, search params)**

- Missing required field; `null` where not nullable; wrong type (`"5"` instead of `5`).
- Unknown enum value: does it fall back as intended, or fail as `serialization`?
- Extra fields: stripped, not passed through.
- Dates without an offset, dates with a different offset, invalid dates.
- Search params edited by hand: unknown values, wrong types, a value repeated twice. Each falls back to its default.

### Step 4 — Distinct angles only

> **Two tests are redundant if a single change to the production code would make both fail for the same reason.**

Before you commit to a test, name the specific behavior, branch, or line that this test — and only this test — guards. If you can't name it, the test doesn't earn its place.

| Redundant | Distinct |
|---|---|
| `rejects an empty title` + `rejects a whitespace title` through one `trim().min(1)` | `rejects a whitespace-only title` + `counts an emoji title by what the backend counts` |
| Three tests for three unknown statuses that hit the same `return 'unknown'` | One test for an unknown 4xx + one for a 5xx outside the listed ones |
| `maps a note` + `maps a note and returns it` | `maps a null archivedAt to null` + `parses an offset date to the same instant` |

Use **`it.each`** when you have **one angle across many data points** (twelve malformed search values hitting the same fallback). Don't use it to smuggle several different angles into one test. Those deserve their own names, because the test name documents the break vector.

```ts
it.each(['', '  ', 'abc', '-1', '1.5', 'NaN', 'Infinity'])(
  'falls back to page 1 for page=%j',
  (page) => {
    expect(noteListSearchSchema.parse({ page }).page).toBe(1)
  },
)
```

### Step 5 — Stop condition

The suite is complete when **you can't name another way to break the unit without changing its public contract.** If a break vector isn't observable through the exports, the unit usually needs to be split or to return more information, not fewer tests.

---

## What is a unit test here

A unit test:

- Imports a function and calls it. It renders nothing.
- Does **no I/O**: no `fetch`, no MSW, no `localStorage`, no real timers, no reading the real clock.
- May use several real modules together (a mapper calling a schema), as long as none of them crosses those boundaries.

| Test | Kind |
|---|---|
| `noteListReducer`, `toNote`, `kindForStatus`, `filterByQuery`, search param schemas, form schemas | ✅ unit (this skill) |
| A Screen rendered with props, a Root or route with MSW | ❌ component test (**react-integration-testing**) |
| An API function or the HTTP client against MSW | ❌ integration test (**react-integration-testing**) |
| A view-model hook through `renderHook` | ❌ component test. Prefer testing it through its Root |

What unit tests **cannot** show, and integration tests must cover instead: that the right request is sent, that the cache is invalidated, that the UI shows the error, that a form submits the right values.

---

## Stack

| Concern | Tool |
|---|---|
| Runner, assertions | Vitest (`describe`, `it`, `expect`) |
| Many data points, one angle | `it.each` |
| Time | `vi.useFakeTimers()` + `vi.setSystemTime(...)` |
| Time zone | fixed in the Vitest config (`test.env.TZ`) |
| Callbacks passed into the unit | `vi.fn()`, asserting the arguments it was called with |

- **No `vi.mock` of the project's own modules.** If a unit needs a module replaced, it does I/O and belongs in an integration test with MSW, or the I/O should be passed in as a parameter.
- **Fake time, never real time.** Code under test calls `Date.now()` or `new Date()` freely. Tests pin it with `vi.setSystemTime(new Date('2026-01-15T10:00:00Z'))` and restore with `vi.useRealTimers()` in `afterEach`.
- **Pin the time zone to one that isn't UTC** (for example `Europe/Berlin`) in the Vitest config, so code that only works in UTC fails in tests, not for users.
- Pure tests can opt out of jsdom with `// @vitest-environment node` at the top of the file. They run faster.
- No snapshot tests for logic. Assert the values that matter.

---

## Where unit tests live

- Next to the file under test: `noteMapper.ts` → `noteMapper.test.ts`.
- `describe` names the unit. `it` is a sentence describing the behavior: `it('keeps the selection when a note is deleted that was not selected')`.
- Shared test data builders (`aNote({ title: 'x' })`) live in the feature, for example `src/features/notes/testing/noteFixtures.ts`. Shared builders for core types live in `src/core/testing/`.
- Run: `npm test`, or `npx vitest <path>` while working.

---

## Examples

### Reducer

```ts
describe('noteListReducer', () => {
  const frozen = (state: NoteListReducerState) =>
    Object.freeze({ ...state, selectedIds: new Set(state.selectedIds) })

  it('ignores a delete confirmation when no delete is pending', () => {
    const state = frozen(initialNoteListState)

    const next = noteListReducer(state, { type: 'deleteConfirm', noteId: 'n1' })

    expect(next).toEqual(initialNoteListState)
  })

  it('leaves selection mode when the last selected note is toggled off', () => {
    const state = frozen({ ...initialNoteListState, isSelecting: true, selectedIds: new Set(['n1']) })

    const next = noteListReducer(state, { type: 'selectionToggle', noteId: 'n1' })

    expect(next.isSelecting).toBe(false)
    expect(state.selectedIds).toEqual(new Set(['n1']))
  })
})
```

### Mapper and schema

```ts
describe('toNote', () => {
  it('keeps the instant of a date with a non-UTC offset', () => {
    const dto = noteDtoSchema.parse(aNoteDto({ updatedAt: '2026-03-29T01:30:00+02:00' }))

    expect(toNote(dto).updatedAt.toISOString()).toBe('2026-03-28T23:30:00.000Z')
  })

  it('maps a null archivedAt to null instead of the epoch', () => {
    const dto = noteDtoSchema.parse(aNoteDto({ archivedAt: null }))

    expect(toNote(dto).archivedAt).toBeNull()
  })
})
```

Parse fixtures through the generated schema, so the mapper gets exactly what it gets in production. Don't unit-test the generated schemas themselves. Test only a schema the project wrote or extended (like an enum fallback).

---

## Optional verification — mutation testing

Once the suite is green, a mutation-testing pass with Stryker (`@stryker-mutator/core` with the Vitest runner) is the strongest check that it is complete. Run it **only when the user asks for it**. If a mutant survives, either fix the test that should have caught it, or add a test for the missed break vector. A mutant that survives because the behavior isn't observable usually means the unit needs a new observation point.

---

## Anti-patterns

| Anti-pattern | What to do instead |
|---|---|
| `vi.mock('../api/notesApi')` | MSW in an integration test, or pass the dependency in |
| `Date.now()` in a test, or relying on the machine's time zone | `vi.setSystemTime` and a pinned `TZ` |
| Asserting the happy path only | Walk the break-vector catalogue first |
| Only ASCII, only positive numbers, only mid-range values | Every text input gets an emoji/unicode case, every number its boundary case |
| Snapshot of a reducer's output | Assert the fields that changed and the ones that must not |
| Testing a hook with `renderHook` when the Root shows the same behavior | A component test of the Root |
| Several tests failing for the same one-line change | Keep one, spend the others on new angles |
| Writing tests from the implementation you just read | Enumerate break vectors from the contract first |
