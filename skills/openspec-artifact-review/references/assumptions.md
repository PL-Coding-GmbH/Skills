# Reviewer: hidden assumptions

Your question: what must be true for these specs to work, without being written
down anywhere?

## Where to look

Go through each area and ask what the specs silently rely on. Use the list to
prompt your thinking; report only what applies to this change.

- **Platform:** operating system, OS version, device type, architecture, browser.
- **Network:** connectivity, latency, partial failure, offline, proxies.
- **Time:** clock synchronization, clock changes, time zones, daylight saving,
  ordering by timestamp, monotonic versus wall clock.
- **Locale and text:** language, encoding, normalization, sort order, right-to-left
  text, number and date formats.
- **Data:** sizes, volumes, uniqueness, migration of existing data, valid formats.
- **Concurrency:** single user or device, ordering, simultaneous edits, atomicity,
  idempotency.
- **Process lifetime:** the app or process being killed, restarts, background
  limits, crashes in the middle of an operation.
- **Resources:** disk space, memory, battery, quotas, rate limits.
- **Permissions and environment:** granted permissions, configuration, feature
  flags, existing accounts.
- **Dependencies:** library or service behavior, versions, availability.
- **Rollout:** deployment order, old and new versions running at the same time,
  platforms shipping at different times.

## What counts as hidden

An assumption is not hidden if the change's artifacts, the project instructions,
`openspec/config.yaml` or the main specs state it. Check before reporting it. An
assumption stated in only one artifact while another contradicts it is a finding.

## Classify every assumption

Every assumption gets exactly one class.

**Must specify:** if it were false, behavior would be wrong or undefined, and two
implementers could reasonably decide differently. Report it as a finding in the
common format, with this field added:

```
- Assumption: <what is silently taken to be true>
```

The proposed fix is the wording that makes the assumption explicit, or specifies
what happens when it doesn't hold.

**Safe to leave implicit:** report it as one row in a table, with no severity:

```
| Assumption | Where it is implied | Why it is safe |
```

A reason is required. "Unlikely" alone is not one; good reasons are things like
"the project only targets these platforms" or "a false value fails loudly at
startup".

## Output

Return, in this order: must-specify findings, the safe-to-leave-implicit table,
Coverage. Name the areas you found not applicable in the Coverage line.
