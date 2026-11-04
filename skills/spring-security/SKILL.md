---
name: spring-security
description: |
  Authentication and authorization for Spring Boot Kotlin backends - stateless JWT access tokens via Spring Security's OAuth2 resource server (HMAC-signed, issued by the app itself), opaque rotating refresh tokens, the SecurityFilterChain in :app, public vs authenticated routes, reading the current user (requestUserId), password hashing, one-time tokens for email verification and password reset, resource ownership checks, custom authentication filters (API keys), and WebSocket handshake auth. Use this skill whenever touching login, registration, tokens, the security config, route protection, the current user, passwords, roles, API keys, CORS, or anything returning 401 or 403. Trigger on phrases like "security", "auth", "login", "register", "JWT", "access token", "refresh token", "SecurityFilterChain", "permitAll", "authenticated", "current user", "requestUserId", "password hash", "BCrypt", "API key", "filter", "OncePerRequestFilter", "401", "403", "role", "permission", "CORS", or "WebSocket auth".
---

# Spring Security

## Principles

- **Stateless.** No HTTP session, no CSRF tokens. Every request carries a bearer access token.
- **Use Spring Security's JWT support, don't hand-roll it.** Validation goes through the OAuth2 resource server (`JwtDecoder`), issuing through `JwtEncoder`. No custom filter that parses JWTs, and no catch-all `try/catch` around token parsing.
- **Two levels of authorization.** The filter chain decides *who may call a route at all* (public vs authenticated, roles). Services decide *whether this user may touch this resource* (ownership, membership) and throw domain exceptions.
- **Secrets never leave the server unhashed at rest.** Passwords, refresh tokens, and one-time tokens are stored as hashes.

---

## Dependencies

```kotlin
// :app and :common
implementation(libs.spring.boot.starter.security)
implementation(libs.spring.boot.starter.security.oauth2.resource.server)

// tests
testImplementation(libs.spring.boot.starter.security.test)
```

---

## Where Things Live

| Piece | Location |
|---|---|
| `SecurityFilterChain`, route rules | `:app` (`api/security/SecurityConfig`) |
| `JwtDecoder` bean, `JwtProperties`, `requestUserId` | `:common` (`infra/security`, `api`) |
| `JwtEncoder`, token issuing, login/refresh/logout | `:user` (`infra/security`, `service`) |
| Password hashing | `:user` (`domain` interface `PasswordHasher`, `infra` implementation) |
| Ownership checks | each module's services |

The filter chain sits in `:app` because it has to know every module's public routes.

---

## JWT Configuration

```kotlin
@ConfigurationProperties(prefix = "chirp.security.jwt")
@Validated
data class JwtProperties(
    @field:NotBlank
    val secretBase64: String,
    val accessTokenTtl: Duration = Duration.ofMinutes(15),
    val refreshTokenTtl: Duration = Duration.ofDays(30),
) {

    fun secretKey(): SecretKey = SecretKeySpec(Base64.getDecoder().decode(secretBase64), "HmacSHA256")
}
```

```yaml
chirp:
  security:
    jwt:
      secret-base64: ${JWT_SECRET_BASE64}
      access-token-ttl: 15m
```

The secret is at least 256 random bits (`openssl rand -base64 32`), only ever from the environment.

### Decoder (`:common`)

```kotlin
@Configuration(proxyBeanMethods = false)
class JwtDecoderConfig {

    @Bean
    fun jwtDecoder(properties: JwtProperties): JwtDecoder {
        return NimbusJwtDecoder
            .withSecretKey(properties.secretKey())
            .macAlgorithm(MacAlgorithm.HS256)
            .build()
            .apply {
                setJwtValidator(
                    DelegatingOAuth2TokenValidator(
                        JwtValidators.createDefault(),
                        JwtClaimValidator<String>(TOKEN_TYPE_CLAIM) { it == ACCESS_TOKEN_TYPE },
                    )
                )
            }
    }
}
```

The `type` claim check stops anything other than an access token from authenticating a request.

### Encoder and issuing (`:user`)

```kotlin
@Component
class JwtAccessTokenIssuer(
    private val jwtEncoder: JwtEncoder,
    private val properties: JwtProperties,
    private val clock: Clock,
) : AccessTokenIssuer {

    override fun issue(userId: UserId): AccessToken {
        val now = Instant.now(clock)
        val expiresAt = now.plus(properties.accessTokenTtl)
        val claims = JwtClaimsSet.builder()
            .subject(userId.toString())
            .claim(TOKEN_TYPE_CLAIM, ACCESS_TOKEN_TYPE)
            .issuedAt(now)
            .expiresAt(expiresAt)
            .build()
        val header = JwsHeader.with(MacAlgorithm.HS256).build()

        val token = jwtEncoder.encode(JwtEncoderParameters.from(header, claims)).tokenValue
        return AccessToken(value = token, expiresAt = expiresAt)
    }
}
```

```kotlin
@Bean
fun jwtEncoder(properties: JwtProperties): JwtEncoder =
    NimbusJwtEncoder(ImmutableSecret<SecurityContext>(properties.secretKey()))
```

- Access tokens are short-lived (≈15 min) and carry only `sub` (the user ID), `type`, `iat`, `exp`, plus roles if the app has them. No email, no username, no personal data.
- `AccessTokenIssuer` is a domain interface, so `AuthService` stays unit-testable with a fake.

---

## Refresh Tokens

Refresh tokens are **opaque random strings**, not JWTs:

- Generate 32 bytes from `SecureRandom`, URL-safe Base64 without padding.
- Store only the SHA-256 hash, with user ID and expiry. The raw value goes to the client once.
- **Rotate on every refresh.** Delete the presented token and issue a new pair in the same transaction. An unknown or expired token is `401 INVALID_TOKEN`.
- Delete all of a user's refresh tokens on password change and password reset.
- Logout deletes the presented token.
- A scheduled job deletes expired rows.

One-time tokens for email verification and password reset follow the same rules: random, stored hashed, single use (`usedAt`), short expiry, all previous tokens of the user invalidated when a new one is issued.

---

## Passwords

```kotlin
// domain
interface PasswordHasher {

    fun hash(rawPassword: String): String
    fun matches(rawPassword: String, hash: String): Boolean
}

// infra
@Component
class BCryptPasswordHasher : PasswordHasher {

    private val encoder = BCryptPasswordEncoder()

    override fun hash(rawPassword: String): String = requireNotNull(encoder.encode(rawPassword))
    override fun matches(rawPassword: String, hash: String): Boolean = encoder.matches(rawPassword, hash)
}
```

- Login failures return the same `401 INVALID_CREDENTIALS` whether the email is unknown or the password is wrong. Never reveal which.
- "Forgot password" always answers success, whether or not the email exists.
- Public auth endpoints (register, login, refresh, forgot password, resend verification) are rate limited per IP and, where an email is involved, per email.

---

## Filter Chain (`:app`)

```kotlin
@Configuration(proxyBeanMethods = false)
@EnableWebSecurity
class SecurityConfig {

    @Bean
    fun securityFilterChain(http: HttpSecurity): SecurityFilterChain {
        http {
            csrf { disable() }
            sessionManagement { sessionCreationPolicy = SessionCreationPolicy.STATELESS }
            authorizeHttpRequests {
                authorize("/api/auth/change-password", authenticated)
                authorize("/api/auth/**", permitAll)
                authorize("/actuator/health", permitAll)
                authorize("/error", permitAll)
                authorize(anyRequest, authenticated)
            }
            oauth2ResourceServer {
                jwt { }
            }
        }
        return http.build()
    }
}
```

- Use the Kotlin DSL (`import org.springframework.security.config.annotation.web.invoke`).
- **Deny by default.** `anyRequest` is `authenticated`. Every public route is listed explicitly.
- Rules are matched in order, so the more specific rule comes first (`/api/auth/change-password` before `/api/auth/**`).
- Missing or invalid tokens get `401` with a `WWW-Authenticate` header from the resource server's entry point. Don't replace it with a custom entry point that writes JSON by hand.
- CSRF is disabled only because the API is stateless and uses bearer tokens. If cookies ever carry auth, CSRF protection must come back.
- CORS is configured only when browser clients call the API, with an explicit list of origins from configuration. Never `*` with credentials.

---

## The Current User

```kotlin
// common.api
val requestUserId: UserId
    get() {
        val authentication = SecurityContextHolder.getContext().authentication as? JwtAuthenticationToken
            ?: throw UnauthorizedException()
        return UUID.fromString(authentication.token.subject)
    }
```

- Only controllers and other `api` code read `requestUserId`. Services receive the user ID as a parameter, so they work the same from listeners and jobs, and tests don't need a security context.
- Never trust a user ID from the request body or path for "who is acting".

---

## Resource Authorization in Services

```kotlin
val chat = chatRepository.findByIdForParticipant(chatId, requestUserId)
    ?: throw ChatNotFoundException(chatId)
```

- Ownership and membership checks are part of the query or an explicit check in the service, before any change.
- Prefer `404` over `403` when a resource belongs to someone else, so IDs can't be probed (see **spring-api-layer**).
- Roles, if the app has them, go into the token as a claim, are mapped to authorities with a `JwtAuthenticationConverter`, and are checked in the filter chain (`hasRole("ADMIN")`). Don't scatter `@PreAuthorize` for ownership logic.

---

## Custom Authentication Filters (API keys, service tokens)

When a client can't use JWTs (a partner integration, an internal service):

```kotlin
@Component
class ApiKeyAuthenticationFilter(
    private val apiKeyService: ApiKeyService,
) : OncePerRequestFilter() {

    override fun doFilterInternal(request: HttpServletRequest, response: HttpServletResponse, chain: FilterChain) {
        val apiKey = request.getHeader(API_KEY_HEADER)
        if (apiKey != null) {
            val client = apiKeyService.findActiveClient(apiKey)
            if (client != null) {
                SecurityContextHolder.getContext().authentication = ApiKeyAuthentication(client)
            }
        }
        chain.doFilter(request, response)
    }
}
```

- A filter only **establishes identity**. It never writes an error response itself. Whether a route needs authentication is decided by the filter chain rules, and the entry point writes the `401`.
- Register it in the chain with `addFilterBefore<BearerTokenAuthenticationFilter>(apiKeyAuthenticationFilter)`.
- A `@Component` filter is also registered as a plain servlet filter by Spring Boot, so it would run twice. Disable that with a `FilterRegistrationBean` with `isEnabled = false`, or don't make the filter a `@Component` and create it in `SecurityConfig`.
- API keys are stored hashed and compared via the hash, like refresh tokens.

---

## WebSocket Handshake

Browsers can't set headers on WebSocket connections, and mobile clients can. Pick one transport for the token and validate it **during the handshake** with the same `JwtDecoder`, in a `HandshakeInterceptor`. Reject the handshake when the token is missing or invalid. Don't accept the connection first and close it afterwards.

---

## Testing

- E2E tests get real tokens through the API (register, verify, log in) or from a small test helper that uses the real `JwtEncoder`. They don't mock the security context (see **spring-integration-testing**).
- Every protected endpoint has a test that it answers `401` without a token.
- Every ownership rule has a test where another user gets `404`/`403`.

---

## Naming Conventions

| Thing | Convention | Example |
|---|---|---|
| Filter chain config | `SecurityConfig` | |
| Token issuer interface / impl | `AccessTokenIssuer` / `JwtAccessTokenIssuer` | |
| Password hashing interface / impl | `PasswordHasher` / `BCryptPasswordHasher` | |
| Custom filter | `<Scheme>AuthenticationFilter` | `ApiKeyAuthenticationFilter` |
| Claim names | constants in `common` | `TOKEN_TYPE_CLAIM`, `ACCESS_TOKEN_TYPE` |

---

## Checklist: Adding or Changing a Protected Route

- [ ] Route is covered by `anyRequest().authenticated()`, or explicitly listed as public with a reason
- [ ] Controller reads the acting user from `requestUserId`
- [ ] Service checks ownership/membership before reading or changing the resource
- [ ] Nothing sensitive (tokens, passwords, emails) is logged
- [ ] Tests for `401` without a token and for access by another user
