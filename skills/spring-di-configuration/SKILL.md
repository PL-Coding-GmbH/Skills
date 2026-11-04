---
name: spring-di-configuration
description: |
  Spring dependency injection and application configuration for Kotlin backends - constructor injection, stereotype annotations, @Configuration and @Bean factories, typed immutable @ConfigurationProperties, profiles and application.yml layout, secrets via environment variables, the injected Clock, stateless singleton beans, and Spring proxy pitfalls (self-invocation with @Transactional, @Cacheable, @Async). Use this skill whenever creating a bean, injecting a dependency, adding a config value or property, writing a @Configuration class, touching application.yml or a profile, wiring a third-party SDK, or reading the current time. Trigger on phrases like "inject", "bean", "@Component", "@Service", "@Configuration", "@Bean", "@Value", "@ConfigurationProperties", "application.yml", "profile", "property", "environment variable", "secret", "Clock", "Instant.now", "@PostConstruct", "self-invocation", or "proxy".
---

# Spring DI and Configuration

## Principles

- **Constructor injection only.** Every dependency is a `private val` constructor parameter. No `lateinit var` with `@Autowired`, no `@Value` on properties, no setter injection.
- **Beans are stateless singletons.** Request-specific data lives in local variables and parameters, never in fields.
- **Configuration is typed.** Config values are bound into immutable `@ConfigurationProperties` classes, never read one by one with `@Value`.
- **Time comes from an injected `Clock`.** No `Instant.now()` without a clock.
- **Secrets come from environment variables.** They never appear in a committed file.

---

## Stereotypes

| Class | Annotation | Layer |
|---|---|---|
| Business logic, transactions | `@Service` | `service` |
| Repository adapter, HTTP client adapter, SDK wrapper | `@Component` | `infra` |
| REST controller | `@RestController` | `api` |
| Event listener, WebSocket handler, exception handler | `@Component` / `@RestControllerAdvice` | `api` |
| Factory for beans you can't annotate (third-party types) | `@Configuration(proxyBeanMethods = false)` + `@Bean` | wherever the bean belongs |

`@Repository` is not used. Spring Data interfaces need no annotation, and adapter classes are plain `@Component`s.

---

## Constructor Injection

```kotlin
@Service
class ChatService(
    private val chatRepository: ChatRepository,
    private val chatParticipantRepository: ChatParticipantRepository,
    private val eventPublisher: ApplicationEventPublisher,
    private val clock: Clock,
) {

    // ...
}
```

- Inject the **domain interface** (`ChatRepository`), never the `infra` class that implements it. Spring finds the single `@Component` that implements the interface.
- When two beans implement one interface, the interface is too broad. Split it before reaching for `@Qualifier` or `@Primary`.
- More than ~6 constructor parameters means the class does too much. Split it.
- Circular dependencies are a design error. Spring Boot refuses to start with one. Never enable `spring.main.allow-circular-references`.

---

## `@Configuration` and `@Bean`

Use a `@Bean` method when the bean is a third-party type, needs construction logic, or needs initialization:

```kotlin
@Configuration(proxyBeanMethods = false)
class FirebaseConfig {

    @Bean
    fun firebaseMessaging(properties: FirebaseProperties, resourceLoader: ResourceLoader): FirebaseMessaging {
        val credentials = resourceLoader.getResource(properties.credentialsPath).inputStream.use {
            GoogleCredentials.fromStream(it)
        }
        val app = FirebaseApp.initializeApp(
            FirebaseOptions.builder().setCredentials(credentials).build()
        )
        return FirebaseMessaging.getInstance(app)
    }
}
```

- `proxyBeanMethods = false` always. Beans reference each other through method parameters, never by calling another `@Bean` method.
- Initialize SDKs in a `@Bean` method, not in a `@PostConstruct` on a service. The consumer then injects the ready SDK client, and a test can provide a different bean.
- A `@Configuration` class lives in the layer of the beans it creates: `infra/config` for SDK clients, `:app` for cross-cutting beans.

### Cross-cutting beans in `:app`

```kotlin
@Configuration(proxyBeanMethods = false)
@EnableScheduling
@EnableAsync
class ApplicationConfig {

    @Bean
    fun clock(): Clock = Clock.systemUTC()
}
```

```kotlin
@SpringBootApplication
@ConfigurationPropertiesScan
class ChirpApplication

fun main(args: Array<String>) {
    runApplication<ChirpApplication>(*args)
}
```

---

## Typed Configuration Properties

One properties class per concern, immutable, validated at startup:

```kotlin
@ConfigurationProperties(prefix = "chirp.email")
@Validated
data class EmailProperties(
    @field:NotBlank
    val from: String,
    @field:NotBlank
    val baseUrl: String,
    val verificationExpiry: Duration = Duration.ofHours(24),
    val passwordResetExpiry: Duration = Duration.ofMinutes(30),
)
```

```yaml
chirp:
  email:
    from: mail@example.com
    base-url: "https://chirp.example.com"
    verification-expiry: 24h
    password-reset-expiry: 30m
```

- `val` properties and a single constructor. Spring binds through the constructor; no `var`, no `@Configuration` on the class.
- `@ConfigurationPropertiesScan` on the application class registers every properties class. Don't add `@EnableConfigurationProperties` per class.
- Use `Duration`, `DataSize`, enums, and lists instead of `Long` minutes or comma-separated strings. The unit then lives in the YAML value (`30m`), not in the property name (`expiry-minutes`).
- Prefix: `<app>.<module>.<concern>` for own properties (`chirp.chat.storage`). Third-party SDK settings follow the same scheme (`chirp.notification.firebase`), never a bare top-level key like `firebase:`.
- Inject the properties class where the values are needed. Properties classes live in the layer that uses them, usually `infra/config` or `service`.

`@Value` is acceptable only in a `@Bean` method parameter of a `@Configuration` class for a single one-off value. If you need two values from the same prefix, write a properties class.

---

## application.yml Layout

```
app/src/main/resources/
├── application.yml          ← Shared defaults for every environment
├── application-dev.yml      ← Local development overrides
└── application-prod.yml     ← Production overrides
```

- `application.yml` holds the structure and safe defaults. Profile files only override.
- **Secrets are only ever `${ENV_VAR}` references** with no default, so a missing secret fails at startup instead of running with a blank one: `password: ${POSTGRES_PASSWORD}`.
- Hosts, ports, and URLs that differ per environment go into the profile file or an env var. Values that are the same everywhere go into `application.yml`.
- Business modules ship no `application.yml`. Their config lives in `:app` under the module's prefix, so one place shows the whole app's configuration.
- Always set in `application.yml`:

```yaml
spring:
  threads:
    virtual:
      enabled: true
  jpa:
    open-in-view: false
```

---

## Time — the Injected `Clock`

Every class that reads the current time takes a `java.time.Clock` in its constructor:

```kotlin
val expiresAt = Instant.now(clock).plus(properties.verificationExpiry)
```

- Production gets `Clock.systemUTC()` from `ApplicationConfig`. Tests pass a fake clock (see **spring-unit-testing**).
- Domain models that need "now" for a check get it as a parameter: `fun isExpired(now: Instant) = now >= expiresAt`. They never read a clock themselves.
- Default parameter values (`createdAt: Instant = Instant.now()`) on entities and DTOs are not allowed either. The service sets the timestamp from its clock.

---

## Stateless Singletons

A singleton bean is called by many request threads at once.

- No `var` fields and no `mutableListOf()` / `HashMap` fields in a bean.
- If a bean must hold state (a WebSocket session registry, an in-memory retry queue), use `java.util.concurrent` types (`ConcurrentHashMap`, `ConcurrentHashMap.newKeySet()`, atomics) and keep every compound update inside one atomic call (`compute`, `merge`).
- State that must survive a restart or be shared between instances belongs in the database or Redis, not in a bean.

---

## Proxy Pitfalls

`@Transactional`, `@Cacheable`, `@CacheEvict`, `@Async`, and `@Retryable` work through Spring proxies. A call from one method of a bean to another method **of the same bean** bypasses the proxy, and the annotation silently does nothing.

```kotlin
@Service
class ChatMessageService(...) {

    fun deleteMessage(...) {
        // ...
        evictCache(chatId)   // ❌ self-invocation: @CacheEvict is ignored
    }

    @CacheEvict("messages", key = "#chatId")
    fun evictCache(chatId: ChatId) = Unit
}
```

Fix it by moving the annotated method to the bean whose job it is, and calling that bean. Don't inject a bean into itself, and don't use `AopContext.currentProxy()`.

Annotated methods must also be `public` and in an open class. The `kotlin-spring` compiler plugin opens `@Component`, `@Service`, `@Configuration`, and `@Transactional` classes automatically, so don't add `open` by hand.

---

## Naming Conventions

| Thing | Convention | Example |
|---|---|---|
| `@Configuration` class | `<Concern>Config` | `FirebaseConfig`, `SecurityConfig` |
| `@ConfigurationProperties` class | `<Concern>Properties` | `EmailProperties`, `StorageProperties` |
| Property prefix | `<app>.<module>.<concern>` | `chirp.chat.storage` |
| Environment variable | `SCREAMING_SNAKE_CASE` | `SUPABASE_SERVICE_KEY` |
| Implementation of a domain interface | describe what makes it unique, no `Impl` | `JpaChatRepository`, `SupabaseFileStorage` |

---

## Checklist: Adding a Bean or Config Value

- [ ] Dependencies are constructor parameters typed as domain interfaces where one exists
- [ ] No mutable fields, or only thread-safe ones with atomic updates
- [ ] Config values bound through a `<Concern>Properties` class with `@Validated`, never `@Value` fields
- [ ] Secrets referenced as `${ENV_VAR}` with no default
- [ ] The current time comes from an injected `Clock`
- [ ] No call from a bean into its own `@Transactional` / `@Cacheable` / `@Async` method
