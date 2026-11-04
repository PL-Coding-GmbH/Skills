---
name: spring-api-layer
description: |
  API layer for Spring Boot Kotlin backends - REST controllers, request and response DTOs, Bean Validation, api mappers, the current user, pagination parameters, and the error contract (domain exceptions mapped to RFC 9457 ProblemDetail with a stable error code in per-module @RestControllerAdvice classes). Use this skill whenever adding or changing an endpoint, writing a controller, creating a request or response DTO, validating input, mapping a domain model to a DTO, adding an exception handler, defining an error code, or deciding which HTTP status an error gets. Trigger on phrases like "add an endpoint", "controller", "REST API", "@RestController", "@GetMapping", "@PostMapping", "request body", "DTO", "response", "validation", "@Valid", "@NotBlank", "custom constraint", "exception handler", "@RestControllerAdvice", "ProblemDetail", "error response", "error code", "status code", "404", "400", or "pagination".
---

# Spring API Layer

The `api` package of a module is everything that receives input from outside the module: REST controllers, WebSocket handlers, and listeners for other modules' events (see **spring-service-layer**). This skill covers REST.

## Principles

- **Controllers are thin.** Read input, call one service method, map the result to a DTO. No business rules, no repository access, no `@Transactional`.
- **DTOs define the HTTP contract.** A controller never returns a domain model or an entity, so changing a domain model never silently changes an API response.
- **Errors are domain exceptions.** Services throw them. The api layer maps them to HTTP in one place per module. Controllers never build error responses by hand.

---

## Controllers

```kotlin
@RestController
@RequestMapping("/api/chats")
class ChatController(
    private val chatService: ChatService,
) {

    @GetMapping("/{chatId}")
    fun getChat(@PathVariable chatId: ChatId): ChatDto {
        return chatService
            .getChat(chatId = chatId, requestUserId = requestUserId)
            .toChatDto()
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    fun createChat(@Valid @RequestBody body: CreateChatRequest): ChatDto {
        return chatService
            .createChat(
                creatorId = requestUserId,
                otherUserIds = body.otherUserIds.toSet(),
            )
            .toChatDto()
    }

    @DeleteMapping("/{chatId}/participants/me")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    fun leaveChat(@PathVariable chatId: ChatId) {
        chatService.removeParticipant(chatId = chatId, userId = requestUserId)
    }
}
```

- Base path `/api/<plural-resource>`. Sub-resources nest (`/api/chats/{chatId}/messages`). Actions that aren't CRUD are a sub-resource noun or a verb segment as a last resort (`/api/auth/refresh`).
- Return the DTO directly. Use `@ResponseStatus` for a fixed non-200 status (`201` on create, `204` on delete). Use `ResponseEntity` only when headers or the status depend on the outcome.
- Pass request fields to the service as named arguments. Don't map a request DTO into a domain model in the controller, unless the service genuinely takes that model.
- Nothing in a controller returns `null` to mean "not found". The service throws a domain exception (`ChatNotFoundException`), and the module's exception handler turns it into `404`. Never throw `ResponseStatusException`.
- The authenticated user comes from `requestUserId` (see **spring-security**). Never accept the acting user's ID from the request body or a path variable.

---

## Request and Response DTOs

```kotlin
data class CreateChatRequest(
    @field:Size(min = 1, max = 50, message = "A chat needs between 1 and 50 other participants")
    val otherUserIds: List<UserId>,
)

data class ChatDto(
    val id: ChatId,
    val participants: List<ChatParticipantDto>,
    val lastMessage: ChatMessageDto?,
    val lastActivityAt: Instant,
)
```

- Incoming bodies: `<Action><Resource>Request` (`CreateChatRequest`, `ChangePasswordRequest`). Outgoing bodies: `<Resource>Dto` (`ChatDto`). A DTO is never used for both directions.
- Plain `data class` with `val`s. Required fields are non-null with no default. A missing required field then fails deserialization and becomes a `400` automatically.
- API enums are their own DTO enums (`PlatformDto`), mapped to domain enums. Renaming a domain enum constant must not break clients.
- `Instant`s go over the wire as ISO-8601 UTC strings (Jackson 3's default). IDs are UUID strings.
- DTOs live in `api/dto`, one file per DTO. Small enums used by only one DTO may share its file.

---

## Validation

```kotlin
@PostMapping("/register")
fun register(@Valid @RequestBody body: RegisterRequest): UserDto { ... }

data class RegisterRequest(
    @field:Email(message = "Must be a valid email address")
    val email: String,
    @field:Size(min = 3, max = 20, message = "Username must be between 3 and 20 characters")
    val username: String,
    @field:Password
    val password: String,
)
```

- Every `@RequestBody` whose type has constraints is annotated `@Valid`. Without it, the constraints compile and do nothing.
- Constraint annotations on constructor properties always use the `@field:` use-site target. That's where Hibernate Validator looks, whatever the compiler defaults are.
- Nested objects and lists of objects get `@field:Valid` so their constraints run too.
- Constraints on `@RequestParam` and `@PathVariable` (`@Max(100) pageSize: Int`) are validated by Spring MVC's built-in method validation. A violation raises `HandlerMethodValidationException`, which the common handler maps to `400`.
- Validation is for **shape**: format, length, ranges, required. Rules that need data (email already taken, user is a chat member) belong in the service and throw domain exceptions.
- Reusable rules become a custom constraint in `api/validation`:

```kotlin
@Target(AnnotationTarget.FIELD, AnnotationTarget.VALUE_PARAMETER)
@Retention(AnnotationRetention.RUNTIME)
@Constraint(validatedBy = [])
@Pattern(regexp = "^(?=.*[\\d\\W]).{8,}$")
@ReportAsSingleViolation
annotation class Password(
    val message: String = "Password must be at least 8 characters and contain a digit or special character",
    val groups: Array<KClass<*>> = [],
    val payload: Array<KClass<out Payload>> = [],
)
```

---

## Mappers

Extension functions in `api/mapper`, one file per domain area:

```kotlin
fun Chat.toChatDto(): ChatDto {
    return ChatDto(
        id = id,
        participants = participants.map { it.toChatParticipantDto() },
        lastMessage = lastMessage?.toChatMessageDto(),
        lastActivityAt = lastActivityAt,
    )
}

fun PlatformDto.toPlatform(): DeviceToken.Platform {
    return when (this) {
        PlatformDto.ANDROID -> DeviceToken.Platform.ANDROID
        PlatformDto.IOS -> DeviceToken.Platform.IOS
    }
}
```

- Name the function after the **target** type: `toChatDto()`, `toPlatform()`.
- Enum mappers use an exhaustive `when` with no `else`, so a new constant fails compilation at every mapper.
- Mappers are pure. No service calls, no clock, no I/O.

---

## Pagination

Lists that grow without bound (messages, notifications) use **keyset pagination**, never offset pagination:

```kotlin
@GetMapping("/{chatId}/messages")
fun getMessages(
    @PathVariable chatId: ChatId,
    @RequestParam before: Instant?,
    @RequestParam(defaultValue = "20") @Min(1) @Max(100) pageSize: Int,
): List<ChatMessageDto> { ... }
```

- The cursor is the sort key of the last item the client has (`before`). An absent cursor means "newest page".
- Every page size has a hard maximum.
- Small bounded lists (a user's chats) return everything without paging.

---

## Error Contract — ProblemDetail

Every error response is an RFC 9457 `application/problem+json` body with one extra property, `code`. Clients switch on `code`, never on `detail` text.

```json
{
  "type": "about:blank",
  "title": "Not Found",
  "status": 404,
  "detail": "Chat not found",
  "instance": "/api/chats/3f2a...",
  "code": "CHAT_NOT_FOUND"
}
```

Validation failures add an `errors` list:

```json
{
  "status": 400,
  "title": "Bad Request",
  "detail": "Request validation failed",
  "code": "VALIDATION_FAILED",
  "errors": [{ "field": "email", "message": "Must be a valid email address" }]
}
```

### Shared helper (`common.api`)

```kotlin
fun problemDetail(status: HttpStatus, code: String, detail: String?): ProblemDetail {
    return ProblemDetail.forStatusAndDetail(status, detail).apply {
        setProperty("code", code)
    }
}
```

### Module exception handler

Each module maps **its own** domain exceptions in `api/exception/<Module>ExceptionHandler`:

```kotlin
@RestControllerAdvice
@Order(Ordered.HIGHEST_PRECEDENCE)
class ChatExceptionHandler {

    @ExceptionHandler(ChatNotFoundException::class)
    fun onChatNotFound(e: ChatNotFoundException) =
        problemDetail(HttpStatus.NOT_FOUND, "CHAT_NOT_FOUND", e.message)

    @ExceptionHandler(InvalidChatSizeException::class)
    fun onInvalidChatSize(e: InvalidChatSizeException) =
        problemDetail(HttpStatus.BAD_REQUEST, "INVALID_CHAT_SIZE", e.message)
}
```

- `@RestControllerAdvice` is required. A handler class without it compiles and is never called.
- Returning a `ProblemDetail` sets the response status from it, so no `@ResponseStatus` is needed.
- One `@ExceptionHandler` per exception type, so every exception gets its own `code`.

### Common exception handler (`common.api`)

Handles Spring MVC's own exceptions, validation, the shared exceptions from `common.domain.exception`, and anything nobody else handled:

```kotlin
@RestControllerAdvice
@Order(Ordered.LOWEST_PRECEDENCE)
class CommonExceptionHandler : ResponseEntityExceptionHandler() {

    override fun handleMethodArgumentNotValid(
        ex: MethodArgumentNotValidException,
        headers: HttpHeaders,
        status: HttpStatusCode,
        request: WebRequest,
    ): ResponseEntity<Any>? {
        val body = problemDetail(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED", "Request validation failed").apply {
            setProperty(
                "errors",
                ex.bindingResult.fieldErrors.map { mapOf("field" to it.field, "message" to it.defaultMessage) }
            )
        }
        return ResponseEntity.badRequest().body(body)
    }

    @ExceptionHandler(ForbiddenException::class)
    fun onForbidden(e: ForbiddenException) =
        problemDetail(HttpStatus.FORBIDDEN, "FORBIDDEN", e.message)

    @ExceptionHandler(AccessDeniedException::class)
    fun onAccessDenied(e: AccessDeniedException) =
        problemDetail(HttpStatus.FORBIDDEN, "FORBIDDEN", "You are not allowed to do that")

    @ExceptionHandler(Exception::class)
    fun onUnexpected(e: Exception): ProblemDetail {
        logger.error("Unhandled exception", e)
        return problemDetail(HttpStatus.INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", "Something went wrong")
    }
}
```

- Extending `ResponseEntityExceptionHandler` turns every Spring MVC exception (malformed JSON, missing parameter, wrong method, method validation) into a `ProblemDetail`. Spring Boot's own problem-details handler backs off when this bean exists, so don't also set `spring.mvc.problemdetails.enabled`.
- The `@Order` values matter. Spring picks the first advice that can handle an exception, and the catch-all `Exception` handler can handle everything. Module handlers must come first.
- `logger` is inherited from `ResponseEntityExceptionHandler`. Declaring your own `logger` property clashes with it.
- The catch-all never puts `e.message` into the response. Internal messages leak implementation details.
- `AccessDeniedException` must be mapped explicitly. Otherwise the catch-all turns a `403` from method security into a `500`.

### Status code mapping

| Situation | Status | Example code |
|---|---|---|
| Malformed input, failed validation | `400` | `VALIDATION_FAILED`, `INVALID_CHAT_SIZE` |
| Not authenticated, bad credentials, bad token | `401` | `INVALID_CREDENTIALS`, `INVALID_TOKEN` |
| Authenticated but not allowed | `403` | `FORBIDDEN`, `EMAIL_NOT_VERIFIED` |
| Resource doesn't exist **or the caller can't see it** | `404` | `CHAT_NOT_FOUND` |
| State conflict (duplicate, same password) | `409` | `USER_ALREADY_EXISTS` |
| Rate limited | `429` | `RATE_LIMIT_EXCEEDED` |
| Third-party dependency failed | `502` / `503` | `STORAGE_UNAVAILABLE` |
| Bug | `500` | `INTERNAL_ERROR` |

Return `404` rather than `403` when revealing that a resource exists would leak information (another user's chat).

Error codes are `SCREAMING_SNAKE_CASE`, specific to the failure, and never renamed once shipped: clients depend on them.

---

## Naming Conventions

| Thing | Convention | Example |
|---|---|---|
| Controller | `<Resource>Controller` | `ChatController` |
| Request body | `<Action><Resource>Request` | `CreateChatRequest` |
| Response body | `<Resource>Dto` | `ChatDto` |
| API enum | `<Name>Dto` | `PlatformDto` |
| Mapper | extension fun named after the target | `fun Chat.toChatDto()` |
| Exception handler | `<Module>ExceptionHandler` | `ChatExceptionHandler` |
| Error code | `SCREAMING_SNAKE_CASE` | `CHAT_NOT_FOUND` |

---

## Checklist: Adding an Endpoint

- [ ] Controller method calls exactly one service method and returns a DTO
- [ ] Request DTO named `<Action><Resource>Request`, constraints with `@field:`, `@Valid` on the parameter
- [ ] Response DTO named `<Resource>Dto`, mapped by an extension function in `api/mapper`
- [ ] Acting user from `requestUserId`, never from the request
- [ ] `@ResponseStatus` for `201` / `204` where it applies
- [ ] Every new domain exception the service can throw is mapped in the module's exception handler with its own `code`
- [ ] Route is public or authenticated as intended in the security config (see **spring-security**)
- [ ] An E2E test covers the success response and each error `code` (see **spring-integration-testing**)
