---
name: spring-service-layer
description: |
  Service and domain layer for Spring Boot Kotlin backends - @Service classes, domain models, domain repository interfaces, transaction boundaries, domain exceptions, authorization checks, in-process Spring application events (module-internal and cross-module), @TransactionalEventListener, @Async listeners, scheduled jobs, and logging. Use this skill whenever writing or changing business logic, adding a service method, defining a domain model or domain exception, deciding where a transaction starts, publishing or listening to an event, making modules react to each other, or adding a @Scheduled job. Trigger on phrases like "service", "business logic", "use case", "domain model", "domain exception", "@Transactional", "transaction", "rollback", "event", "publish an event", "ApplicationEventPublisher", "@TransactionalEventListener", "@EventListener", "cross-module", "when a user is created", "@Async", "@Scheduled", "cron job", "cleanup job", or "logger".
---

# Spring Service and Domain Layer

## Principles

- **Services hold all business rules.** Validation that needs data, authorization ("is this user in the chat?"), state transitions, and orchestration happen in `service`, not in controllers, entities, or listeners.
- **Services speak domain.** They take and return domain models and plain values. They depend on domain interfaces, not on `infra` classes, Spring Data, or HTTP types.
- **A transaction is one unit of business work** and starts at a public service method.
- **Modules react to each other through events**, never by calling each other's services.

---

## Domain Models (`domain/model`)

```kotlin
data class Chat(
    val id: ChatId,
    val creator: ChatParticipant,
    val participants: Set<ChatParticipant>,
    val lastMessage: ChatMessage?,
    val createdAt: Instant,
) {

    val lastActivityAt: Instant
        get() = lastMessage?.createdAt ?: createdAt

    fun isParticipant(userId: UserId): Boolean = participants.any { it.userId == userId }
}
```

- Immutable `data class`es. Changes produce a copy.
- IDs are never null. The service assigns a new ID (`UUID.randomUUID()`) when it creates the model, so no `id!!` exists anywhere.
- Pure behavior that only needs the model's own data lives on the model (`isParticipant`, `isExpired(now)`). Anything that needs a collaborator lives in a service.
- No Spring, no `jakarta.persistence`, no Jackson annotations.
- ID types are typealiases in `common.domain.type` (`typealias ChatId = UUID`).

---

## Domain Repository Interfaces (`domain/repository`)

Services reach persistence through interfaces the domain owns. `infra` implements them with JPA (see **spring-persistence-jpa**), and unit tests implement them with in-memory fakes (see **spring-unit-testing**).

```kotlin
interface ChatRepository {

    fun findById(chatId: ChatId): Chat?
    fun findByIdForParticipant(chatId: ChatId, userId: UserId): Chat?
    fun findAllForParticipant(userId: UserId): List<Chat>
    fun save(chat: Chat): Chat
    fun deleteById(chatId: ChatId)
}
```

- Return `T?` for single lookups, `List`/`Set` for many. Never `Optional`, never Spring's `Page`/`Pageable`. Pass paging as plain parameters (`before: Instant?, limit: Int`).
- Name methods by intent (`findAllForParticipant`), not by query mechanics.
- Only add methods a service actually calls. This is not a generic CRUD wrapper.
- The same pattern applies to anything else that leaves the process: `FileStorage`, `PushNotificationSender`, `EmailSender` interfaces in `domain`, implemented in `infra`.

---

## Services

```kotlin
@Service
class ChatService(
    private val chatRepository: ChatRepository,
    private val chatParticipantRepository: ChatParticipantRepository,
    private val eventPublisher: ApplicationEventPublisher,
    private val clock: Clock,
) {

    @Transactional(readOnly = true)
    fun getChat(chatId: ChatId, requestUserId: UserId): Chat {
        return chatRepository.findByIdForParticipant(chatId, requestUserId)
            ?: throw ChatNotFoundException(chatId)
    }

    @Transactional
    fun addParticipants(chatId: ChatId, requestUserId: UserId, userIds: Set<UserId>): Chat {
        val chat = chatRepository.findById(chatId)
            ?: throw ChatNotFoundException(chatId)

        if (!chat.isParticipant(requestUserId)) {
            throw ChatNotFoundException(chatId)
        }

        val newParticipants = chatParticipantRepository.findAllByIds(userIds)
        if (newParticipants.size != userIds.size) {
            throw ChatParticipantNotFoundException(userIds - newParticipants.map { it.userId }.toSet())
        }

        val updatedChat = chatRepository.save(
            chat.copy(participants = chat.participants + newParticipants)
        )

        eventPublisher.publishEvent(
            ChatParticipantsJoinedEvent(chatId = chatId, userIds = userIds)
        )

        return updatedChat
    }
}
```

- Name: `<Concept>Service`. Split a service when it serves clearly separate use cases (`ChatService`, `ChatMessageService`), not per method.
- A service may call other services **of the same module**. It never touches another module's classes.
- "Must exist" lookups throw a domain exception. Return `null` only from methods whose contract is "search, may find nothing".
- Load collections in one query (`findAllByIds`), never one repository call per element in a loop.
- Trim and normalize user input (emails lowercased, strings trimmed) in the service, once, before using it.
- Read the time as `Instant.now(clock)` (see **spring-di-configuration**).

---

## Transactions

- Every public service method that touches the database is annotated: `@Transactional` for writes, `@Transactional(readOnly = true)` for reads.
- `@Transactional` appears only in `service`. Never on controllers, listeners, adapters, or domain classes.
- **No remote calls inside a transaction.** An HTTP call, email, or push notification inside a transaction holds a database connection for its whole duration and can't be rolled back anyway. Do the remote work before the transaction starts, or after commit through an event listener.
- Spring rolls back on unchecked exceptions only. Domain exceptions extend `RuntimeException`. Infra adapters wrap checked exceptions from Java SDKs (`IOException`, `FirebaseMessagingException`) in a domain exception. Otherwise Kotlin lets them through unchecked, and Spring **commits** the transaction.
- A private method or a call to another method of the same bean never starts its own transaction (see the proxy pitfalls in **spring-di-configuration**).

---

## Domain Exceptions (`domain/exception`)

```kotlin
class ChatNotFoundException(val chatId: ChatId) : RuntimeException("Chat not found")

class ChatParticipantNotFoundException(val userIds: Set<UserId>) :
    RuntimeException("One or more users could not be found")
```

- One class per distinct failure a client may want to handle. Name: `<Thing><Problem>Exception`.
- The message is **safe to show to a client**: it ends up in the `detail` of the ProblemDetail. Put IDs and internals into properties, not into the message.
- Exceptions shared by every module (`ForbiddenException`, `UnauthorizedException`) live in `common.domain.exception`.
- Each new exception gets a mapping in the module's exception handler (see **spring-api-layer**).
- Never use exceptions for control flow inside the service. They are for failures the caller must hear about.

---

## Events

All events are in-process Spring application events. Two kinds:

| Kind | Declared in | Example | Consumers |
|---|---|---|---|
| Module-internal | `<module>.domain.event` | `MessageDeletedEvent` | Same module (WebSocket broadcast, cache eviction, after-commit side effects) |
| Cross-module | `common.domain.event.<publisher>` | `UserEvent.Verified` | Other modules |

### Defining events

```kotlin
// common.domain.event.user
sealed interface UserEvent {

    val userId: UserId

    data class Created(
        override val userId: UserId,
        val email: String,
        val username: String,
        val verificationToken: String,
    ) : UserEvent

    data class Verified(
        override val userId: UserId,
        val email: String,
        val username: String,
    ) : UserEvent
}
```

- Name events in the past tense: something that already happened.
- Each publishing module owns one sealed interface in `common`. A module only publishes its own events.
- Carry every value consumers need. A consumer must never have to call back into the publisher.
- Only IDs, primitives, and `Instant`s. Never entities, never domain models of another module.

### Publishing

Publish with `ApplicationEventPublisher.publishEvent(...)` from inside a `@Transactional` service method. `@TransactionalEventListener`s only run when that transaction commits, so a rolled-back operation never announces itself. An event published outside a transaction is silently dropped.

### Listening — same module

```kotlin
@TransactionalEventListener
fun onMessageDeleted(event: MessageDeletedEvent) {
    broadcastToChat(event.chatId, ...)
}
```

`@TransactionalEventListener` defaults to `AFTER_COMMIT`. Use it for side effects that must only happen once the data is committed: WebSocket broadcasts, remote calls, cache eviction.

### Listening — another module

The listener lives in the consuming module's `api/event` package. It is an entry point like a controller, so it only hands the work to a service:

```kotlin
@Component
class UserEventListener(
    private val chatParticipantService: ChatParticipantService,
) {

    @Async
    @TransactionalEventListener
    fun onUserEvent(event: UserEvent) {
        when (event) {
            is UserEvent.Verified -> chatParticipantService.createParticipant(
                userId = event.userId,
                username = event.username,
                email = event.email,
            )
            is UserEvent.Created -> Unit
        }
    }
}
```

- **`@Async` is required for cross-module listeners.** It runs the listener on its own (virtual) thread with its own transaction, so the consumer's service method can commit its writes, and a failing consumer doesn't fail the publisher's request after its data was already committed.
- The service method the listener calls is a normal `@Transactional` method.
- `when` over the sealed event is exhaustive with explicit `-> Unit` branches for events this module ignores. Never `else`: a new event type must force a decision in every consumer.
- Listeners must be idempotent. Handling the same event twice must not create duplicates (check before insert, or use a unique constraint).
- `@EnableAsync` is set once in `:app` (see **spring-di-configuration**).

Known trade-off: an `@Async` after-commit event is lost if the process dies between the commit and the listener finishing, and a listener exception is only logged. When losing an event is not acceptable, raise it with the user before building around it. The standard fix is a persistent event publication registry (Spring Modulith), which is a deliberate project decision.

---

## Scheduled Jobs

```kotlin
@Scheduled(cron = "\${chirp.user.token-cleanup-cron}")
@Transactional
fun deleteExpiredTokens() {
    emailVerificationTokenRepository.deleteExpiredBefore(Instant.now(clock))
}
```

- Scheduled methods live on the service that owns the data and follow the same transaction rules.
- Cron expressions come from configuration, not literals in code.
- If the app ever runs on more than one instance, every scheduled job needs a distributed lock (ShedLock). Flag this to the user rather than adding it silently.

---

## Logging

```kotlin
private val logger = LoggerFactory.getLogger(javaClass)

logger.info("Created chat {} with {} participants", chat.id, chat.participants.size)
```

- SLF4J with `{}` placeholders, not string templates: the message is only built when the level is enabled.
- Log IDs and counts. Never log passwords, tokens, API keys, emails, or full request payloads.
- `error` with the exception for failures someone must look at, `warn` for handled problems, `info` for business events, `debug` for diagnostics.
- No `println`.

---

## Naming Conventions

| Thing | Convention | Example |
|---|---|---|
| Service | `<Concept>Service` | `ChatService` |
| Domain model | plain noun | `Chat`, `ChatMessage` |
| Domain repository interface | `<Model>Repository` | `ChatRepository` |
| Other outbound interface | role noun | `FileStorage`, `PushNotificationSender` |
| Domain exception | `<Thing><Problem>Exception` | `ChatNotFoundException` |
| Module-internal event | `<Thing><PastTenseVerb>Event` | `MessageDeletedEvent` |
| Cross-module events | sealed `<Publisher>Event` with past-tense subtypes | `UserEvent.Verified` |
| Cross-module listener | `<Publisher>EventListener` | `UserEventListener` |

---

## Checklist: Adding a Service Method

- [ ] Takes and returns domain models or plain values, never DTOs or entities
- [ ] `@Transactional` (write) or `@Transactional(readOnly = true)` (read)
- [ ] No remote call inside the transaction; after-commit work goes through an event
- [ ] Every failure is a domain exception with a client-safe message, mapped in the module's exception handler
- [ ] Authorization checked before any change
- [ ] No repository call inside a loop
- [ ] Time from the injected `Clock`
- [ ] Events published inside the transaction; cross-module events defined in `common` and consumed with `@Async @TransactionalEventListener`
- [ ] Unit tests with fakes (see **spring-unit-testing**) and an integration test for the persistence path (see **spring-integration-testing**)
