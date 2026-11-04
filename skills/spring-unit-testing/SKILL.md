---
name: spring-unit-testing
description: |
  Unit testing for Spring Boot Kotlin backends - an adversarial "how would I break this?" methodology first, then JUnit 5, AssertK, hand-written fakes of domain interfaces (never Mockito or MockK), a mutable fake Clock, a recording ApplicationEventPublisher, shared fakes in :common test fixtures, and no Spring context. Every suite starts by enumerating break vectors - unicode and emoji input, numeric overflow, boundaries, time and expiry edges, duplicate and out-of-order requests, every collaborator failure - and keeps only distinct, non-overlapping test angles. A unit test runs in memory with NO I/O - no database, no network, no Spring context, no real clock. Use this skill whenever writing or reviewing tests for services, domain models, validators, mappers, or any pure logic. Trigger on phrases like "unit test", "test the service", "test this logic", "fake repository", "fake clock", "JUnit", "AssertK", "assertThat", "assertFailure", "@ParameterizedTest", "test the mapper", "test the validator", or "write tests for".
---

# Spring Unit Testing

## Core methodology — test as someone who wants to break the code

**Read this before anything else in this skill. It applies to every test you write, and it comes before any question of setup, libraries, or syntax.**

Before writing a single test for a unit, switch roles. You are not the author demonstrating that the code works. You are an adversary who has been handed this code and paid to make it produce a wrong answer, corrupt data, leak another user's data, or throw the wrong error. Assume a bug is in there. Your job is to find the input, ordering, or collaborator response that exposes it.

Three rules govern everything below:

1. **Adversary first.** Enumerate break vectors *in writing* before you write any test code. The happy path is one line item in the list, not the starting point.
2. **Creative exhaustion.** The obvious edge cases are the ones the author already handled. The bugs live in the cases nobody imagined: an emoji in a username, a token that expires exactly now, the same request arriving twice, a user acting on someone else's chat. Hunt those deliberately.
3. **One angle per test.** Every test must attack the unit from an angle no other test covers. Twenty tests that all fail for the same reason are one test with nineteen copies.

### Step 1 — Map the attack surface

List, explicitly:

- Every public function and every parameter it takes.
- Every outcome: each return shape and **each domain exception** it can throw.
- Every collaborator (domain interface), and every outcome that collaborator can produce, including "not found" and throwing.
- Every side effect: what gets saved, deleted, and which events get published.
- Every implicit input: the injected `Clock`, configuration properties, default parameter values.

### Step 2 — For each item, ask: "How would I break this?"

Write the break vectors down as a plain list first, in prose. Keep asking until the list stops growing. Only then write `@Test` methods, one per surviving vector.

Useful adversary prompts:

- What input makes this function's assumption about its argument false?
- What value is legal for the type but illegal for the domain?
- What happens exactly at the boundary, and one step past it?
- What if this request arrives twice? Concurrently? For a resource that was just deleted?
- What if the acting user isn't allowed to touch this resource?
- What if the collaborator succeeds but returns nothing useful?
- What would a malicious client send here?

### Step 3 — The break-vector catalogue

Walk this every time. Not every category applies to every unit, but you must *consider* each one and consciously skip it, not forget it.

**Text and string input**

- Empty string; whitespace-only; leading/trailing whitespace (is it trimmed before the uniqueness check *and* before saving?).
- **Emoji**, including multi-codepoint ones: `"👍🏽".length == 4`, `"👨‍👩‍👧‍👦".length == 11`. Every length limit, truncation, or preview text is a break vector — a 20-character username limit counts UTF-16 units, not what the user sees.
- Non-Latin scripts (Arabic, CJK, Cyrillic), combining characters (`"é"` as one code point vs `e` + U+0301) wherever equality, dedup, or search matters.
- Case: `"Alice@Example.com"` vs `"alice@example.com"` in every uniqueness check and lookup. `"ß".uppercase() == "SS"`.
- Very long input, and input exactly at, one below, and one above every max length.
- Control characters, zero-width space (U+200B), bidi override (U+202E).
- Homoglyphs (Cyrillic `а` vs Latin `a`) wherever uniqueness matters (usernames).
- Strings interpolated into anything: `"%s"`, `"../.."`, quotes, HTML.

**Numbers and arithmetic**

- `0`, `1`, `-1`, and both sides of every domain boundary.
- **Overflow.** `Int.MAX_VALUE + 1` wraps silently. Every counter, `page * pageSize`, size total, or millisecond duration is a break vector.
- Negative values where only non-negative makes sense (page size, quantity, TTL).
- Unit confusion: seconds vs millis, minutes vs hours in configuration.

**Collections**

- Empty; one element; exactly at a limit; limit + 1.
- Duplicates, including duplicates that only differ by case.
- **The acting user included in a list of "other" users** (creating a chat with yourself).
- IDs in the list that don't exist; a mix of existing and missing IDs.

**Time and expiry**

- A token that expires **exactly now** (`expiresAt == now`): expired or not? The contract must say, and the test must pin it.
- One nanosecond before and after expiry.
- A clock that returns the same instant twice (ordering by `createdAt` ties).
- Year boundaries, DST changes if anything is computed in a local zone.

**State, ordering, and idempotency**

- The same command twice (double submit): second registration, second verification of the same token, second delete.
- Acting on something that was already deleted, already used, or already expired.
- An event handled twice must not create duplicates.
- Every state transition, and the transitions that must be impossible (reset a password with a used token).

**Authorization**

- Every operation performed by a user who is **not** the owner or member.
- A user acting on their own resource vs someone else's, with the same IDs otherwise.

**Collaborators**

- Every "not found" from every repository, individually.
- A collaborator throwing (storage unavailable, sender fails): is the right domain exception propagated, and was nothing half-done before it?
- Success with a degenerate payload: empty list, null optional fields.

### Step 4 — Distinct angles only

> **Two tests are redundant if a single change to the production code would make both fail for the same reason.**

Before you commit to a test, name the specific behavior, branch, or line that this test — and only this test — guards. If you can't name it, the test doesn't earn its place.

| Redundant | Distinct |
|---|---|
| `empty email is rejected` + `blank email is rejected` through one branch | `blank email is rejected` + `email is trimmed before the duplicate check` |
| Three tests for three missing IDs that hit the same `throw` | One test with a missing ID + one with a mix of existing and missing IDs |
| `creates chat` + `creates chat and returns it` | `creates chat` + `publishes ChatCreatedEvent with all participant IDs` |

Use **`@ParameterizedTest`** when you have **one angle across many data points** (twelve malformed emails hitting the same rejection). Don't use it to smuggle several different angles into one method. Those deserve their own names, because the test name documents the break vector.

```kotlin
@ParameterizedTest
@ValueSource(strings = ["", "   ", "no-at-sign", "@no-local", "a@@b.com"])
fun `malformed emails are rejected`(email: String) {
    assertFailure { service.register(email = email, username = "alice", password = "Secret123!") }
        .isInstanceOf<InvalidEmailException>()
}
```

### Step 5 — Stop condition

The suite is complete when **you can't name another way to break the unit without changing its public contract.** If a break vector isn't observable through the public surface, the unit usually needs a new observation point, not fewer tests.

---

## What is a unit test here

A unit test:

- Runs in memory, in milliseconds, with **no Spring context**. No `@SpringBootTest`, no `@ExtendWith(SpringExtension::class)`, no autowiring.
- Does **no I/O**: no database, no Testcontainers, no HTTP, no file system, no real clock.
- Constructs the unit with its constructor, passing fakes for every domain interface that would cross an I/O boundary.
- May wire several real classes together, as long as none of them crosses those boundaries.

Examples:

- ✅ `ChatService` + `FakeChatRepository` + `FakeChatParticipantRepository` + `RecordingEventPublisher` + `MutableClock` → unit.
- ✅ `Chat.isParticipant`, `EmailVerificationToken.isExpired(now)`, `Chat.toChatDto()` → unit.
- ❌ `JpaChatRepository` against Postgres → integration (**spring-integration-testing**).
- ❌ `SupabaseFileStorage` against WireMock → integration.
- ❌ Anything through `RestTestClient` → E2E (**spring-integration-testing**).

What unit tests **cannot** show, and must be covered by integration tests instead: transaction rollback, JPA mappings and queries, unique constraints, `@TransactionalEventListener` timing, security rules, and JSON serialization.

---

## Stack

| Concern | Library |
|---|---|
| Framework | JUnit 5 Jupiter (`org.junit.jupiter:junit-jupiter`), added by the `<app>.kotlin.jvm` convention plugin |
| Assertions | AssertK (`com.willowtreeapps.assertk:assertk-jvm`) |
| Exceptions | AssertK `assertFailure { }` |
| Test doubles | Hand-written fakes |
| Time | `MutableClock` from `:common` test fixtures |
| Events | `RecordingEventPublisher` from `:common` test fixtures |

- Only AssertK assertions. No `kotlin.test` asserts, no JUnit `Assertions.assertEquals`, no AssertJ (which `spring-boot-starter-test` brings in). JUnit's `assertThrows` is tolerated, but prefer `assertFailure`.
- **No Mockito, no MockK.** `spring-boot-starter-test` puts Mockito on the classpath; never import it.
- No `Thread.sleep` and no reflection into private members.

---

## Where unit tests live

- `src/test/kotlin` of the module, in the same package as the class under test.
- Name: `<ClassUnderTest>Test`. Test function names are backticked sentences describing the behavior: `` `adding a participant who is already in the chat does not duplicate them` ``.
- Run: `./gradlew :chat:test`.
- Fakes used by one module live in that module's `src/test/kotlin/.../fake`. Fakes used by several modules live in `:common`'s `src/testFixtures` and reach other modules through `testImplementation(testFixtures(project(":common")))` (added by the convention plugin).

---

## Shared fakes (`:common` test fixtures)

```kotlin
class MutableClock(
    private var current: Instant = Instant.parse("2026-01-01T12:00:00Z"),
    private val zone: ZoneId = ZoneOffset.UTC,
) : Clock() {

    override fun instant(): Instant = current
    override fun getZone(): ZoneId = zone
    override fun withZone(zone: ZoneId): Clock = MutableClock(current, zone)

    fun advanceBy(duration: Duration) {
        current += duration
    }

    fun setTo(instant: Instant) {
        current = instant
    }
}
```

```kotlin
class RecordingEventPublisher : ApplicationEventPublisher {

    private val recorded = mutableListOf<Any>()

    val events: List<Any>
        get() = recorded.toList()

    override fun publishEvent(event: Any) {
        recorded += event
    }

    inline fun <reified T> eventsOf(): List<T> = events.filterIsInstance<T>()
}
```

---

## Fakes, not mocks

A fake is a working in-memory implementation of a domain interface:

```kotlin
class FakeChatRepository : ChatRepository {

    private val chats = mutableMapOf<ChatId, Chat>()

    var failWith: RuntimeException? = null

    fun given(vararg chat: Chat) {
        chat.forEach { chats[it.id] = it }
    }

    override fun findById(chatId: ChatId): Chat? = chats[chatId]

    override fun findByIdForParticipant(chatId: ChatId, userId: UserId): Chat? =
        chats[chatId]?.takeIf { it.isParticipant(userId) }

    override fun findAllForParticipant(userId: UserId): List<Chat> =
        chats.values.filter { it.isParticipant(userId) }

    override fun save(chat: Chat): Chat {
        failWith?.let { throw it }
        chats[chat.id] = chat
        return chat
    }

    override fun deleteById(chatId: ChatId) {
        chats.remove(chatId)
    }
}
```

- The fake behaves like the real adapter for everything the contract promises: filtering by participant, returning `null` for unknown IDs. A fake that returns whatever the test set up regardless of arguments hides bugs.
- Expose a way to make it fail (`failWith`), mirroring the real failure modes.
- Assert on **state and events**, never on call patterns. "The chat now has three participants" is a test. "`save` was called once" is not.
- If a collaborator can't be faked because its type isn't yours (an SDK client), it is missing a domain interface. Add the interface (see **spring-service-layer**).
- Pure collaborators that are cheap to build (validators, normalizers, mappers) are used for real, not faked.

---

## Service test example

```kotlin
class ChatServiceTest {

    private val clock = MutableClock()
    private val chatRepository = FakeChatRepository()
    private val participantRepository = FakeChatParticipantRepository()
    private val eventPublisher = RecordingEventPublisher()

    private val service = ChatService(
        chatRepository = chatRepository,
        chatParticipantRepository = participantRepository,
        eventPublisher = eventPublisher,
        clock = clock,
    )

    private val alice = participant("alice")
    private val bob = participant("bob")
    private val carol = participant("carol")

    @BeforeEach
    fun setUp() {
        participantRepository.given(alice, bob, carol)
    }

    @Test
    fun `a non-member can't add participants and the chat stays unchanged`() {
        val chat = chat(creator = alice, participants = setOf(alice, bob))
        chatRepository.given(chat)

        assertFailure {
            service.addParticipants(chat.id, requestUserId = carol.userId, userIds = setOf(carol.userId))
        }.isInstanceOf<ChatNotFoundException>()

        assertThat(chatRepository.findById(chat.id)!!.participants).containsExactlyInAnyOrder(alice, bob)
        assertThat(eventPublisher.events).isEmpty()
    }

    @Test
    fun `adding an unknown user fails without adding the known ones`() {
        val chat = chat(creator = alice, participants = setOf(alice, bob))
        chatRepository.given(chat)
        val unknownUserId = UUID.randomUUID()

        assertFailure {
            service.addParticipants(chat.id, requestUserId = alice.userId, userIds = setOf(carol.userId, unknownUserId))
        }.isInstanceOf<ChatParticipantNotFoundException>()

        assertThat(chatRepository.findById(chat.id)!!.participants).containsExactlyInAnyOrder(alice, bob)
    }
}
```

- A fresh test class instance per test (JUnit's default) gives every test fresh fakes. Don't share mutable state in a companion object.
- Small factory functions (`participant("alice")`, `chat(...)`) keep tests focused on what differs. Put them next to the fakes.
- `!!` is fine in test code when a `null` would be a test failure anyway.

---

## Optional verification — mutation testing

Once the suite is green, a mutation-testing pass is the strongest check that it is complete. Run it **only when the user asks for it**. If a mutation survives, either fix the test that should have caught it, or add a test for the missed break vector. A mutation that survives because the behavior isn't observable usually means the unit needs a new observation point.

---

## Anti-patterns

| Anti-pattern | What to do instead |
|---|---|
| Mockito / MockK, `verify { }` | A fake and an assertion on resulting state or events |
| `@SpringBootTest` for testing service logic | Construct the service with fakes; Spring contexts are for integration tests |
| `Instant.now()` in tests or in the code under test | `MutableClock` injected into the unit |
| Asserting the happy path only | Walk the break-vector catalogue first |
| Testing that a failure rolled back with fakes | Integration test against the real database |
| Fake ignores its arguments and returns canned data | Fake implements the interface's contract in memory |
| AssertJ / `kotlin.test` / JUnit assertions | AssertK |
| Several tests failing for the same one-line change | Keep one, spend the others on new angles |
| Only ASCII, only positive numbers, only mid-range values | Every text input gets a unicode/emoji case, every number its boundary case |
| Writing tests from the implementation you just read | Enumerate break vectors from the contract first |
