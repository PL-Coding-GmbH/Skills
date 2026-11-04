---
name: react-ui-components
description: |
  Building React UI components for SPAs styled with Tailwind CSS v4 and a token-based design system in core/ui that mirrors the Figma Design System and Foundations - Figma variable names as theme tokens, Figma text styles as type utilities, shadcn/ui components copied in and restyled on Radix primitives, the cn helper and cva variants, prop design (className passthrough, native prop spreading, ref as a prop), icons exported from Figma as SVG components, the Icon and IconButton wrappers, slots through children and asChild, theme tokens instead of raw colors or dark: variants, light and dark following the system, user-facing text through react-i18next (namespaces, typed keys, plurals, interpolation, date and number formatting), accessibility basics, and dev-only previews for every design system component. Use this skill whenever writing or changing a component that is not a Root/Screen (buttons, cards, list items, inputs, dialogs, menus, toolbars), adding a design system component, adding an icon, styling with Tailwind, adding translations, or reviewing accessibility. For Root/Screen components, see react-presentation-mvi. Trigger on phrases like "create a component", "Figma component", "SVG", "button", "card", "dialog", "input", "text field", "dropdown", "menu", "shadcn", "Radix", "Tailwind", "className", "cn", "cva", "variant", "icon", "IconButton", "design system", "theme", "color", "dark mode", "token", "translation", "i18n", "t(", "useTranslation", "plural", "format date", "aria-label", "accessibility", "a11y", or "preview".
---

# React UI Components

## Scope

This skill covers every component that is not a page-level Root or Screen: design system components in `src/core/ui/` and feature components in `src/features/<feature>/components/`.

- A component used by one feature lives in that feature.
- It moves to `core/ui` when a second feature needs it. It then loses every feature-specific word: all text comes in through props.

---

## The Design System (`core/ui`)

`core/ui` is the code version of the Figma file's **Design System** page (components) and **Foundations** page (tokens). Figma is the source of truth: a component's variants, sizes, states and slots are the ones in Figma, no more and no fewer.

`core/ui` is the only place that imports Radix. Features import from `@/core/ui/...`, which lint enforces (see **react-project-structure**).

### From Figma to `core/ui`

1. Find the component on the Design System page and read it with the Figma MCP (`get_design_context`, `get_screenshot`). If the MCP call fails, stop and report it. Never build a component from a guess.
2. Build it as described below, with the variants Figma defines.
3. Add a preview section (see [Previews](#previews)).

### shadcn/ui as the base

shadcn/ui components are copied into the project, not installed as a package. They give us Radix behavior (focus handling, keyboard support, ARIA) and a component structure. Their look is replaced with our tokens.

To add one:

1. Generate it with the shadcn CLI (or copy it from the docs) into `src/core/ui/`.
2. Replace every shadcn color and radius class (`bg-primary`, `text-muted-foreground`, `rounded-md` from their scale) with the project's token classes.
3. Rename the file to PascalCase and switch to named exports, `type` and our prop conventions below.
4. Remove variants the Figma component doesn't have, and add the ones it has.
5. Add a preview section (see [Previews](#previews)).

Like Material 3 on Android, the library is the starting point for behavior, not for the visual design.

### `cn` and variants

```ts
// src/core/ui/cn.ts
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

```tsx
// src/core/ui/Button.tsx
const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 rounded-6 type-label transition-colors focus-visible:outline-2 focus-visible:outline-accent disabled:opacity-50',
  {
    variants: {
      variant: {
        primary: 'bg-accent text-background-surface',
        secondary: 'bg-background-surface text-text-primary border border-border-strong',
        ghost: 'text-text-primary hover:bg-accent-soft',
        danger: 'bg-danger text-background-surface',
      },
      size: {
        md: 'h-10 px-4',
        lg: 'h-12 px-5',
      },
    },
    defaultVariants: { variant: 'primary', size: 'md' },
  },
)

type ButtonProps = ComponentProps<'button'> &
  VariantProps<typeof buttonVariants> & {
    isLoading?: boolean
    asChild?: boolean
  }

export function Button({ variant, size, isLoading, asChild, className, children, disabled, ...props }: ButtonProps) {
  const Component = asChild ? Slot : 'button'
  return (
    <Component
      className={cn(buttonVariants({ variant, size }), className)}
      disabled={disabled || isLoading}
      aria-busy={isLoading || undefined}
      {...props}
    >
      {children}
    </Component>
  )
}
```

- The classes above show the token names. The real variants, sizes and styles come from the Button in Figma.
- Variants use `cva`, as shadcn does. Variant names follow the Figma variant names and describe purpose (`primary`, `danger`), not color (`blue`).
- If `twMerge` doesn't resolve a conflict between two custom utilities (a custom type style and a font size, say), register them with `extendTailwindMerge` in `cn.ts`.

---

## Styling with Tokens

- **Colors, radii, spacing, breakpoints and type styles come only from the theme.** The theme replaces Tailwind's default palette, so `bg-blue-500` produces no CSS.
- **No raw values.** No hex colors in components, no arbitrary values like `bg-[#fff]` or `p-[13px]`. Arbitrary values can't be blocked by lint, so review catches them.
- **No `dark:` variants.** Each token class points at a CSS variable, and the theme swaps the variable values under `prefers-color-scheme: dark`. `bg-background-surface` is correct in both themes. The theme always follows the system. There is no in-app theme switch.
- The theme lives in `src/core/ui/theme/`. Read values with the Figma MCP (`get_variable_defs`), never from screenshots.

### Token names come from Figma

Every theme token is named after its Figma variable: `/` becomes `-`, and a trailing `/default` is dropped.

| Figma variable | Theme variable | Example class |
|---|---|---|
| `background/app`, `background/surface`, `background/column`, `background/sidebar` | `--color-background-app`, ... | `bg-background-surface` |
| `text/primary`, `text/muted`, `text/faint` | `--color-text-primary`, ... | `text-text-muted` |
| `border/default`, `border/strong` | `--color-border`, `--color-border-strong` | `border-border` |
| `accent/default`, `accent/soft` | `--color-accent`, `--color-accent-soft` | `bg-accent-soft` |
| `danger/default`, `success/default` | `--color-danger`, `--color-success` | `text-danger` |
| `label/red` ... `label/slate` (20 label colors) | `--color-label-red`, ... | `bg-label-red` |
| `radius/4` ... `radius/12`, `radius/full` | `--radius-4`, ... | `rounded-8`, `rounded-full` |

- **Spacing** uses Figma's steps only: 4, 8, 12, 16, 20, 24 and 32 px. With a 4 px spacing base these are `1`, `2`, `3`, `4`, `5`, `6` and `8` (`p-3`, `gap-2`). Don't use other steps.
- **Type styles are utilities** named after the Figma text styles: `type-page-title`, `type-screen-title`, `type-card-title`, `type-body`, `type-label`, `type-metadata`, `type-section-label`. Each one sets font family (Geist or Geist Mono), size, weight, line height and letter spacing, including the larger phone sizes Figma lists. Don't combine `text-*` size, `font-*` weight and `leading-*` by hand.
- **Breakpoints** come from Figma Foundations: `tablet` from 640 px, `desktop` from 1024 px. They are marked as a proposal in Figma, so they are defined only in the theme and nowhere else.
- When Figma adds or renames a variable, update the theme in the same change. Never add a token that has no Figma variable.

---

## Prop Design

```tsx
type NoteCardProps = {
  note: Note
  isSelected: boolean
  onSelectedChange: (selected: boolean) => void
  className?: string
}
```

- **Props in order:** required data first, then state, then callbacks, then `className`.
- **`className` is the `Modifier`.** Every component that renders an element accepts `className` and merges it onto the outer element with `cn`. The parent controls placement and spacing (margin, width, grid position). The component controls its own look.
- **Wrapping a native element:** take `ComponentProps<'button'>` (or the element in question) and spread the rest onto it, so `type`, `aria-*`, `data-*` and event handlers pass through.
- **`ref` is a regular prop** in React 19. No `forwardRef`. Input components must pass `ref` to the `input` so React Hook Form's `register` works.
- **Booleans** read as a state: `isSelected`, `isLoading`. Native names stay native: `disabled`, `required`.
- **Callbacks** are `on<Event>`: `onClick`, `onSelectedChange`. A controlled value is `value` + `onValueChange` (or `open` + `onOpenChange`), matching Radix.
- **Pass the smallest thing the component needs.** A component that shows a title and a date gets `title` and `updatedAt`, or the domain object if it really uses most of it. Never pass a query result object or the whole screen state.

### Local state

Components may hold state that only affects how they look: hover, a menu being open, a tooltip, which tab of a self-contained widget is active. Make it controlled (`open`/`onOpenChange`) only when a parent needs to drive it. Radix components already manage their own open state when uncontrolled.

---

## Icons

```tsx
<Icon icon={PlusIcon} />                                  // default size, hidden from screen readers
<Icon icon={StarIcon} label={t('notes:favorite')} />
<IconButton icon={TrashIcon} label={t('notes:delete')} onClick={...} />
```

Icons are SVGs exported from Figma. There is no icon library.

```tsx
// src/core/ui/icons/TrashIcon.tsx
export function TrashIcon(props: ComponentProps<'svg'>) {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" {...props}>
      <path d="..." />
    </svg>
  )
}
```

- One file per icon in `src/core/ui/icons/`, named `<Name>Icon.tsx` after the Figma icon. Add an icon when a feature first needs it, exported from Figma with the MCP. Never draw or copy an icon from somewhere else.
- Replace every hard-coded fill and stroke color with `currentColor`. Keep the `viewBox` from Figma, remove fixed `width` and `height`.
- Icons are rendered through `Icon` or `IconButton` from `core/ui`, which limit size to the design system's options. Never render an icon component directly.
- An icon next to visible text has no label and is hidden from assistive technology.
- An icon-only button requires `label`. `IconButton` makes it a required prop, so a missing label is a type error.
- Icon color follows the text color (`currentColor`). Set color on the parent with a token class.

---

## Slots

- `children` is the main slot.
- Named slots are `ReactNode` props: `leading`, `trailing`, `actions`.
- To render a design system component as another element, use Radix's `asChild` (`<Button asChild><Link to="/notes">...</Link></Button>`). That keeps the link a real link with button styling.

---

## Text and Translations

All user-facing text comes from translation files through react-i18next. Text only shown on the dev-only preview page is exempt.

```tsx
const { t } = useTranslation('notes')

<h2>{t('list.title')}</h2>
<p>{t('list.count', { count: notes.length })}</p>
<p>{t('list.updated', { date: note.updatedAt })}</p>
```

```json
{
  "list": {
    "title": "Notes",
    "count_one": "{{count}} note",
    "count_other": "{{count}} notes",
    "updated": "Updated {{date, datetime(dateStyle: medium)}}"
  }
}
```

- **One namespace per feature**, named after the feature, plus a shared `common` namespace. A feature adds its English JSON together with the feature.
- **Keys are typed.** The i18next type declaration is derived from the English resources, so a key that doesn't exist fails `npm run typecheck`.
- **No concatenation.** `t('a') + name + t('b')` breaks in languages with a different word order. Use interpolation.
- **Plurals** use `count` and `_one` / `_other` suffixes. Other languages add the forms they need (`_few`, `_many`).
- **Dates and numbers** are formatted with i18next's built-in formatters (`datetime`, `number`, `relativetime`, `list`), which use `Intl` and the active language. Outside `t`, use `Intl.DateTimeFormat(i18n.resolvedLanguage, ...)`. Never format with a fixed locale or by hand.
- **`core/ui` components don't call `t` for content.** Labels and messages come in as props. Generic words (a "Close" label on a dialog) may come from `common`.
- **Schema messages are translation keys.** Zod error messages in form schemas are keys like `'notes:form.titleRequired'`. `useTranslatedError()` from `core/i18n` turns them into text. It's the one place that translates a key that isn't known at compile time.
- Rich text with markup in a translation uses the `Trans` component, never `dangerouslySetInnerHTML`.

---

## Accessibility

- Every interactive element has an accessible name: visible text, a `<label>`, or `aria-label` for icon-only controls.
- Inputs have a visible `<label>` connected with `htmlFor` and `useId`. Error text is linked with `aria-describedby` and the input gets `aria-invalid`.
- Focus is always visible. Never remove the focus outline without a `focus-visible:` replacement.
- Use Radix-based components for dialogs, menus, popovers, tabs and tooltips. Don't hand-build them.
- Don't use color alone to convey state. Add an icon or text.
- Disabled buttons that should still explain themselves use `aria-disabled` and a tooltip instead of `disabled`.

---

## Previews

Every `core/ui` component has a section on the dev-only design system preview page. It shows each variant, each size and each meaningful state: default, disabled, loading, with an error, with long text that has to wrap or truncate, and with and without optional slots.

- The preview page is a second Vite HTML entry that the production build doesn't include. It shows the active OS theme, so check both.
- Feature components and Screens don't get previews. Their component tests cover their states (see **react-integration-testing**).

---

## Checklist: Building a Component

- [ ] Lives in the feature, or in `core/ui` if a second feature needs it
- [ ] Read from Figma with the MCP, with exactly the variants, sizes and states Figma defines
- [ ] Design system components start from shadcn/Radix and are restyled with tokens
- [ ] Only token classes named after Figma variables, no raw colors, no arbitrary values, no `dark:`
- [ ] Accepts `className` merged with `cn` on the outer element, spreads native props where it wraps an element
- [ ] Variants with `cva`, named by purpose
- [ ] Icons exported from Figma, `currentColor`, rendered through `Icon`/`IconButton`, icon-only buttons have a label
- [ ] All text from translation files, plurals and formatting through i18next
- [ ] Accessible name, label, visible focus, keyboard support
- [ ] `core/ui` components have a preview section covering every variant and state
