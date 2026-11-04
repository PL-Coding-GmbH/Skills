---
name: spring-rest-client
description: |
  Calling third-party HTTP APIs from Spring Boot 4 Kotlin backends with declarative HTTP service clients - @HttpExchange interfaces backed by RestClient, @ImportHttpServices groups, spring.http.serviceclient properties for base URL and timeouts, auth headers via RestClientHttpServiceGroupConfigurer, provider DTOs, adapters behind domain interfaces, error translation, and retries. Use this skill whenever integrating an external API or SaaS (storage, payments, email provider, maps, AI APIs), writing an HTTP client, adding an outgoing REST call, configuring a base URL or timeout, or handling errors from a remote service. Trigger on phrases like "call an API", "external API", "third-party", "HTTP client", "REST client", "RestClient", "@HttpExchange", "@GetExchange", "@PostExchange", "HTTP interface", "ImportHttpServices", "base URL", "timeout", "integrate with", "webhook call", or "API key header".
---

# Spring REST Client (HTTP Service Clients)

## Principles

- **Declarative clients.** Every external API is a Kotlin interface annotated with `@HttpExchange`, backed by `RestClient`. No hand-written `.get().uri().retrieve()` chains in business code.
- **External APIs hide behind a domain interface.** Services depend on `FileStorage`, not on Supabase. The HTTP interface and its DTOs stay in `infra`.
- **Every remote failure becomes a domain exception** at the adapter. No `RestClientException` escapes `infra`.
- **Every client has explicit timeouts.**
- **No remote call inside a database transaction** (see **spring-service-layer**).

---

## Dependency

```kotlin
// <module>/build.gradle.kts
implementation(libs.spring.boot.starter.restclient)
```

---

## Layout

```
chat
├── domain/storage/FileStorage.kt                ← Interface the service uses
└── infra/http/supabase/
    ├── SupabaseStorageApi.kt                    ← @HttpExchange interface
    ├── SupabaseDtos.kt                          ← Provider request/response DTOs (internal)
    ├── SupabaseFileStorage.kt                   ← Adapter: implements FileStorage
    ├── SupabaseClientConfig.kt                  ← @ImportHttpServices + auth configurer
    └── SupabaseProperties.kt                    ← @ConfigurationProperties
```

One package per provider. The HTTP interface, its DTOs and the adapter are `internal`, so no other module can reach them. Spring still finds and injects them.

---

## Domain Interface

```kotlin
interface FileStorage {

    fun createUploadUrl(path: String, expiresIn: Duration): UploadUrl
    fun delete(path: String)
}
```

Speak domain terms. No provider names, no HTTP types, no provider DTOs.

---

## HTTP Interface

```kotlin
@HttpExchange("/storage/v1/object")
internal interface SupabaseStorageApi {

    @PostExchange("/upload/sign/{bucket}/{fileName}")
    fun createSignedUploadUrl(
        @PathVariable bucket: String,
        @PathVariable fileName: String,
        @RequestBody body: CreateSignedUploadUrlRequest,
    ): SignedUploadUrlResponse

    @DeleteExchange("/{bucket}/{fileName}")
    fun deleteObject(
        @PathVariable bucket: String,
        @PathVariable fileName: String,
    )
}
```

```kotlin
internal data class CreateSignedUploadUrlRequest(
    val expiresIn: Long,
)

internal data class SignedUploadUrlResponse(
    val url: String,
)
```

- Provider DTOs mirror the provider's JSON exactly. Use `@JsonProperty` for names that aren't valid Kotlin or don't follow camelCase. Never reuse your own API DTOs or domain models here.
- Response DTOs only declare the fields you read. Jackson ignores the rest, so a provider adding fields doesn't break you.
- Make fields the provider may omit nullable. A non-null field the provider leaves out fails deserialization.
- Return `Unit` when the body is irrelevant, `ResponseEntity<T>` only when you need headers or the exact status.

---

## Registration and Configuration

```kotlin
@Configuration(proxyBeanMethods = false)
@ImportHttpServices(group = "supabase", types = [SupabaseStorageApi::class])
class SupabaseClientConfig {

    @Bean
    fun supabaseClientConfigurer(properties: SupabaseProperties) =
        RestClientHttpServiceGroupConfigurer { groups ->
            groups.filterByName("supabase").forEachClient { _, builder ->
                builder.defaultHeader(HttpHeaders.AUTHORIZATION, "Bearer ${properties.serviceKey}")
            }
        }
}
```

```kotlin
@ConfigurationProperties(prefix = "chirp.chat.supabase")
@Validated
data class SupabaseProperties(
    @field:NotBlank
    val serviceKey: String,
    @field:NotBlank
    val bucket: String,
    @field:NotBlank
    val publicUrl: String,
)
```

```yaml
spring:
  http:
    clients:
      connect-timeout: 2s
      read-timeout: 10s
    serviceclient:
      supabase:
        base-url: "https://xyz.supabase.co"
        read-timeout: 5s

chirp:
  chat:
    supabase:
      service-key: ${SUPABASE_SERVICE_KEY}
      bucket: profile-pictures
      public-url: "https://xyz.supabase.co/storage/v1/object/public"
```

- One **group** per provider, named after it. The group name connects the `@ImportHttpServices` declaration, the `spring.http.serviceclient.<group>` properties, and the configurer.
- `spring.http.clients.*` sets defaults for every client. Per-group values override them. Always set a connect and a read timeout. A remote API that hangs must not hang the request.
- Base URL and timeouts go in `spring.http.serviceclient.<group>`. Secrets and provider settings go in the module's own properties class.
- Auth headers, request interceptors, and other per-provider client tweaks go in a `RestClientHttpServiceGroupConfigurer` filtered to the group. Never configure one provider's credentials globally.

---

## Adapter and Error Translation

```kotlin
@Component
internal class SupabaseFileStorage(
    private val api: SupabaseStorageApi,
    private val properties: SupabaseProperties,
) : FileStorage {

    private val logger = LoggerFactory.getLogger(javaClass)

    override fun createUploadUrl(path: String, expiresIn: Duration): UploadUrl {
        val response = callSupabase {
            api.createSignedUploadUrl(
                bucket = properties.bucket,
                fileName = path,
                body = CreateSignedUploadUrlRequest(expiresIn = expiresIn.seconds),
            )
        }
        return UploadUrl(
            uploadUrl = response.url,
            publicUrl = "${properties.publicUrl}/${properties.bucket}/$path",
        )
    }

    override fun delete(path: String) {
        callSupabase {
            try {
                api.deleteObject(bucket = properties.bucket, fileName = path)
            } catch (e: HttpClientErrorException.NotFound) {
                logger.info("File {} was already deleted", path)
            }
        }
    }

    private fun <T> callSupabase(call: () -> T): T {
        return try {
            call()
        } catch (e: RestClientException) {
            logger.warn("Supabase storage call failed", e)
            throw StorageUnavailableException()
        }
    }
}
```

What the client throws:

| Situation | Exception |
|---|---|
| `4xx` response | `HttpClientErrorException` (subclasses per status: `.NotFound`, `.Conflict`, ...) |
| `5xx` response | `HttpServerErrorException` |
| Connection refused, timeout | `ResourceAccessException` |
| Body can't be read | `RestClientException` |

All extend `RestClientException`.

- Catch the specific statuses that mean something for your domain (`404` on delete = already gone) and translate them into domain results or exceptions.
- Translate everything else into one domain exception per integration (`StorageUnavailableException`), mapped to `502`/`503` in the module's exception handler.
- Log the failure once, at the adapter, with the exception. Never log request bodies or headers: they contain credentials and personal data.
- Don't check `response.statusCode.isError` after `retrieve()`. The default status handler has already thrown by then.

---

## Retries

- Retry only **idempotent** calls (`GET`, `PUT`, `DELETE`) and only on `ResourceAccessException` or `5xx`. Never retry a `POST` that creates something unless the provider supports idempotency keys.
- Use Spring Framework's `@Retryable` (with `@EnableResilientMethods` in `:app`) on the adapter method, with a small `maxRetries` and backoff. No hand-written retry loops.
- Retries multiply latency. With a 5s read timeout and 3 attempts, the caller may wait 15s. Size timeouts with that in mind.

---

## Testing

- **Unit tests** of services use a fake `FileStorage` (see **spring-unit-testing**). They never see the HTTP interface.
- **Adapter integration tests** run the real adapter against WireMock, pointing `spring.http.serviceclient.<group>.base-url` at it. They verify paths, headers, body mapping, and error translation (see **spring-integration-testing**).
- **E2E tests** replace the adapter with the fake `FileStorage` bean, so the suite never calls a real provider.

---

## Naming Conventions

| Thing | Convention | Example |
|---|---|---|
| Domain interface | role noun | `FileStorage`, `PushNotificationSender` |
| HTTP interface | `<Provider><Area>Api` | `SupabaseStorageApi` |
| Provider DTOs | mirror provider naming + `Request`/`Response` | `SignedUploadUrlResponse` |
| Adapter | `<Provider><Role>` | `SupabaseFileStorage` |
| Config | `<Provider>ClientConfig` | `SupabaseClientConfig` |
| Group name | provider name, lowercase | `supabase` |
| Domain exception | `<Role>UnavailableException` | `StorageUnavailableException` |

---

## Checklist: Adding an External API

- [ ] Domain interface in `domain` in domain terms; services depend only on it
- [ ] `@HttpExchange` interface + `internal` provider DTOs in `infra/http/<provider>`
- [ ] `@ImportHttpServices(group = "<provider>")`; base URL and timeouts under `spring.http.serviceclient.<provider>`
- [ ] Credentials from env through a properties class, applied by a group-filtered configurer
- [ ] Adapter translates every `RestClientException` into a domain exception, mapped in the exception handler
- [ ] Not called inside a `@Transactional` method
- [ ] Retries only for idempotent calls
- [ ] Fake for unit tests, WireMock integration test for the adapter
