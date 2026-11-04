---
name: react-project-structure
description: |
  Folder layout, dependency rules, lint-enforced import boundaries, file naming, code style, npm dependency handling, and verification gates for client-side React SPAs built with Vite and TypeScript (feature folders with api/components/hooks, a shared core, and src/app as the wiring layer). Use this skill whenever creating a new feature, deciding where a file belongs, adding a shared module to core, wiring an app-wide provider, adding or updating an npm package, changing lint boundaries, or making any project-level architecture decision. Trigger on phrases like "add a feature", "where does X live", "project structure", "folder structure", "how should I structure", "shared code", "core", "import boundary", "no-restricted-imports", "oxlint", "add a dependency", "npm install", "path alias", "provider", "barrel file", or "verification gates".
---

# React Project Structure

## Core Philosophy

- **Feature-first.** Code lives in the feature that uses it. It moves to `core` only when a second feature needs it.
- **Features never import each other.** Shared models, components and helpers go to `core`. Cross-feature navigation uses typed links to routes (see **react-routing**), not imports.
- **`src/app` is the only place that knows every feature.** It holds the router, the route files, app-wide providers and the app shell.
- **Boundaries are enforced by the linter, not by review.** Every rule that can be a lint rule is one, and a test proves the lint rules still catch their cases.

---

## Folder Layout

```
api/
  openapi.json          # committed copy of the backend's OpenAPI spec (see react-data-layer)
src/
  main.tsx              # entry point: imports global CSS, i18n init, renders <App />
  index.css             # Tailwind entry + theme import
  testSetup.ts          # Vitest setup (jest-dom matchers, MSW server, cleanup)
  app/
    App.tsx             # app-wide providers + RouterProvider
    router.ts           # createRouter, router context, Register augmentation
    routes/             # TanStack Router file routes (thin, see react-routing)
    routeTree.gen.ts    # generated, committed, excluded from lint and Prettier
  core/
    api/                # HTTP client, DataError, QueryClient factory, shared API code
      generated/        # Zod schemas and DTO types generated from api/openapi.json, excluded from lint and Prettier
    auth/               # session state, token handling, auth guard helpers
    ui/                 # design system: components, Icon, icons/ (one component per Figma icon), theme tokens
    i18n/               # i18next setup, translation files, test helper
    utils/              # small pure helpers used by several features
  features/<feature>/
    api/                # API functions, mappers, query and mutation definitions
    components/         # Root + Screen components and feature components
    hooks/              # view-model hooks, reducers, other feature hooks
    utils/              # pure feature logic (validation, sorting, calculations)
    types.ts            # the feature's domain types
```

A feature only creates the folders it needs. A feature with one type keeps `types.ts`. A feature with many may use a `types/` folder.

Create a new folder in `core` only for a self-contained concern with real substance (several files, its own API). A single helper goes into an existing `core` folder.

### Dependency direction inside a feature

```
components  ->  hooks  ->  api  ->  types
     \___________\__________\____->  utils
```

- `types.ts` imports nothing from the feature's other folders.
- `api/` never imports from `components/` or `hooks/`.
- Components may import query options from `api/` directly when they don't need a view-model hook.
- Only `api/` imports from `@/core/api/generated`. Components, hooks and `types.ts` work with domain types.

This direction is a convention, checked in review. The cross-feature and core rules below are lint errors.

---

## Dependency Rules

| From | May import |
|---|---|
| `src/app` | everything |
| `src/features/<x>` | its own files (relative imports), `@/core/**`, npm packages except the ones wrapped by `core/ui` |
| `src/core` | other `@/core/**` folders, npm packages |

- **No `@/features/...` import inside a feature.** Inside a feature, imports are relative (`../api/notesApi`). That turns "don't import another feature" into "never write `@/features` in a feature", which needs no per-feature config.
- **No `@/app/...` import outside `src/app`.**
- **Features use `@/core/ui` instead of the libraries it wraps** (`@radix-ui/*`). See **react-ui-components**.

### Enforcing with oxlint

`.oxlintrc.json` uses `no-restricted-imports` in folder `overrides`:

```json
{
  "overrides": [
    {
      "files": ["src/core/**"],
      "rules": {
        "no-restricted-imports": ["error", { "patterns": [
          { "group": ["@/app", "@/app/**", "@/features", "@/features/**"], "message": "core must not import from app or features." },
          { "regex": "^(\\.\\./)+(app|features)(/|$)", "message": "core must not import from app or features." }
        ] }]
      }
    },
    {
      "files": ["src/features/**"],
      "rules": {
        "no-restricted-imports": ["error", { "patterns": [
          { "group": ["@/app", "@/app/**", "@/features", "@/features/**"], "message": "Features must not import from app or other features. Use relative imports inside a feature." },
          { "regex": "^(\\.\\./)+app(/|$)", "message": "Features must not import from app." },
          { "group": ["@radix-ui/*"], "message": "Use the components from @/core/ui instead." }
        ] }]
      }
    }
  ]
}
```

- oxlint overrides **replace** a rule's options for matching files instead of merging them. An override for a sub-folder must repeat every pattern of its parent folder.
- A relative import that climbs into another feature (`../../other/api/x`) is not caught. Review catches it.

### Testing the lint rules

The lint config is the only enforcement of the architecture, so it has a test (like a Konsist or ArchUnit test). `src/app/lintBoundaries.test.ts`:

1. Copies `.oxlintrc.json` into a temp directory.
2. Writes small fixture files at `src/...` paths, one per forbidden and one per allowed import.
3. Runs `oxlint --format json` there and asserts each forbidden fixture reports the expected rule and each allowed one reports nothing.

When you add or change a boundary rule, add a forbidden and an allowed fixture for it.

---

## Wiring in `src/app`

There is no DI container. Feature code imports API functions and query options directly, and tests intercept HTTP with MSW (see **react-integration-testing**). React Context is only for objects that are truly app-wide:

```tsx
// src/app/App.tsx
export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  )
}
```

- `App.tsx` is the one place providers are added, like assembling Koin modules in `Application.onCreate`.
- Objects the route loaders need (`queryClient`) go into the router context, set in `createAppRouter` (see **react-routing**).
- Don't add a Context to swap implementations for tests. Fake the network with MSW instead.

---

## File Naming and Code Style

| Thing | Convention | Example |
|---|---|---|
| Component file | PascalCase, named after its main component | `NoteListScreen.tsx`, `NoteCard.tsx` |
| Hook file | `useXxx.ts` | `useNoteListViewModel.ts` |
| Other modules | camelCase | `notesApi.ts`, `noteMapper.ts`, `notesQueries.ts` |
| Tests | next to the file, `.test.ts(x)` | `noteMapper.test.ts` |
| Route files | TanStack Router file naming | `routes/notes/$noteId.tsx` |

- **Named exports only.** Default exports only where a tool requires one (config files). Enforced by `import/no-default-export`.
- **`type`, not `interface`.** Enforced by `typescript/consistent-type-definitions`. Module augmentation (`declare module`) is the one place an `interface` is required. Disable the rule for that line with a short comment saying why.
- **No `any`.** Use `unknown` and narrow. Enforced by `typescript/no-explicit-any`.
- **No TypeScript `enum`.** Use string literal unions. `erasableSyntaxOnly` makes `enum` a compile error.
- **Function components only.**
- **No barrel files** (`index.ts` that re-exports a folder). Import the file you need. Barrels hide circular imports and slow down the dev server's hot reload. Icons are one file each (`@/core/ui/icons/PlusIcon`), not re-exported from an index.
- **Path alias `@/` maps to `src/`.** Use it for anything outside the current feature. Use relative imports inside a feature.
- Prettier decides formatting. Don't hand-format.

### tsconfig baseline

`strict`, `noUncheckedIndexedAccess`, `noUnusedLocals`, `noUnusedParameters`, `erasableSyntaxOnly`, `verbatimModuleSyntax`, `noFallthroughCasesInSwitch`. Test files are excluded from the app tsconfig and type-checked by a separate `tsconfig.test.json` that adds Node types.

---

## npm Dependencies

- Add a package in the change that first needs it, not ahead of time.
- Use `npm install <pkg>` (or `-D` for tooling and test libraries). Commit `package-lock.json`.
- Check that a new package supports the installed major versions of React, Vite and TypeScript before adding it.
- Prefer the platform over a package: `fetch` instead of axios, `Intl` instead of a date-formatting library, `crypto.randomUUID()` instead of `uuid`.
- When several parallel changes need new packages, add them all in one early PR. `package.json` is the file most likely to conflict.

---

## Verification Gates

Every PR must pass:

| Command | What it checks |
|---|---|
| `npm run typecheck` | `tsc -b` over app and test tsconfigs, including translation keys and route paths |
| `npm run lint` | oxlint, including import boundaries |
| `npm run format:check` | Prettier |
| `npm test` | Vitest unit and component tests |
| `npm run build` | production build |

Playwright E2E tests are not a merge gate (see **react-integration-testing**).

---

## Checklist: Adding a New Feature

- [ ] Create `src/features/<feature>/` with only the folders it needs
- [ ] Domain types in `types.ts`, API functions and mappers in `api/`, using the generated DTO schemas (see **react-data-layer**)
- [ ] Query keys, query options and mutations in `api/<feature>Queries.ts` (see **react-server-state**)
- [ ] Root + Screen components in `components/`, view-model hook in `hooks/` (see **react-presentation-mvi**)
- [ ] Route files in `src/app/routes/` that render the feature's Root (see **react-routing**)
- [ ] Translation namespace for the feature (see **react-ui-components**)
- [ ] Code needed by a second feature moved to `core`, not imported across features
- [ ] All five gates pass
