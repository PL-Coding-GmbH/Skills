---
name: spring-persistence-jpa
description: |
  Persistence layer for Spring Boot Kotlin backends with JPA/Hibernate, Spring Data, Postgres, and Flyway - JPA entities in Kotlin, Spring Data repositories, adapters that implement domain repository interfaces, entity mappers, JPQL queries and fetch joins, N+1 avoidance, keyset pagination, optimistic locking, schema-per-module, and Flyway migrations. Use this skill whenever creating or changing an entity, table, column, index, relation, repository, query, or migration, or when debugging lazy loading, N+1 queries, or schema mismatches. Trigger on phrases like "entity", "@Entity", "table", "column", "add a field to the database", "repository", "JpaRepository", "Spring Data", "query", "@Query", "JPQL", "JOIN FETCH", "N+1", "lazy loading", "LazyInitializationException", "migration", "Flyway", "schema", "index", "foreign key", "@ManyToOne", "@OneToMany", "@ManyToMany", or "optimistic locking".
---

# Spring Persistence (JPA + Flyway)

## Principles

- **Entities never leave `infra`.** Services see domain models through domain repository interfaces. An adapter in `infra` implements the interface with Spring Data and maps entities to domain models.
- **The schema is owned by Flyway**, not by Hibernate. `spring.jpa.hibernate.ddl-auto: validate` in every environment, including dev and tests.
- **Each module owns one Postgres schema** (`chat_service`). No module reads another module's tables, and there are no foreign keys across schemas.
- **Every query is explicit about what it loads.** All associations are lazy and get fetched on purpose.

---

## Package Layout (`infra/database`)

```
infra/database
├── entity/        ChatEntity, ChatMessageEntity
├── repository/    SpringDataChatRepository (Spring Data), JpaChatRepository (adapter)
└── mapper/        ChatEntityMappers.kt
```

| Type | Visibility | Role |
|---|---|---|
| `SpringDataChatRepository : JpaRepository<ChatEntity, ChatId>` | `internal` | Spring Data interface. Queries only. |
| `JpaChatRepository : ChatRepository` | `@Component` | Adapter. Implements the domain interface, maps to and from domain models. |
| `ChatEntity` | `internal` where possible | JPA mapping of the table. |

Marking Spring Data interfaces and entities `internal` keeps other modules from touching them at compile time.

---

## Entities

```kotlin
@Entity
@Table(
    name = "chats",
    schema = "chat_service",
)
class ChatEntity(
    @Id
    var id: ChatId,

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "creator_id", nullable = false)
    var creator: ChatParticipantEntity,

    @ManyToMany(fetch = FetchType.LAZY)
    @JoinTable(
        name = "chat_participants_cross_ref",
        schema = "chat_service",
        joinColumns = [JoinColumn(name = "chat_id")],
        inverseJoinColumns = [JoinColumn(name = "user_id")],
    )
    var participants: MutableSet<ChatParticipantEntity> = mutableSetOf(),

    @Column(name = "created_at", nullable = false, updatable = false)
    var createdAt: Instant,

    @Version
    var version: Long? = null,
)
```

- A plain `class`, **never a `data class`**. Generated `equals`/`hashCode`/`toString` read every property, which triggers lazy loads, breaks `HashSet` membership, and can recurse forever through bidirectional relations.
- Properties are `var` constructor parameters. The `kotlin-jpa` plugin adds the no-arg constructor Hibernate needs, and the `allOpen` config in the convention plugin opens the class for proxies (see **spring-module-structure**).
- `@Table(name = ..., schema = ...)` on every entity. The table name never derives from the class name.
- `@Column(nullable = ...)` matches the Kotlin type: a non-null Kotlin type is `nullable = false`, a nullable one is `nullable = true`.
- **IDs are assigned by the application** (`UUID`, set by the service when it creates the domain model). No `@GeneratedValue`, so domain models never have a null ID.
- `@Version var version: Long? = null` on every aggregate root. It gives optimistic locking against lost updates. It also tells Spring Data whether an entity is new: `null` means `persist`, otherwise `merge`. Without it, `save` on an entity with an assigned ID always issues an extra `SELECT`.
- Timestamps are set from the service's `Clock` and passed in. No `Instant.now()` defaults, no `@CreationTimestamp`.
- Enums are stored with `@Enumerated(EnumType.STRING)`, never ordinal.
- Collections are `MutableSet`, so Hibernate can track changes in place. Use `List` only with an `@OrderColumn`.
- Business logic doesn't live on entities. `isExpired` belongs on the domain model.

### Associations

| Relation | Mapping |
|---|---|
| Many-to-one | `@ManyToOne(fetch = FetchType.LAZY, optional = false)` + `@JoinColumn(nullable = false)` |
| One-to-many | Prefer no mapping. Query the child side by parent ID. Map it only when the parent truly owns the children's lifecycle. |
| Many-to-many | `@ManyToMany(fetch = FetchType.LAZY)` with an explicit `@JoinTable` in the module's schema |
| Reference to another module's data | A plain ID column (`var userId: UserId`), never an association |

**Never `FetchType.EAGER`**, and always set `fetch = LAZY` explicitly on `@ManyToOne`/`@OneToOne`, because JPA makes those eager by default. Eager associations load on every query, and with JPQL they turn into one extra query per row.

---

## Spring Data Repositories

```kotlin
internal interface SpringDataChatRepository : JpaRepository<ChatEntity, ChatId> {

    @Query(
        """
        SELECT DISTINCT c
        FROM ChatEntity c
        JOIN FETCH c.creator
        JOIN FETCH c.participants
        WHERE c.id = :chatId
        AND EXISTS (
            SELECT 1 FROM c.participants p WHERE p.userId = :userId
        )
        """
    )
    fun findByIdForParticipant(chatId: ChatId, userId: UserId): ChatEntity?

    @Query(
        """
        SELECT DISTINCT c
        FROM ChatEntity c
        JOIN FETCH c.creator
        JOIN FETCH c.participants
        WHERE EXISTS (
            SELECT 1 FROM c.participants p WHERE p.userId = :userId
        )
        """
    )
    fun findAllForParticipant(userId: UserId): List<ChatEntity>
}
```

- Return `T?` for single results. Never `Optional`, and use `findByIdOrNull(id)` instead of `findById(id)`.
- Derived queries (`findByToken`, `findByUserIdIn`) for simple lookups. `@Query` with JPQL as soon as a query needs a join, a fetch, or a condition that makes the method name long.
- Every query that feeds a mapper `JOIN FETCH`es exactly the associations the mapper reads. That is the contract between query and mapper.
- Bulk updates and deletes use `@Modifying` + `@Query`. They bypass the persistence context, so never mix them with loaded entities of the same type in one transaction without `clearAutomatically = true`.
- Batch loads use `...In` queries or `findAllById(ids)`. A repository call inside `map`, `forEach`, or a `for` loop is an N+1.
- Native SQL only for Postgres features JPQL can't express. Keep it in the same repository with `nativeQuery = true`.

---

## Adapters

The adapter implements the domain interface. Mapping happens inside the adapter, within the service's transaction, so lazy associations it reads are already fetched by the query.

```kotlin
@Component
internal class JpaChatRepository(
    private val springDataChatRepository: SpringDataChatRepository,
    private val springDataChatParticipantRepository: SpringDataChatParticipantRepository,
) : ChatRepository {

    override fun findByIdForParticipant(chatId: ChatId, userId: UserId): Chat? {
        return springDataChatRepository.findByIdForParticipant(chatId, userId)?.toChat()
    }

    override fun save(chat: Chat): Chat {
        val participantEntities = springDataChatParticipantRepository
            .findAllById(chat.participants.map { it.userId })
            .toMutableSet()

        val entity = springDataChatRepository.findByIdOrNull(chat.id)
            ?.apply { participants = participantEntities }
            ?: chat.toChatEntity(
                creator = participantEntities.first { it.userId == chat.creator.userId },
                participants = participantEntities,
            )

        return springDataChatRepository.save(entity).toChat()
    }

    // ...
}
```

- Name: `Jpa<Model>Repository`. Spring Data interface: `SpringData<Model>Repository`. Never `Impl`.
- `save` loads the existing entity and copies the changed fields onto it, or builds a new entity. The `@Version` check then protects against concurrent updates.
- The adapter has no `@Transactional`. It runs inside the service's transaction.
- The adapter contains no business rules. If you're writing an `if` about the domain, it belongs in the service.

---

## Entity Mappers (`infra/database/mapper`)

```kotlin
internal fun ChatEntity.toChat(lastMessage: ChatMessage? = null): Chat {
    return Chat(
        id = id,
        creator = creator.toChatParticipant(),
        participants = participants.map { it.toChatParticipant() }.toSet(),
        lastMessage = lastMessage,
        createdAt = createdAt,
    )
}
```

- Extension functions named after the target type, like api mappers.
- No `!!`. If a mapper needs `!!`, the entity's nullability is wrong.
- A mapper reading an association the query didn't fetch is an N+1 or a `LazyInitializationException`. Fix the query, not the mapper.

---

## Keyset Pagination

```kotlin
@Query(
    """
    SELECT m
    FROM ChatMessageEntity m
    JOIN FETCH m.sender
    WHERE m.chatId = :chatId
    AND m.createdAt < :before
    ORDER BY m.createdAt DESC, m.id DESC
    """
)
fun findPageBefore(chatId: ChatId, before: Instant, limit: Limit): List<ChatMessageEntity>
```

- Order by the cursor column plus the ID as a tiebreaker, and back it with a matching index (`(chat_id, created_at DESC, id DESC)`).
- Use Spring Data's `Limit` parameter, not `Pageable`. Offset paging gets slower with every page and skips or repeats rows when new data arrives.

---

## Flyway Migrations

```
chat/src/main/resources/db/migration/chat/
├── V2026_10_13_1200__create_chat_tables.sql
└── V2026_10_20_0930__add_message_index.sql
```

```yaml
spring:
  flyway:
    schemas:
      - user_service
      - chat_service
      - notification_service
    locations:
      - classpath:db/migration/user
      - classpath:db/migration/chat
      - classpath:db/migration/notification
  jpa:
    hibernate:
      ddl-auto: validate
```

- Each module keeps its migrations in `src/main/resources/db/migration/<module>`. They end up on the app's classpath because the module is a dependency of `:app`.
- One Flyway run applies all modules' locations. Versions must be unique across all modules, so use a **timestamp version** (`V2026_10_13_1200__...`), never `V1`, `V2`.
- `spring.flyway.schemas` creates the schemas. The first one listed also holds Flyway's history table.
- A migration is **never edited after it is merged**. Fix mistakes with a new migration.
- Every table, column, index, and constraint the entity relies on is created by a migration. Write the SQL by hand; don't paste Hibernate's generated DDL without reviewing it.
- Index every foreign key column and every column used in a `WHERE` or `ORDER BY` of a frequent query. Indexes are declared in SQL, not in `@Table(indexes = ...)`.
- Changes must be safe while the old version of the app still runs: add a nullable column, deploy, backfill, then add `NOT NULL` in a later migration. Never rename or drop a column in the same release that stops using it.

```sql
-- V2026_10_13_1200__create_chat_tables.sql
CREATE TABLE chat_service.chat_participants (
    user_id             UUID PRIMARY KEY,
    username            VARCHAR(20)  NOT NULL UNIQUE,
    email               VARCHAR(320) NOT NULL UNIQUE,
    profile_picture_url TEXT,
    created_at          TIMESTAMPTZ  NOT NULL
);

CREATE TABLE chat_service.chats (
    id         UUID PRIMARY KEY,
    creator_id UUID        NOT NULL REFERENCES chat_service.chat_participants (user_id),
    created_at TIMESTAMPTZ NOT NULL,
    version    BIGINT      NOT NULL
);

CREATE INDEX idx_chats_creator_id ON chat_service.chats (creator_id);
```

Store every `Instant` as `TIMESTAMPTZ`.

---

## Configuration

```yaml
spring:
  jpa:
    open-in-view: false
    hibernate:
      ddl-auto: validate
    properties:
      hibernate:
        jdbc:
          time_zone: UTC
  datasource:
    hikari:
      maximum-pool-size: 10
```

- `open-in-view: false`. Lazy loading in controllers or during JSON serialization hides N+1s and holds connections for the whole request.
- Don't enable `show_sql` in shared config. Turn on `logging.level.org.hibernate.SQL: debug` locally when you need it.
- With virtual threads, `maximum-pool-size` is the real concurrency limit for database work. Size it against the database's connection limit, not the thread count.

---

## Naming Conventions

| Thing | Convention | Example |
|---|---|---|
| Entity | `<Model>Entity` | `ChatEntity` |
| Spring Data interface | `SpringData<Model>Repository` | `SpringDataChatRepository` |
| Adapter | `Jpa<Model>Repository` | `JpaChatRepository` |
| Mapper | extension fun named after the target | `fun ChatEntity.toChat()` |
| Schema | `<module>_service` | `chat_service` |
| Table | plural `snake_case` | `chat_messages` |
| Index | `idx_<table>_<columns>` | `idx_chat_messages_chat_id_created_at` |
| Migration | `V<yyyy_MM_dd_HHmm>__<description>.sql` | `V2026_10_13_1200__create_chat_tables.sql` |

---

## Checklist: Adding or Changing Persistence

- [ ] Flyway migration in the module's location with a timestamp version; safe while the old app version runs
- [ ] Entity is a plain class with `@Table(name, schema)`, assigned ID, `@Version` on aggregate roots
- [ ] Kotlin nullability matches `nullable` on every column
- [ ] Every association is `LAZY`; references to other modules are plain ID columns
- [ ] Queries `JOIN FETCH` everything their mapper reads; no repository call in a loop
- [ ] Indexes for new foreign keys and query filters
- [ ] Domain interface method added only if a service calls it; adapter maps to domain models
- [ ] Repository integration test against Postgres via Testcontainers (see **spring-integration-testing**)
