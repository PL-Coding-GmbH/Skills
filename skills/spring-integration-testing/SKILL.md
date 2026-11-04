---
name: spring-integration-testing
description: |
  Integration and end-to-end testing for Spring Boot Kotlin backends - real Postgres through Testcontainers with @ServiceConnection, Flyway-migrated schemas, @DataJpaTest adapter tests, module-level @SpringBootTest tests of services with real persistence, transactions and events, WireMock tests for HTTP service clients, and full-app E2E tests in :app with RestTestClient against a running server. Fakes replace only the boundaries that leave the system (third-party APIs, email, push). These are the most valuable tests in the codebase. Use this skill whenever writing tests that touch the database, a query, a migration, a transaction, an event listener, security rules, JSON serialization, an external HTTP API, or a whole HTTP flow. Trigger on phrases like "integration test", "E2E test", "end-to-end", "test the endpoint", "test the API", "test the repository", "test the query", "Testcontainers", "@SpringBootTest", "@DataJpaTest", "RestTestClient", "MockMvc", "WireMock", "test with a real database", "test the migration", "test the transaction", or "test the event listener".
---

# Spring Integration and E2E Testing

The same adversarial methodology as **spring-unit-testing** applies: enumerate break vectors from the contract first, one distinct angle per test. This skill covers the tests that cross real boundaries. They catch what unit tests can't: wrong queries, missing migrations, transactions that don't roll back, events that never fire, security holes, broken JSON.

## Test Types

| Type | Lives in | Spring context | Real | Faked |
|---|---|---|---|---|
| **Persistence** | module `src/test` | `@DataJpaTest` | Postgres, Flyway, entities, Spring Data, adapter | — |
| **Module integration** | module `src/test` | `@SpringBootTest` with the module's test app | Services, adapters, Postgres, transactions, internal events | Remote providers, `Clock` |
| **HTTP client** | module `src/test` | `@SpringBootTest` with the module's test app | HTTP service client, adapter, JSON | The provider (WireMock) |
| **E2E** | `:app` `src/test` | `@SpringBootTest(RANDOM_PORT)` | Everything: security, controllers, all modules, events, Postgres | Remote providers, `Clock` |

Rules for all of them:

- **Real Postgres, never H2.** H2 accepts SQL Postgres rejects and the other way round.
- The schema comes from the **real Flyway migrations**. `ddl-auto: validate` stays on, so a test fails when an entity and its migration disagree.
- Only boundaries that leave the system are faked: third-party HTTP APIs, email, push notifications. The fakes replace the **domain interface** (`FileStorage`, `EmailSender`), never a class in the middle.
- No Mockito, no `@MockitoBean`. Fakes are registered as beans.
- AssertK for assertions, Awaitility for waiting on async work. Never `Thread.sleep`.

---

## Dependencies

```toml
[versions]
wiremock = "3.13.1"

[libraries]
spring-boot-starter-test = { module = "org.springframework.boot:spring-boot-starter-test" }
spring-boot-starter-data-jpa-test = { module = "org.springframework.boot:spring-boot-starter-data-jpa-test" }
spring-boot-starter-security-test = { module = "org.springframework.boot:spring-boot-starter-security-test" }
spring-boot-testcontainers = { module = "org.springframework.boot:spring-boot-testcontainers" }
testcontainers-postgresql = { module = "org.testcontainers:testcontainers-postgresql" }
testcontainers-junit-jupiter = { module = "org.testcontainers:testcontainers-junit-jupiter" }
awaitility-kotlin = { module = "org.awaitility:awaitility-kotlin" }
wiremock = { module = "org.wiremock:wiremock-standalone", version.ref = "wiremock" }
```

Look up the latest WireMock version before adding it. The others are managed by the Spring Boot BOM.

---

## Shared Test Infrastructure (`:common` test fixtures)

```kotlin
// common/build.gradle.kts
dependencies {
    testFixturesApi(libs.spring.boot.testcontainers)
    testFixturesApi(libs.testcontainers.postgresql)
    testFixturesApi(libs.spring.boot.starter.test)
    testFixturesApi(libs.awaitility.kotlin)
}
```

### Postgres container

```kotlin
@TestConfiguration(proxyBeanMethods = false)
class PostgresTestConfig {

    @Bean
    @ServiceConnection
    fun postgresContainer(): PostgreSQLContainer = PostgreSQLContainer("postgres:17-alpine")
}
```

- `@ServiceConnection` points the datasource at the container. No `@DynamicPropertySource` for the database URL.
- Use the same Postgres major version as production.
- The container is a bean, so it lives as long as the cached Spring context. Every test class with the same configuration reuses one container and one context. Keep test configurations identical across classes so Spring can cache them.

### Database cleaner

```kotlin
class DatabaseCleaner(
    private val jdbcTemplate: JdbcTemplate,
) {

    fun clean(vararg schemas: String) {
        val tables = jdbcTemplate.queryForList(
            """
            SELECT table_schema || '.' || table_name
            FROM information_schema.tables
            WHERE table_schema IN (${schemas.joinToString { "'$it'" }})
            AND table_type = 'BASE TABLE'
            AND table_name <> 'flyway_schema_history'
            """,
            String::class.java,
        )
        if (tables.isNotEmpty()) {
            jdbcTemplate.execute("TRUNCATE ${tables.joinToString()} CASCADE")
        }
    }
}
```

`@SpringBootTest` tests are **not** `@Transactional`. A test-managed transaction never commits, so `@TransactionalEventListener`s never fire and rollback behavior can't be observed. Clean the module's schema in `@BeforeEach` instead.

---

## Module Test Application

`@DataJpaTest` and `@SpringBootTest` need a `@SpringBootConfiguration`. Each business module has one in its test sources, at the module's root package:

```kotlin
// chat/src/test/kotlin/com/<company>/<app>/chat/ChatTestApplication.kt
@SpringBootApplication
@ConfigurationPropertiesScan
@Import(PostgresTestConfig::class, ChatTestConfig::class)
class ChatTestApplication
```

```kotlin
@TestConfiguration(proxyBeanMethods = false)
@EnableAsync
class ChatTestConfig {

    @Bean
    fun clock(): MutableClock = MutableClock()

    @Bean
    @Primary
    fun fakeFileStorage(): FakeFileStorage = FakeFileStorage()

    @Bean
    fun databaseCleaner(jdbcTemplate: JdbcTemplate) = DatabaseCleaner(jdbcTemplate)
}
```

```yaml
# chat/src/test/resources/application.yml
spring:
  flyway:
    schemas: [chat_service]
    locations: [classpath:db/migration/chat]
  jpa:
    open-in-view: false
    hibernate:
      ddl-auto: validate
  threads:
    virtual:
      enabled: true
  http:
    serviceclient:
      supabase:
        base-url: "http://localhost:1"

chirp:
  chat:
    supabase:
      service-key: test-key
      bucket: test-bucket
      public-url: "http://localhost:1/public"
```

- The module's test app only scans the module's own package, so module tests start fast and prove the module doesn't secretly depend on another one.
- `FakeFileStorage` is the same in-memory fake the unit tests use. As a `@Primary` bean it wins wherever `FileStorage` is injected. The real `SupabaseFileStorage` is still created, which is why the test config gives it dummy properties pointing at an unreachable URL. Only the WireMock test talks to it directly.

---

## Persistence Tests (`@DataJpaTest`)

Test each adapter against the real database:

```kotlin
@DataJpaTest
@Import(JpaChatRepository::class, JpaChatParticipantRepository::class)
class JpaChatRepositoryTest @Autowired constructor(
    private val chatRepository: JpaChatRepository,
    private val participantRepository: JpaChatParticipantRepository,
    private val entityManager: TestEntityManager,
) {

    @Test
    fun `findByIdForParticipant hides the chat from non-members`() {
        val alice = participantRepository.save(participant("alice"))
        val bob = participantRepository.save(participant("bob"))
        val carol = participantRepository.save(participant("carol"))
        val chat = chatRepository.save(chat(creator = alice, participants = setOf(alice, bob)))
        entityManager.flush()
        entityManager.clear()

        assertThat(chatRepository.findByIdForParticipant(chat.id, carol.userId)).isNull()
        assertThat(chatRepository.findByIdForParticipant(chat.id, bob.userId)?.participants)
            .isNotNull()
            .containsExactlyInAnyOrder(alice, bob)
    }
}
```

- `@DataJpaTest` rolls back after each test, which is fine here: nothing depends on commit.
- **Always `flush()` and `clear()` between writing and reading.** Otherwise the read is served from the persistence context and never runs your query.
- Test what the database decides: query filters and ordering, keyset pagination boundaries (ties on `createdAt`), unique constraints (expect the exception on `flush()`), cascades, `@Version` conflicts, and that mappers don't hit unfetched lazy associations (`clear()` first, then map).
- Constructor injection with `@Autowired constructor` is the one place `@Autowired` appears: JUnit creates the test instance, not Spring.

---

## Module Integration Tests

Services with real adapters and a real transaction:

```kotlin
@SpringBootTest(classes = [ChatTestApplication::class])
@RecordApplicationEvents
class ChatServiceIntegrationTest @Autowired constructor(
    private val chatService: ChatService,
    private val chatRepository: ChatRepository,
    private val participantRepository: ChatParticipantRepository,
    private val databaseCleaner: DatabaseCleaner,
    private val events: ApplicationEvents,
) {

    @BeforeEach
    fun setUp() {
        databaseCleaner.clean("chat_service")
    }

    @Test
    fun `a failing add leaves the chat unchanged in the database`() {
        val alice = participantRepository.save(participant("alice"))
        val chat = chatRepository.save(chat(creator = alice, participants = setOf(alice)))

        assertFailure {
            chatService.addParticipants(chat.id, requestUserId = alice.userId, userIds = setOf(UUID.randomUUID()))
        }.isInstanceOf<ChatParticipantNotFoundException>()

        assertThat(chatRepository.findById(chat.id)!!.participants).containsExactly(alice)
        assertThat(events.stream(ChatParticipantsJoinedEvent::class.java).count()).isEqualTo(0L)
    }
}
```

Use these for what only a real transaction shows: rollback on failure, constraint violations surfacing as the right domain exception, events published only after commit, `@Version` conflicts between two concurrent updates, scheduled cleanup jobs.

### Async event listeners

Cross-module listeners run `@Async` after commit. Publish the event inside a real transaction (inject `TransactionTemplate` and `ApplicationEventPublisher`), then wait for the result, don't sleep:

```kotlin
transactionTemplate.executeWithoutResult {
    eventPublisher.publishEvent(UserEvent.Verified(userId = userId, email = "alice@example.com", username = "alice"))
}

await atMost Duration.ofSeconds(5) untilAsserted {
    assertThat(participantRepository.findById(userId)).isNotNull()
}
```

Also test that handling the **same event twice** leaves one row, not two.

---

## HTTP Client Tests (WireMock)

```kotlin
@SpringBootTest(classes = [ChatTestApplication::class])
class SupabaseFileStorageTest @Autowired constructor(
    private val fileStorage: SupabaseFileStorage,
) {

    companion object {

        @JvmField
        @RegisterExtension
        val wireMock: WireMockExtension = WireMockExtension.newInstance()
            .options(wireMockConfig().dynamicPort())
            .build()

        @JvmStatic
        @DynamicPropertySource
        fun properties(registry: DynamicPropertyRegistry) {
            registry.add("spring.http.serviceclient.supabase.base-url") { wireMock.baseUrl() }
            registry.add("chirp.chat.supabase.service-key") { "test-key" }
        }
    }

    @Test
    fun `a 503 from Supabase becomes StorageUnavailableException`() {
        wireMock.stubFor(post(urlPathMatching("/storage/v1/object/upload/sign/.*")).willReturn(serviceUnavailable()))

        assertFailure { fileStorage.createUploadUrl("avatar.png", Duration.ofMinutes(5)) }
            .isInstanceOf<StorageUnavailableException>()
    }

    @Test
    fun `requests carry the service key`() {
        wireMock.stubFor(delete(anyUrl()).willReturn(ok()))

        fileStorage.delete("avatar.png")

        wireMock.verify(deleteRequestedFor(anyUrl()).withHeader("Authorization", equalTo("Bearer test-key")))
    }
}
```

- This is the one place the real provider adapter runs. Include it in this test's context explicitly; keep it out of every other test.
- Cover: the exact path and method, auth headers, request body shape, response mapping, every error translation (`4xx` that matter, `5xx`, timeout via `withFixedDelay` beyond the read timeout, malformed body).
- Copy real provider responses into the stubs. A hand-invented response tests your assumptions, not the integration.

---

## E2E Tests (`:app`)

The whole app on a random port, called over real HTTP:

```kotlin
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@Import(PostgresTestConfig::class, E2eTestConfig::class)
abstract class E2eTest {

    @LocalServerPort
    private var port: Int = 0

    @Autowired
    private lateinit var databaseCleaner: DatabaseCleaner

    @Autowired
    protected lateinit var clock: MutableClock

    @Autowired
    protected lateinit var fakeEmailSender: FakeEmailSender

    protected lateinit var client: RestTestClient

    @BeforeEach
    fun setUpE2e() {
        databaseCleaner.clean("user_service", "chat_service", "notification_service")
        client = RestTestClient.bindToServer().baseUrl("http://localhost:$port").build()
    }
}
```

```kotlin
@TestConfiguration(proxyBeanMethods = false)
class E2eTestConfig {

    @Bean
    @Primary
    fun testClock(): MutableClock = MutableClock()

    @Bean
    @Primary
    fun fakeFileStorage(): FakeFileStorage = FakeFileStorage()

    @Bean
    @Primary
    fun fakeEmailSender(): FakeEmailSender = FakeEmailSender()

    @Bean
    fun databaseCleaner(jdbcTemplate: JdbcTemplate) = DatabaseCleaner(jdbcTemplate)
}
```

- One abstract base class, so every E2E class shares one cached context and one container.
- Field injection in the base class is the accepted exception for test classes.
- `@Primary` fakes win over the real adapters for every boundary that leaves the system.

### Auth helper

```kotlin
protected fun registerAndLogin(username: String): AuthenticatedUserDto {
    val email = "$username@example.com"
    client.post().uri("/api/auth/register")
        .body(RegisterRequest(email = email, username = username, password = "Secret123!"))
        .exchange()
        .expectStatus().is2xxSuccessful

    val token = fakeEmailSender.lastVerificationTokenFor(email)
    client.get().uri("/api/auth/verify?token=$token").exchange().expectStatus().isOk

    return client.post().uri("/api/auth/login")
        .body(LoginRequest(email = email, password = "Secret123!"))
        .exchange()
        .expectStatus().isOk
        .expectBody<AuthenticatedUserDto>()
        .returnResult()
        .responseBody!!
}
```

Tokens come from the real login flow, so the test also covers security. Don't build authentication objects by hand.

### Example

```kotlin
class ChatE2eTest : E2eTest() {

    @Test
    fun `a user who isn't in the chat gets 404 with CHAT_NOT_FOUND`() {
        val alice = registerAndLogin("alice")
        val bob = registerAndLogin("bob")
        val mallory = registerAndLogin("mallory")
        val chat = createChat(alice, otherUserIds = listOf(bob.user.id))

        client.get().uri("/api/chats/${chat.id}")
            .header(HttpHeaders.AUTHORIZATION, "Bearer ${mallory.accessToken}")
            .exchange()
            .expectStatus().isNotFound
            .expectBody()
            .jsonPath("$.code").isEqualTo("CHAT_NOT_FOUND")
    }

    @Test
    fun `chat endpoints require a token`() {
        client.get().uri("/api/chats")
            .exchange()
            .expectStatus().isUnauthorized
    }
}
```

What E2E tests must cover:

- Every endpoint: the success status and body shape, as the client sees the JSON.
- Every error `code` an endpoint can return, with its status.
- `401` without a token on every protected route; `404`/`403` for another user's resource.
- Validation: one invalid body per endpoint returns `400 VALIDATION_FAILED` with the field name.
- Cross-module flows: an action in one module shows up in another (register → verify → user appears as a chat participant), using Awaitility for the async step.
- Time-dependent flows with `clock.advanceBy(...)`: tokens expire, refresh tokens rotate.

---

## Running

| Scope | Command |
|---|---|
| One module (unit + integration) | `./gradlew :chat:test` |
| E2E | `./gradlew :app:test` |
| Everything | `./gradlew test` |

Docker must be running for Testcontainers.

---

## Anti-patterns

| Anti-pattern | What to do instead |
|---|---|
| H2 or an embedded database | Postgres via Testcontainers |
| `ddl-auto: create-drop` in tests | Real Flyway migrations with `ddl-auto: validate` |
| `@Transactional` on `@SpringBootTest` tests | Clean the schema in `@BeforeEach`; let transactions commit |
| Reading back without `flush()` + `clear()` in `@DataJpaTest` | Flush and clear so the query really runs |
| `@MockitoBean` / Mockito | `@Primary` fake beans of domain interfaces |
| Calling real third-party APIs | Fakes in E2E, WireMock for adapter tests |
| `Thread.sleep` for async listeners | Awaitility `untilAsserted` |
| A different `@Import` / property set per test class | One shared configuration per test type, so the context is cached |
| Building a `SecurityContext` by hand in E2E tests | Real tokens from the login flow |
| Asserting only the status code of an error | Assert the ProblemDetail `code` too |
