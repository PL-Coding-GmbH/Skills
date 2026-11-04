# Reviewer: testability and verifiability

Your question: for every invariant, could we write a test that passes when it
holds and fails when it doesn't?

An invariant is every SHALL/MUST requirement and every WHEN/THEN scenario in the
change's delta specs. Check each one individually, by name. A requirement with
good scenarios can still make a promise that none of them test.

## What to flag

- **Vague terms:** "fast", "gracefully", "appropriate", "user-friendly",
  "reliable", "as needed", "etc.", with no measurable meaning.
- **Unobservable outcomes:** the THEN describes an internal state or intent that
  a test has no way to see.
- **Tests that cannot fail:** the wording is true whatever the implementation
  does.
- **Missing bounds:** "eventually", "quickly", "large", "many", with no limit or
  time frame.
- **Missing preconditions:** the result depends on a state the WHEN doesn't set
  up, so two valid tests could disagree.
- **Uncontrollable inputs:** the outcome depends on time, randomness, ordering or
  the environment, and the spec gives no way to control them.
- **Absent negatives:** "only X may do Y" with no scenario for someone who is not
  X.
- **Several behaviors in one scenario:** a failing test wouldn't show which part
  broke.
- **Requirements with no scenario,** or scenarios that don't cover the
  requirement's promise.

## What each finding adds

Add these fields:

```
- Test sketch:
  - Level: <unit | integration | UI | contract>
  - Arrange and act: <one sentence>
  - Passes when: <observable result>
  - Fails when: <a concrete wrong implementation and what the test sees>
```

Check your own rewrite: if you can't name a wrong implementation that makes the
test fail, the rewrite isn't finished.

## Fit the project

Check that the test could exist in this project. If project instructions rule
out a test level, or the code cannot support the test, say so: an invariant that
can only be checked at a forbidden level is itself a finding. Propose wording
that can be tested at an allowed level, or say what would have to change.

In a specs-only repo, describe tests as platform-neutral contract tests.

## Coverage

Report how many requirements and scenarios you checked and how many you flagged,
so the user can see that all of them were looked at.
