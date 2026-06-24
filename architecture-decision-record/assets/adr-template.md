---
# Metadata block — OPTIONAL. Delete the whole front matter for a minimal ADR,
# or keep only the fields you need. `deciders`, `consulted`, `informed` are all optional.
status: "{proposed | rejected | accepted | deprecated | superseded by NNNN}"
date: { YYYY-MM-DD }
deciders: { who is accountable for the decision } # optional
consulted: { experts consulted, two-way } # optional
informed: { stakeholders kept in the loop, one-way } # optional
---

# {Short title — the problem solved and the chosen solution}

## Context and Problem Statement

{Two or three sentences describing the situation and the problem that forces a decision.
Often best phrased as a question. Give enough context that a newcomer understands why a
choice was needed.}

## Decision Drivers <!-- OPTIONAL (recommended) — delete if unused -->

- {driver / force / constraint, e.g. legal or compliance risk}
- {driver, e.g. fear of a user-data breach → security requirement}
- {driver, e.g. team skills, cost, performance, time-to-market}

## Considered Options

- {option 1}
- {option 2}
- {option 3}

## Decision Outcome

Chosen option: "{option}", because {justification — tie it back to the decision drivers}.

### Consequences

- Good, because {positive consequence}.
- Good, because {positive consequence}.
- Bad, because {negative consequence / cost / risk taken on}.
- Neutral, because {consequence that is neither clearly good nor bad}. <!-- optional line -->

### Confirmation <!-- OPTIONAL — delete if unused -->

{How the implementation of this decision is validated and enforced — e.g. code review,
automated tests, an architecture fitness function in CI, a linter rule.}

## Pros and Cons of the Options <!-- OPTIONAL — delete if unused -->

### {option 1}

- Good, because {argument}.
- Neutral, because {argument}.
- Bad, because {argument}.

### {option 2}

- Good, because {argument}.
- Bad, because {argument}.

## More Information <!-- OPTIONAL — delete if unused -->

{Links to related ADRs or docs, evidence gathered, degree of team agreement, confidence
level, and when this decision should be revisited. Note "Supersedes NNNN" here if applicable.}
