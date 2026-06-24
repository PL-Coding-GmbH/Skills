---
name: kotlin-mutation-testing
description: |
  Audit how well a Kotlin test class covers its production code with
  model-driven mutation testing. The skill modifies the production code
  the test class exercises with a small behavior-changing edit, reruns
  the entire test class, and flags any mutation no test in the class
  caught — surfacing under-tested production behavior. Works on Android,
  KMP, and plain JVM Kotlin projects. Use this skill ONLY when the user
  explicitly asks for mutation testing — e.g. "mutation test", "run a
  mutation test", "mutation-test these tests", "do a mutation testing
  pass", or otherwise names mutation testing directly. Do NOT trigger
  for general unit-testing requests, ordinary requests to write, review,
  audit, or verify tests, or generic "check my test quality" / "are my
  tests good" asks that don't mention mutation testing.
---

# Kotlin Mutation Testing

Audit a Kotlin test class by breaking the production code it exercises, then checking whether the suite of tests in that class catches the break. Mutations that survive the **whole** class point at production behavior the suite does not constrain.

This is not a full AST-level mutator like Pitest — it's a focused, model-driven audit. You read the production code, pick contextually meaningful mutations, run all tests in the class against each mutation, and report the survivors. The point is to find under-tested production paths, not to grade individual tests.

> **One mutation is judged by the whole class, not by one test.** A mutation is *killed* if at least one test in the test class fails. A mutation is *survived* if every test still passes. Never scope the test run to a single method.

---

## Inputs

The user provides one test class, as either:

- A file path (e.g., `feature/notes/src/commonTest/kotlin/.../NoteListViewModelTest.kt`), or
- A fully qualified class name (e.g., `com.plcoding.notes.NoteListViewModelTest`).

If the user provides only a class name, resolve the file with `find` or `grep -r "class NoteListViewModelTest"` before proceeding.

If the user gives a whole module or directory, stop and ask them to pick a single test class. This skill works one class at a time on purpose — the output must stay reviewable.

---

## Preflight

### 1. Confirm git is clean for production files

The skill mutates production code and restores it with `git checkout --`. If the user has uncommitted changes in the files the skill would touch, restoration would destroy their work.

```bash
git status --porcelain
```

If any file under `src/main/`, `src/commonMain/`, `src/androidMain/`, `src/jvmMain/`, `src/iosMain/`, or `src/desktopMain/` in the module under test is listed as modified, staged, or untracked: **stop**. Tell the user which files are dirty and ask them to commit or stash before retrying. The test file itself may be dirty — the skill never edits test sources.

### 2. Detect the module

Walk up from the test file until you hit a `build.gradle.kts` (or `build.gradle`). The Gradle module path is the directory path with `/` replaced by `:`. Examples:

- `feature/notes/build.gradle.kts` → `:feature:notes`
- `app/build.gradle.kts` → `:app`

### 3. Detect the test task

From the same `build.gradle.kts`:

- If it applies `com.android.library` or `com.android.application` → use `:module:testDebugUnitTest` for unit tests under `src/test/` or `src/commonTest/`.
- Otherwise → use `:module:test`.
- For KMP modules, prefer `:module:jvmTest` for JVM-only targets. For `commonTest` code that runs on multiple targets, pick the JVM variant unless the user says otherwise.
- Instrumented tests (under `src/androidTest/`, using `ComposeTestRule` on a device, or annotated with `@RunWith(AndroidJUnit4::class)` and reading from actual Android framework) **require a connected device**. If one is not available, skip those test classes with a clear note rather than running.

---

## Workflow

The unit of work is **one mutation**, not one test. For the chosen test class, enumerate a set of meaningful mutations against the production code those tests exercise, then for each mutation: apply it, run the whole class, classify the result, restore the file, move on.

**Restoring the file is mandatory on every exit path**, including exceptions, compile errors, and user cancellation.

### Step 1 — Map the production surface the class exercises

Read every `@Test`-annotated method in the class. From all of them collected together, write down:

- **Production classes / functions imported** from non-test source sets → the candidates to mutate.
- **Methods, properties, branches, and return values actually reached** by the tests → where mutations should land.
- **Assertion shape** used by the suite → equality on enums, list equality, `assertTrue`, `verify` calls, etc. This shapes which mutations the suite *could* catch.
- **Test type**:
  - **Unit** — only fakes/mocks, pure logic, no framework dependencies, no real DB/HTTP/UI.
  - **Integration** — real collaborators wired together (in-memory Room, MockWebServer, real repository over a fake data source).
  - **E2E / UI** — `ComposeTestRule`, instrumented, drives a real UI flow.

### Step 2 — Read the production code

Never pick mutations from the test alone. Open the production file(s) and locate every branch, comparator, return, and side effect the test class touches. Mutations must be chosen against *real* behavior, not guessed.

### Step 3 — Plan the mutations

Build a list of small, behavior-changing edits. Each entry should:

- Touch **one line or one token**.
- Have a clear behavioral consequence (a correct suite *would* catch it).
- Cover a different point in the production code — don't pile up redundant variants of the same edit.

Aim for breadth: every guard, every comparator, every return value, every collection operation the suite touches should appear at least once.

A mutation is valid only if **a correct suite would definitely catch it**. If you can't state in one sentence why the suite should fail, pick a different one.

See the [Mutation catalog](#mutation-catalog) below for concrete choices.

### Step 4 — For each mutation, apply → run class → classify → restore

For every mutation in the list:

1. **Apply** with `Edit` — change exactly one line or one token. The diff must be small enough for the user to verify at a glance in the final report.
2. **Run the entire test class**:
   ```bash
   ./gradlew :module:test --tests "com.example.MyClassTest"
   ```
   - For Android modules use `:module:testDebugUnitTest` instead of `:module:test`.
   - For KMP modules with a JVM target use `:module:jvmTest`.
   - Always scope with `--tests "ClassName"` (no method suffix). Running the whole class is the entire point: the suite's job is to catch the mutation collectively. Filtering down to one method defeats the audit.
3. **Classify** with the table below.
4. **Restore** the production file:
   ```bash
   git checkout -- <relative/path/to/ProductionFile.kt>
   ```
   Verify restoration worked by re-running `git status --porcelain` for the touched file — the line must disappear. If it doesn't, stop the audit and tell the user.

Never mutate:
- Test sources (`src/test/`, `src/commonTest/`, `src/androidTest/`, `src/jvmTest/`, etc.).
- Files outside the module the test belongs to.
- Generated code (anything under `build/`).

### Step 5 — Classify the result

| Outcome                     | Meaning                                                                          | Action                                                                  |
|-----------------------------|----------------------------------------------------------------------------------|-------------------------------------------------------------------------|
| At least one test fails     | Mutation **killed** by the class. Note which test(s) failed.                      | Restore file, mark mutation as killed, continue.                        |
| Every test passes           | Mutation **survived**. The class does not constrain this production behavior.    | Restore file, flag the mutation as a coverage gap, continue.            |
| Compile error               | Mutation was not well-formed.                                                    | Restore file, pick a different mutation. Don't count as a result.       |
| Build failure (unrelated)   | Something broke outside the test class (e.g., KSP, dependencies).                | Restore file, stop the audit, report the failure.                       |
| Timeout                     | Gradle stalled or test hung.                                                     | Restore file, skip with note.                                           |

### Step 6 — Equivalent mutations

Some mutations don't change observable behavior — for example, `password.length < 9` vs. `password.length <= 8` are mathematically identical. If a mutation survives, ask: *is there any input on which this produces a different program?* If no, mark it **equivalent**, not survived. Equivalent mutations are not coverage gaps; they're impossible to kill by definition.

### Step 7 — When to skip mutations

Some production lines aren't usefully mutatable. Skip (don't include) in these cases:

- The line only constructs a data class or returns a constant the test class never reads.
- The branch is behind a DI graph the skill can't resolve from static reading alone (e.g., a platform-specific `expect/actual` whose `actual` lives in a sibling module).
- The line calls into a third-party library where mutating the user's code wouldn't change observable behavior.
- Instrumented test class and no connected device → skip the whole audit.

Note any skipped lines in the final report with their reason.

---

## Mutation catalog

Think in terms of *what behavior the line encodes*, not *what pattern matches*. Common cases:

| What the line encodes                  | Mutation to try                                                                         |
|----------------------------------------|------------------------------------------------------------------------------------------|
| A boolean condition gates behavior     | Flip the condition: `if (x > 0)` → `if (x <= 0)`, or replace with `if (true)` / `if (false)`. |
| A comparator picks the right branch    | Swap the operator: `<` ↔ `>=`, `==` ↔ `!=`. Also: `<` → `<=` to probe boundary inclusion. |
| An arithmetic result                   | Swap the operator: `+` → `-`, `*` → `/`, or replace RHS with `0`.                        |
| A return value (enum / sealed type)    | Replace with every other valid value of the same type, one at a time.                    |
| A state update (`_state.update { ... }`) | Remove the `.copy(field = newValue)` field change, or replace with `it.copy()` (no-op).  |
| An emission on a Flow / Channel        | Swap `emit(x)` for `emit(defaultValue)`, or comment out the `emit` line entirely.        |
| A side effect (save, log, schedule)    | Comment out the call.                                                                    |
| An exception thrown for bad input      | Replace `throw …` with `return` / `return defaultValue`.                                 |
| A mapping/transformation               | Replace `items.map { transform(it) }` with `items` (identity), or flip which field is mapped. |
| A collection filter                    | Remove the `.filter { … }` call.                                                         |
| A collection accumulator (`errors += X`) | Comment out the `+=` line — does the suite notice the missing entry?                    |
| Rule ordering in a sequence of guards  | Swap two adjacent guard blocks — does any test depend on the order?                      |

Rule of thumb: **one line or one token**. If your mutation needs more, you're probably mutating the wrong thing — re-read the production code and pick a tighter target.

---

## Final report

After every planned mutation has been processed, print this markdown report to the user:

```markdown
# Mutation testing report — com.example.MyClassTest

- Mutations applied: 14
- Killed: 11
- Survived: 2
- Equivalent: 1

## Survived mutations (coverage gaps)

### Mutation 1
- **File**: `feature/notes/src/main/kotlin/.../NoteRepository.kt:42`
- **Before**: `if (note.isArchived)`
- **After**: `if (!note.isArchived)`
- **Why the class missed it**: no test in the class exercises the archived branch with an unarchived note; every test passes archived notes only.
- **Suggested test**: a case that constructs an unarchived note and asserts it is not deleted.

### Mutation 2
- **File**: `…`
- **Before**: …
- **After**: …
- **Why the class missed it**: …
- **Suggested test**: …

## Equivalent mutations

### Mutation X
- **File**: `…:N`
- **Before**: `password.length < 9`
- **After**: `password.length <= 8`
- **Justification**: equivalent for all integer inputs; no test could distinguish.
```

The **Why the class missed it** line is the most valuable part of the report — it turns a raw "this mutation survived" signal into an actionable suggestion. Write one sentence that names which production behavior is unconstrained, and one sentence that sketches the missing test.

---

## Anti-patterns

- **Don't edit test code.** The only way to audit the suite fairly is to leave it untouched.
- **Don't scope the test run to a single method.** Every mutation must be evaluated against the whole test class — a mutation killed by *any* test is killed.
- **Don't mutate more than one place at a time.** Compound mutations make the diff unreviewable and confuse classification.
- **Don't skip the restore.** A crashed audit that leaves the repo mutated is worse than no audit at all. Verify with `git status --porcelain` between every mutation.
- **Don't invent a mutation you can't justify.** If you can't explain in one sentence why a correct suite should catch the change, pick a different one or skip the line.
- **Don't silently pass when the build fails.** A compile error is not a killed mutation; it's a bad mutation.
- **Don't conflate survived with equivalent.** A survived mutation is a real coverage gap; an equivalent mutation cannot be killed by definition. Treat them separately in the report.
