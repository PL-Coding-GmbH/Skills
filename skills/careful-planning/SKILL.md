---
name: careful-planning
description: Interview the user with single- and multiple-choice questions until every decision behind a feature or change is settled, then record the result in decisions.md. Use before writing OpenSpec proposals or specs, when a feature should be planned in detail, or when the user says "careful planning".
---

# Careful Planning

Your goal is a shared understanding of the change with nothing left silently
assumed. You find the facts; the user makes the decisions. This skill does not
write proposals, specs, designs or code.

## Think in a decision tree

Every decision opens follow-up decisions that only make sense once it is
settled. Example: "Can users edit a submitted order?" → if yes, "Until when?"
→ "What happens to an already captured payment?"

Keep this tree up to date for the whole session. A decision is **ready** when
everything it depends on is settled. All ready decisions together form the
**frontier**: the questions you can ask now without guessing at answers you
have not heard yet.

## Before the first round

- Read what already exists: `openspec/specs/`, the specs of referenced stores
  (listed by `openspec instructions`; fetch them with
  `openspec show <spec-id> --type spec --store <store>`), the change folder,
  and the code the change touches.
- Anything already settled in this conversation (for example during
  `/opsx:explore`) counts as settled. Do not ask it again, but record it.

## Work in rounds

1. Compute the frontier. Leave out any question whose answer depends on
   another question that is still open in this round; it belongs to a later
   round.
2. Ask the whole frontier with the AskUserQuestion tool. One call holds up to
   four questions. If the frontier is larger, make several calls in the same
   round, most fundamental questions first.
3. Wait for the answers. Update the tree: settled decisions unblock the
   questions that hang off them. Recompute the frontier and start the next
   round.

Never decide on the user's behalf. Never ask in plain text what can be asked
with AskUserQuestion.

## How to write a question

- **question**: one decision per question, ending with a question mark.
  Include the context needed to decide, such as what currently happens or what
  each choice would cause.
- **header**: a short topic tag, at most 12 characters (e.g. "Edit window").
- **options**: 2–4 genuinely different choices. Labels of 1–5 words, each with
  a one-line description of its consequence or trade-off.
- **Recommendation**: put your recommended option first and end its label with
  "(Recommended)", so accepting it is one click. Leave the marker off only when
  the choice is purely a matter of taste.
- **multiSelect**: only when the options are not mutually exclusive (e.g.
  "Which platforms need this?").
- **preview**: use it when comparing concrete shapes helps, such as API
  payloads, data models or screen layouts.
- Offer "Decide later" or "Out of scope" as an option only where that is a
  realistic answer.
- Never add your own "Other" option; the tool always provides one. If the user
  answers via "Other", treat their text as the decision. If it is ambiguous,
  ask a follow-up in the next round.

## Facts are your job

Never ask the user for something you can look up: how the current code
behaves, what an existing spec says, which endpoints or fields exist. For
anything beyond a quick lookup, dispatch a sub-agent with a fresh context
(for example the Explore agent) to find it.

Do not block the round on it. A running lookup is just an unsettled
prerequisite: only the questions that depend on it wait. Ask the rest of the
frontier now. Record each fact with its source.

## Check coverage before you stop

An empty frontier only proves that the branches you opened are closed. Before
finishing, make sure each of these areas is decided, confirmed as not
applicable, or explicitly out of scope, and open new questions for any that
are not:

- Main flow and who can trigger it
- Input validation and limits
- Error, empty and edge states
- Loading, offline and slow-network behavior
- Authentication and permissions
- Data lifecycle: create, edit, delete, and migration of existing data
- Differences between backend, web and mobile
- Side effects: notifications, emails, analytics, other systems
- Backward compatibility and breaking changes
- What is explicitly out of scope

## Finish

1. When the frontier is empty and coverage is complete, show a summary in the
   chat with one line per decision.
2. Ask with AskUserQuestion whether this is the shared understanding. Options:
   "Yes, record it (Recommended)" and "No, revise something". On "No", ask
   which decisions to revisit and continue with new rounds.
3. Only after a "Yes", write `decisions.md`. Inside an OpenSpec change, write
   it to the change folder and follow the template OpenSpec provides for the
   decisions artifact. Outside a change, ask where to save it. Write the file
   only at this point: OpenSpec treats the artifact as complete as soon as the
   file exists.

Do not continue with proposals, specs or code inside this skill. Hand back to
the workflow that called it.