# Reviewer: security

Your question: how would you attack what this change specifies, and where would
its security promises pass in tests but fail in production?

This is written analysis only. Describe attacks in words: no working payloads,
no exploit code, and nothing run against the code or any system. The report may
be committed, so if you come across a secret, cite its location and never repeat
its value.

## Step 1: Map the surface

- List the security requirements the change states.
- Find every trust boundary, whether or not the specs mention it, from the
  artifacts and, if there is code, from the code. A trust boundary is anywhere
  data or control passes from something less trusted to something more trusted.
  Examples: network requests and responses, authentication and authorization
  checks, user input, imported files, deep links and intents, IPC, other apps,
  backups and exported data, local storage, third-party services, content passed
  to an LLM.

If the change has no explicit security requirements, keep going with the
boundaries you found. A boundary that needs a requirement and has none is a
finding.

## Step 2: Attack every trust boundary

For each boundary, write a section:

```
### Boundary: <name>
- Attacker position: <who they are and what access they start with>
- Attack path: <concrete steps>
- What they gain: <the concrete impact>
- What stops it: <the spec text that prevents this, or "nothing">
```

If the spec text stops the attack, say so and why; this confirms the boundary
was examined. If nothing stops it, add a finding (S1, S2, ...) in the common
format, with a proposed spec change that does.

## Step 3: Test versus production for each security-relevant invariant

A security-relevant invariant is a requirement or scenario an attacker would
benefit from breaking. Skip the others; the testability reviewer covers them.

For each one, write a section:

```
### Invariant: <requirement or scenario name>
- What a test would do: <setup, including its fakes and fixed values>
- What differs in production: <the concrete difference>
- How it fails: <the sequence where the invariant breaks while tests stay green>
- What would close the gap: <spec text, or a test requirement>
```

Good places to look: fakes standing in for real auth or crypto, in-memory
databases with different transaction behavior, fixed clocks and token expiry,
single-threaded tests hiding races, debug builds and permissive test config,
mock servers that never return malformed data, retries and replays, stale caches
after permission changes, and rollouts where old and new clients coexist.

Each gap that really could happen is also a finding, in the common format. If you
can't find a realistic gap for an invariant, say that and why rather than
inventing one.

## Output

Return, in this order: boundary sections, invariant sections, findings, Coverage.
If the change truly has no trust boundaries, say so and explain why. Report how
many boundaries and invariants you examined.
