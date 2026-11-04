---
name: spring-module-structure
description: |
  Module layout, package and layer structure, dependency rules, Gradle convention plugins, and version catalog for Spring Boot Kotlin backends built as a modular monolith (one deployable app, several business modules). Use this skill whenever setting up a new Spring Boot project, adding a business module, deciding where a class or package belongs, deciding how two modules may talk to each other, adding a dependency, or touching build-logic, settings.gradle.kts, or libs.versions.toml. Trigger on phrases like "set up the project", "add a module", "new business module", "where does X live", "project structure", "package structure", "layer", "convention plugin", "build-logic", "version catalog", "libs.versions.toml", "add a dependency", "add a starter", "multi-module", or "modular monolith".
---

# Spring Boot Module Structure

## Core Philosophy

- **Modular monolith.** One deployable Spring Boot app, split into Gradle modules by **business capability** (`user`, `chat`, `notification`), never by technical layer.
- **Layers live inside each module as packages**, not as separate Gradle modules: `api`, `service`, `domain`, `infra`.
- **Business modules never depend on each other.** They share only `:common`, and talk at runtime through Spring application events (see **spring-service-layer**).
- **Each module owns its data.** It has its own Postgres schema and its own Flyway migrations. No module reads or writes another module's tables.
- **`:app` only assembles.** It holds the `@SpringBootApplication` class, cross-cutting config (security filter chain, `Clock`, async), `application.yml`, and end-to-end tests. No business logic.

---

## Module Layout

```
:app                 ← @SpringBootApplication, application*.yml, SecurityFilterChain, E2E tests
:common              ← Shared kernel: ID typealiases, cross-module events, base exceptions, shared api helpers
:user                ← Business module
:chat                ← Business module
:notification        ← Business module
build-logic/         ← Included build with convention plugins
gradle/libs.versions.toml
```

Create a new business module when a capability has its own data, its own vocabulary, and could in principle be owned by a separate team. Don't create a module for a single class or a technical concern. A helper used by two modules goes to `:common` only if it is part of the shared kernel (IDs, events, error contract). Otherwise each module keeps its own copy.

---

## Package Structure

Every module has its own root package: `com.<company>.<app>.<module>`. Two modules never share a package. Shared packages break the layer checks and make it unclear which module owns a class.

```
com.<company>.<app>.chat
├── api                         ← Everything that receives input from outside the module
│   ├── controller/             ChatController
│   ├── dto/                    CreateChatRequest, ChatDto
│   ├── mapper/                 ChatDtoMappers.kt
│   ├── exception/              ChatExceptionHandler
│   ├── event/                  Listeners for other modules' events (UserEventListener)
│   └── websocket/              (if the module has one)
├── service/                    ChatService, ChatMessageService
├── domain
│   ├── model/                  Chat, ChatMessage, ChatParticipant
│   ├── exception/              ChatNotFoundException
│   ├── event/                  Module-internal events (MessageDeletedEvent)
│   └── repository/             ChatRepository, ChatMessageRepository (interfaces)
└── infra
    ├── database/
    │   ├── entity/             ChatEntity
    │   ├── repository/         SpringDataChatRepository, JpaChatRepository
    │   └── mapper/             ChatEntityMappers.kt
    ├── http/                   Third-party HTTP clients (HTTP interfaces + adapters)
    └── config/                 Module-specific @Configuration / @ConfigurationProperties
```

`:common` uses the same layer names under `com.<company>.<app>.common`:

```
com.<company>.<app>.common
├── api/                        CommonExceptionHandler, requestUserId, ErrorCode
├── domain
│   ├── type/                   UserId, ChatId (typealiases)
│   ├── event/                  Cross-module events, one sealed interface per publishing module
│   └── exception/              Base exceptions (NotFoundException, ForbiddenException, ...)
└── infra/                      Shared infrastructure that every module needs
```

Package names are lowercase, one word where possible, never `snake_case` (`exception`, not `exception_handling`). Use singular (`model`, `event`, `entity`) everywhere.

---

## Layer Rules

| Layer | Contains | May depend on |
|---|---|---|
| `domain` | Models, domain exceptions, events, repository interfaces | Nothing but Kotlin, `java.*`, and `common.domain` |
| `service` | Business logic, transactions, event publishing | `domain` |
| `infra` | JPA entities and adapters, HTTP clients, external SDKs | `domain` |
| `api` | Controllers, DTOs, exception handlers, event listeners, WebSocket | `service`, `domain` |

- `domain` imports no Spring and no `jakarta.persistence`. It is plain Kotlin.
- `service` depends on `domain` interfaces, never on `infra` classes. Spring wires the `infra` implementation in. This is what makes services unit-testable with fakes (see **spring-unit-testing**).
- JPA entities never leave `infra`. HTTP types (`ResponseEntity`, `HttpStatus`, `ResponseStatusException`, servlet types) never appear outside `api`.
- Controllers never inject repositories.

If the project uses the custom detekt rule set, `LayerDependency`, `PersistenceTypeLeaksOutOfInfra`, `NoHttpTypesOutsideApiLayer` and `ControllerMustNotInjectRepository` enforce these rules. Configure `LayerDependency` as:

```yaml
LayerDependency:
  active: true
  allowedDependencies:
    - 'domain ->'
    - 'service -> domain'
    - 'infra -> domain'
    - 'api -> service, domain'
  forbiddenPackages:
    - 'domain -> org.springframework, jakarta.persistence'
```

---

## Module Dependency Rules

| Module | May depend on |
|---|---|
| `:common` | Nothing project-internal |
| business module | `:common` only |
| `:app` | Every module |

- A module that needs to react to something another module did listens to that module's event from `common.domain.event` (see **spring-service-layer**).
- A module that needs data owned by another module keeps its own read copy, fed by events (like `chat` keeping `ChatParticipant` rows from `UserEvent.Verified`).
- A synchronous cross-module query is the exception. When it is unavoidable, declare a small interface in `:common` (`interface UserLookup`) and implement it in the owning module. Never add a Gradle dependency between business modules.

---

## Runtime Baseline

- JDK 25 toolchain, Kotlin 2.3+ (needed for the JVM 25 target), Spring Boot 4.x, Gradle 9.
- Spring MVC (blocking) with virtual threads: `spring.threads.virtual.enabled: true` in `application.yml`. No coroutines and no WebFlux in request handling.
- With virtual threads, connection pools become the throttle. Size `spring.datasource.hikari.maximum-pool-size` deliberately and never hold a pooled resource while waiting on a remote call.
- Postgres, one schema per module (`user_service`, `chat_service`, ...), migrated by Flyway (see **spring-persistence-jpa**).
- `spring.jpa.open-in-view: false`.

---

## Convention Plugin Architecture

Convention plugins in `build-logic` remove all repeated config from module build files. A module build file only lists the module's own extra dependencies.

```
<app>.kotlin.jvm             ← Kotlin JVM, toolchain, compiler flags, JUnit 5 + AssertK
    └── <app>.spring.module  ← + kotlin-spring, Spring Boot BOM, Jackson Kotlin, depends on :common
        ├── <app>.spring.jpa ← + kotlin-jpa, allOpen for entities, Data JPA, Flyway, Postgres driver
        └── <app>.spring.application ← + Spring Boot plugin (bootJar), used by :app only
```

| Module | Plugins |
|---|---|
| `:common` | `<app>.spring.module` |
| business module with a database | `<app>.spring.module` + `<app>.spring.jpa` |
| business module without a database | `<app>.spring.module` |
| `:app` | `<app>.spring.application` + `<app>.spring.jpa` |

The Spring Boot BOM is applied as a Gradle `platform()`, not through the `io.spring.dependency-management` plugin. The plugin rewrites versions in every configuration, including ones it has no business in (it downgrades the Kotlin compiler that detekt embeds, for example). A `platform()` only affects the configurations it is added to.

---

## Build-Logic Infrastructure

### build-logic/settings.gradle.kts

```kotlin
rootProject.name = "build-logic"

dependencyResolutionManagement {
    repositories {
        mavenCentral()
        gradlePluginPortal()
    }
    versionCatalogs {
        create("libs") {
            from(files("../gradle/libs.versions.toml"))
        }
    }
}

include(":convention")
```

### build-logic/convention/build.gradle.kts

```kotlin
plugins {
    `kotlin-dsl`
}

dependencies {
    compileOnly(libs.kotlin.gradlePlugin)
    compileOnly(libs.kotlin.allopen.gradlePlugin)
    compileOnly(libs.kotlin.noarg.gradlePlugin)
    compileOnly(libs.spring.boot.gradlePlugin)
}

kotlin {
    jvmToolchain(25)
}

gradlePlugin {
    plugins {
        register("kotlinJvm") {
            id = "<app>.kotlin.jvm"
            implementationClass = "KotlinJvmConventionPlugin"
        }
        register("springModule") {
            id = "<app>.spring.module"
            implementationClass = "SpringModuleConventionPlugin"
        }
        register("springJpa") {
            id = "<app>.spring.jpa"
            implementationClass = "SpringJpaConventionPlugin"
        }
        register("springApplication") {
            id = "<app>.spring.application"
            implementationClass = "SpringApplicationConventionPlugin"
        }
    }
}
```

### Helper: ProjectExt.kt

```kotlin
import org.gradle.api.Project
import org.gradle.api.artifacts.VersionCatalog
import org.gradle.api.artifacts.VersionCatalogsExtension
import org.gradle.kotlin.dsl.getByType

val Project.libs: VersionCatalog
    get() = extensions.getByType<VersionCatalogsExtension>().named("libs")

fun VersionCatalog.library(alias: String) = findLibrary(alias).get()

fun VersionCatalog.version(alias: String) = findVersion(alias).get().requiredVersion
```

### Plugin: KotlinJvmConventionPlugin

```kotlin
import org.gradle.api.Plugin
import org.gradle.api.Project
import org.gradle.api.tasks.testing.Test
import org.gradle.kotlin.dsl.configure
import org.gradle.kotlin.dsl.dependencies
import org.gradle.kotlin.dsl.withType
import org.jetbrains.kotlin.gradle.dsl.KotlinJvmProjectExtension

class KotlinJvmConventionPlugin : Plugin<Project> {

    override fun apply(target: Project) {
        with(target) {
            pluginManager.apply("org.jetbrains.kotlin.jvm")

            extensions.configure<KotlinJvmProjectExtension> {
                jvmToolchain(libs.version("java").toInt())
                compilerOptions {
                    freeCompilerArgs.addAll(
                        "-Xjsr305=strict",
                        "-Xannotation-default-target=param-property",
                    )
                }
            }

            tasks.withType<Test>().configureEach {
                useJUnitPlatform()
            }

            dependencies {
                "testImplementation"(libs.library("junit-jupiter"))
                "testImplementation"(libs.library("assertk"))
                "testRuntimeOnly"(libs.library("junit-platform-launcher"))
            }
        }
    }
}
```

### Plugin: SpringModuleConventionPlugin

```kotlin
import org.gradle.api.Plugin
import org.gradle.api.Project
import org.gradle.kotlin.dsl.dependencies
import org.gradle.kotlin.dsl.project

class SpringModuleConventionPlugin : Plugin<Project> {

    override fun apply(target: Project) {
        with(target) {
            pluginManager.apply("<app>.kotlin.jvm")
            pluginManager.apply("org.jetbrains.kotlin.plugin.spring")
            pluginManager.apply("java-library")

            pluginManager.withPlugin("java-test-fixtures") {
                dependencies {
                    "testFixturesImplementation"(platform(libs.library("spring-boot-bom")))
                }
            }

            dependencies {
                "implementation"(platform(libs.library("spring-boot-bom")))

                "implementation"(libs.library("kotlin-reflect"))
                "implementation"(libs.library("jackson-module-kotlin"))
                "implementation"(libs.library("spring-boot-starter"))

                if (path != ":common") {
                    "implementation"(project(":common"))
                    "testImplementation"(testFixtures(project(":common")))
                }
            }
        }
    }
}
```

`:common` applies the `java-test-fixtures` plugin in its own build file. Its `src/testFixtures` holds the fakes every module's tests share (`MutableClock`, `RecordingEventPublisher`).

### Plugin: SpringJpaConventionPlugin

```kotlin
import org.gradle.api.Plugin
import org.gradle.api.Project
import org.gradle.kotlin.dsl.configure
import org.gradle.kotlin.dsl.dependencies
import org.jetbrains.kotlin.allopen.gradle.AllOpenExtension

class SpringJpaConventionPlugin : Plugin<Project> {

    override fun apply(target: Project) {
        with(target) {
            pluginManager.apply("org.jetbrains.kotlin.plugin.jpa")

            // Hibernate creates lazy proxies by subclassing, so entities must be open.
            extensions.configure<AllOpenExtension> {
                annotation("jakarta.persistence.Entity")
                annotation("jakarta.persistence.MappedSuperclass")
                annotation("jakarta.persistence.Embeddable")
            }

            dependencies {
                "implementation"(libs.library("spring-boot-starter-data-jpa"))
                "implementation"(libs.library("spring-boot-starter-flyway"))
                "implementation"(libs.library("flyway-database-postgresql"))
                "runtimeOnly"(libs.library("postgresql"))
            }
        }
    }
}
```

### Plugin: SpringApplicationConventionPlugin

```kotlin
import org.gradle.api.Plugin
import org.gradle.api.Project

class SpringApplicationConventionPlugin : Plugin<Project> {

    override fun apply(target: Project) {
        with(target) {
            pluginManager.apply("<app>.spring.module")
            pluginManager.apply("org.springframework.boot")
        }
    }
}
```

Resources (`db/migration/<module>`, templates) of business modules end up in the boot jar because the modules are `implementation` dependencies of `:app`. Never copy another module's `src/main/resources` into `bootJar` by hand.

---

## Version Catalog Conventions

Every version, library, and plugin lives in `gradle/libs.versions.toml`. No version string appears in any `build.gradle.kts`, including `build-logic`. Libraries managed by the Spring Boot BOM have no version in the catalog. Look up the latest stable version before adding or bumping anything.

```toml
[versions]
java = "25"
kotlin = "2.3.0"
spring-boot = "4.0.0"
assertk = "0.28.1"

[libraries]
# Gradle plugin artifacts for build-logic
kotlin-gradlePlugin = { module = "org.jetbrains.kotlin:kotlin-gradle-plugin", version.ref = "kotlin" }
kotlin-allopen-gradlePlugin = { module = "org.jetbrains.kotlin:kotlin-allopen", version.ref = "kotlin" }
kotlin-noarg-gradlePlugin = { module = "org.jetbrains.kotlin:kotlin-noarg", version.ref = "kotlin" }
spring-boot-gradlePlugin = { module = "org.springframework.boot:spring-boot-gradle-plugin", version.ref = "spring-boot" }

# BOM
spring-boot-bom = { module = "org.springframework.boot:spring-boot-dependencies", version.ref = "spring-boot" }

# Spring Boot starters (versions from the BOM)
spring-boot-starter = { module = "org.springframework.boot:spring-boot-starter" }
spring-boot-starter-webmvc = { module = "org.springframework.boot:spring-boot-starter-webmvc" }
spring-boot-starter-validation = { module = "org.springframework.boot:spring-boot-starter-validation" }
spring-boot-starter-data-jpa = { module = "org.springframework.boot:spring-boot-starter-data-jpa" }
spring-boot-starter-flyway = { module = "org.springframework.boot:spring-boot-starter-flyway" }
spring-boot-starter-restclient = { module = "org.springframework.boot:spring-boot-starter-restclient" }
spring-boot-starter-security = { module = "org.springframework.boot:spring-boot-starter-security" }
spring-boot-starter-security-oauth2-resource-server = { module = "org.springframework.boot:spring-boot-starter-security-oauth2-resource-server" }

# Kotlin / Jackson 3
kotlin-reflect = { module = "org.jetbrains.kotlin:kotlin-reflect" }
jackson-module-kotlin = { module = "tools.jackson.module:jackson-module-kotlin" }

# Database
postgresql = { module = "org.postgresql:postgresql" }
flyway-database-postgresql = { module = "org.flywaydb:flyway-database-postgresql" }

# Test
junit-jupiter = { module = "org.junit.jupiter:junit-jupiter" }
junit-platform-launcher = { module = "org.junit.platform:junit-platform-launcher" }
assertk = { module = "com.willowtreeapps.assertk:assertk-jvm", version.ref = "assertk" }
spring-boot-starter-test = { module = "org.springframework.boot:spring-boot-starter-test" }
spring-boot-starter-data-jpa-test = { module = "org.springframework.boot:spring-boot-starter-data-jpa-test" }
spring-boot-testcontainers = { module = "org.springframework.boot:spring-boot-testcontainers" }
testcontainers-postgresql = { module = "org.testcontainers:testcontainers-postgresql" }
testcontainers-junit-jupiter = { module = "org.testcontainers:testcontainers-junit-jupiter" }

[plugins]
kotlin-jvm = { id = "org.jetbrains.kotlin.jvm", version.ref = "kotlin" }
kotlin-spring = { id = "org.jetbrains.kotlin.plugin.spring", version.ref = "kotlin" }
kotlin-jpa = { id = "org.jetbrains.kotlin.plugin.jpa", version.ref = "kotlin" }
spring-boot = { id = "org.springframework.boot", version.ref = "spring-boot" }

convention-kotlin-jvm = { id = "<app>.kotlin.jvm", version = "unspecified" }
convention-spring-module = { id = "<app>.spring.module", version = "unspecified" }
convention-spring-jpa = { id = "<app>.spring.jpa", version = "unspecified" }
convention-spring-application = { id = "<app>.spring.application", version = "unspecified" }
```

Spring Boot 4 notes that matter when adding dependencies:

- Starters are modular. `spring-boot-starter-web` is now `spring-boot-starter-webmvc`. Flyway needs `spring-boot-starter-flyway`; the bare `flyway-core` no longer gets auto-configured.
- Each technology has a matching test starter (`spring-boot-starter-webmvc-test`, `spring-boot-starter-data-jpa-test`, `spring-boot-starter-security-test`).
- Jackson 3 is the default: group `tools.jackson.*`, packages `tools.jackson.*`. Only `jackson-annotations` keeps `com.fasterxml.jackson.annotation`. Never mix in Jackson 2 artifacts.
- Testcontainers 2 prefixes every module with `testcontainers-` and moves containers to `org.testcontainers.<module>` packages.

---

## Root-Level Build Files

### settings.gradle.kts

```kotlin
pluginManagement {
    includeBuild("build-logic")
    repositories {
        gradlePluginPortal()
        mavenCentral()
    }
}

dependencyResolutionManagement {
    repositories {
        mavenCentral()
    }
}

enableFeaturePreview("TYPESAFE_PROJECT_ACCESSORS")

rootProject.name = "<app>"

include(":app")
include(":common")
include(":user")
include(":chat")
include(":notification")
```

Repositories are declared once, here. Module build files never declare `repositories {}`, `group`, or `version`.

### build.gradle.kts (root)

```kotlin
plugins {
    alias(libs.plugins.kotlin.jvm) apply false
    alias(libs.plugins.kotlin.spring) apply false
    alias(libs.plugins.kotlin.jpa) apply false
    alias(libs.plugins.spring.boot) apply false
}

allprojects {
    group = "com.<company>"
    version = "0.0.1-SNAPSHOT"
}
```

### gradle.properties

```properties
org.gradle.jvmargs=-Xmx4096M -Dfile.encoding=UTF-8
org.gradle.parallel=true
org.gradle.caching=true
org.gradle.configuration-cache=true
kotlin.code.style=official
```

---

## Example Module Build Files

### common/build.gradle.kts

```kotlin
plugins {
    alias(libs.plugins.convention.spring.module)
    `java-test-fixtures`
}

dependencies {
    implementation(libs.spring.boot.starter.webmvc)
    implementation(libs.spring.boot.starter.security)
}
```

### chat/build.gradle.kts

```kotlin
plugins {
    alias(libs.plugins.convention.spring.module)
    alias(libs.plugins.convention.spring.jpa)
}

dependencies {
    implementation(libs.spring.boot.starter.webmvc)
    implementation(libs.spring.boot.starter.validation)
    implementation(libs.spring.boot.starter.restclient)

    testImplementation(libs.spring.boot.starter.data.jpa.test)
    testImplementation(libs.spring.boot.testcontainers)
    testImplementation(libs.testcontainers.postgresql)
    testImplementation(libs.testcontainers.junit.jupiter)
}
```

### app/build.gradle.kts

```kotlin
plugins {
    alias(libs.plugins.convention.spring.application)
    alias(libs.plugins.convention.spring.jpa)
}

dependencies {
    implementation(projects.user)
    implementation(projects.chat)
    implementation(projects.notification)

    implementation(libs.spring.boot.starter.webmvc)
    implementation(libs.spring.boot.starter.security)
    implementation(libs.spring.boot.starter.security.oauth2.resource.server)

    testImplementation(libs.spring.boot.starter.test)
    testImplementation(libs.spring.boot.testcontainers)
    testImplementation(libs.testcontainers.postgresql)
    testImplementation(libs.testcontainers.junit.jupiter)
}
```

---

## Checklist: Adding a New Business Module

- [ ] Create `:<module>` and add it to `settings.gradle.kts`
- [ ] Apply `convention.spring.module`, plus `convention.spring.jpa` if it stores data
- [ ] Root package `com.<company>.<app>.<module>` with `api`, `service`, `domain`, `infra` packages
- [ ] Own Postgres schema `<module>_service` and migrations in `src/main/resources/db/migration/<module>` (see **spring-persistence-jpa**)
- [ ] No Gradle dependency on another business module; cross-module events go to `common.domain.event`
- [ ] Add `implementation(projects.<module>)` to `:app`
- [ ] Add the module's public routes to the security config in `:app` if it has any (see **spring-security**)
- [ ] Add a module-level exception handler for the module's domain exceptions (see **spring-api-layer**)
