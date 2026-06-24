---
name: android-version-catalog
description: |
  Gradle version catalog management and convention plugin creation for Android/KMP - adding libraries, plugins, bundles, and version refs in libs.versions.toml, plus creating convention plugins for libraries with non-trivial Gradle config (KSP, compiler plugins, multi-artifact setup). Use this skill whenever adding a dependency, creating a bundle, registering a plugin in the version catalog, creating a convention plugin, looking up the latest version of a library, or updating a dependency version. Trigger on phrases like "add a library", "add a dependency", "version catalog", "libs.versions.toml", "bundle", "add a plugin", "convention plugin", "latest version of", "update dependency", "create a convention plugin", "add Ktor", "add Room", or "add KSP".
---

# Android / KMP Gradle Version Catalog & Convention Plugins

## Principles

- **All versions are named references** — every version lives in `[versions]` with a named key. Never inline a version string directly in a library or plugin definition.
- **Kebab-case everywhere** — aliases for versions, libraries, bundles, and plugins all use kebab-case.
- **Single source of truth** — `gradle/libs.versions.toml` is the only place versions and coordinates are declared. No hardcoded versions in build files.
- **Bundles for cohesive sets** — when multiple artifacts from the same library are always used together, group them in `[bundles]`.
- **All plugins live in `[plugins]`** — both external Gradle plugins (with `version.ref`) and convention plugins from `:build-logic` (with `version = "unspecified"`).
- **Suggest convention plugins for non-trivial config** — when a library involves KSP, compiler plugins, BOM, platform-specific setup, or config that would be copy-pasted across modules, suggest creating a convention plugin.
- **Keep related versions in sync** — when adding a library that depends on KSP, Kotlin, or other toolchain dependencies, also check and update those versions to the latest compatible release. For example, adding Room requires checking that the KSP version matches the current Kotlin version.

---

## Version Catalog Structure

```toml
[versions]
ktor = "3.1.1"
koin = "4.0.4"
room = "2.7.2"
ksp = "2.1.20-1.0.32"
kotlin = "2.1.20"
compose-multiplatform = "1.7.3"

[libraries]
ktor-client-core = { module = "io.ktor:ktor-client-core", version.ref = "ktor" }
ktor-client-content-negotiation = { module = "io.ktor:ktor-client-content-negotiation", version.ref = "ktor" }
ktor-client-auth = { module = "io.ktor:ktor-client-auth", version.ref = "ktor" }
ktor-client-logging = { module = "io.ktor:ktor-client-logging", version.ref = "ktor" }
ktor-serialization-kotlinx-json = { module = "io.ktor:ktor-serialization-kotlinx-json", version.ref = "ktor" }
koin-core = { module = "io.insert-koin:koin-core", version.ref = "koin" }
room-runtime = { module = "androidx.room:room-runtime", version.ref = "room" }
room-compiler = { module = "androidx.room:room-compiler", version.ref = "room" }

[bundles]
ktor = [
    "ktor-client-core",
    "ktor-client-content-negotiation",
    "ktor-client-auth",
    "ktor-client-logging",
    "ktor-serialization-kotlinx-json",
]

[plugins]
# External plugins — real versions via version.ref
ksp = { id = "com.google.devtools.ksp", version.ref = "ksp" }
kotlin-serialization = { id = "org.jetbrains.kotlin.plugin.serialization", version.ref = "kotlin" }
compose-compiler = { id = "org.jetbrains.kotlin.plugin.compose", version.ref = "kotlin" }
room = { id = "androidx.room", version.ref = "room" }

# Convention plugins — version is always "unspecified"
convention-android-application = { id = "com.plcoding.convention.android.application", version = "unspecified" }
convention-cmp-feature = { id = "com.plcoding.convention.cmp.feature", version = "unspecified" }
convention-kmp-library = { id = "com.plcoding.convention.kmp.library", version = "unspecified" }
convention-room = { id = "com.plcoding.convention.room", version = "unspecified" }
```

---

## Naming Conventions

### Library Aliases

Derive from the Maven `artifactId`, keeping kebab-case as-is:

| Maven coordinate | Alias |
|---|---|
| `io.ktor:ktor-client-core` | `ktor-client-core` |
| `io.insert-koin:koin-core` | `koin-core` |
| `androidx.room:room-runtime` | `room-runtime` |
| `org.jetbrains.kotlinx:kotlinx-coroutines-core` | `kotlinx-coroutines-core` |
| `io.coil-kt.coil3:coil-compose` | `coil-compose` |

If two libraries would collide on `artifactId` alone, prefix with enough of the group to disambiguate.

### Version Keys

Use the shortest unambiguous name for the library family:

| Library family | Version key |
|---|---|
| Ktor | `ktor` |
| Koin | `koin` |
| AndroidX Room | `room` |
| Kotlin | `kotlin` |
| KSP | `ksp` |
| Compose BOM | `compose-bom` |
| Compose Multiplatform | `compose-multiplatform` |

### Full Naming Summary

| Thing | Format | Example |
|---|---|---|
| Version key | Shortest unambiguous kebab-case | `ktor`, `room`, `compose-bom` |
| Library alias | Kebab-case from artifactId | `ktor-client-core`, `room-runtime` |
| Bundle alias | Kebab-case library family name | `ktor`, `koin` |
| External plugin alias | Kebab-case from plugin name | `ksp`, `kotlin-serialization` |
| Convention plugin alias | `convention-<short-name>` | `convention-room`, `convention-cmp-feature` |

---

## Bundles

Create a bundle when 2+ artifacts from the same library are always added together:

```toml
[bundles]
ktor = ["ktor-client-core", "ktor-client-content-negotiation", "ktor-client-auth"]
koin = ["koin-core", "koin-android", "koin-androidx-compose"]
```

Usage in `build.gradle.kts`:

```kotlin
implementation(libs.bundles.ktor)
```

Do not create a bundle for a single artifact.

---

## External Plugins

External Gradle plugins use real versions with `version.ref`:

```toml
[plugins]
ksp = { id = "com.google.devtools.ksp", version.ref = "ksp" }
```

```kotlin
plugins {
    alias(libs.plugins.ksp)
}
```

---

## Convention Plugins

When a library involves non-trivial Gradle config — KSP processing, compiler plugins, BOM management, platform-specific setup, or config that would be duplicated across modules — suggest creating a convention plugin. This keeps feature module build files clean and ensures consistent configuration.

### Directory Structure

```
build-logic/
└── convention/
    ├── build.gradle.kts                          ← gradlePlugin { } registration
    └── src/main/kotlin/
        ├── RoomConventionPlugin.kt               ← plugin classes at package root
        └── com/plcoding/<project>/convention/
            ├── ProjectExt.kt                     ← val Project.libs accessor
            ├── KotlinAndroid.kt                  ← shared Android config
            ├── KotlinMultiplatform.kt            ← shared KMP config
            └── AndroidCompose.kt                 ← shared Compose config
```

### ProjectExt.kt (required utility)

Every convention plugin project needs this accessor to read the version catalog:

```kotlin
import org.gradle.api.Project
import org.gradle.api.artifacts.VersionCatalog
import org.gradle.api.artifacts.VersionCatalogsExtension
import org.gradle.kotlin.dsl.getByType

val Project.libs: VersionCatalog
    get() = extensions.getByType<VersionCatalogsExtension>().named("libs")
```

### Plugin Class Pattern

Convention plugins implement `Plugin<Project>`, apply other plugins, and configure the project. They pull dependencies from the version catalog — never hardcode coordinates.

**Example — Room (KMP):**

```kotlin
import com.plcoding.chirp.convention.libs
import org.gradle.api.Plugin
import org.gradle.api.Project
import org.gradle.kotlin.dsl.dependencies
import androidx.room.gradle.RoomExtension
import com.google.devtools.ksp.gradle.KspExtension

class RoomConventionPlugin : Plugin<Project> {
    override fun apply(target: Project) {
        with(target) {
            pluginManager.apply("com.google.devtools.ksp")
            pluginManager.apply("androidx.room")

            extensions.configure<RoomExtension> {
                schemaDirectory("$projectDir/schemas")
            }

            dependencies {
                "commonMainImplementation"(libs.findLibrary("room-runtime").get())
                "commonMainImplementation"(libs.findLibrary("sqlite-bundled").get())
                "kspAndroid"(libs.findLibrary("room-compiler").get())
                "kspIosSimulatorArm64"(libs.findLibrary("room-compiler").get())
                "kspIosArm64"(libs.findLibrary("room-compiler").get())
                "kspIosX64"(libs.findLibrary("room-compiler").get())
                "kspDesktop"(libs.findLibrary("room-compiler").get())
            }
        }
    }
}
```

**Example — Android-only library (Compose):**

```kotlin
class ComposeConventionPlugin : Plugin<Project> {
    override fun apply(target: Project) {
        with(target) {
            pluginManager.apply("org.jetbrains.kotlin.plugin.compose")

            extensions.configure<com.android.build.api.dsl.CommonExtension<*, *, *, *, *, *>> {
                buildFeatures {
                    compose = true
                }
            }

            dependencies {
                val bom = libs.findLibrary("compose-bom").get()
                "implementation"(platform(bom))
                "androidTestImplementation"(platform(bom))
            }
        }
    }
}
```

### Plugin Layering

Convention plugins can compose by applying other convention plugins. Each layer adds its specific config on top:

```
cmp-feature  →  applies cmp-library  →  applies kmp-library
   (Koin,          (Compose,              (KMP targets,
    Navigation,     Compose compiler)       Serialization)
    shared deps)
```

This avoids duplication — a feature module only applies one plugin and inherits all layers.

### Registration

Register each plugin in `build-logic/convention/build.gradle.kts`:

```kotlin
gradlePlugin {
    plugins {
        register("room") {
            id = "com.plcoding.convention.room"
            implementationClass = "RoomConventionPlugin"
        }
        register("cmpFeature") {
            id = "com.plcoding.convention.cmp.feature"
            implementationClass = "CmpFeatureConventionPlugin"
        }
    }
}
```

Detect the namespace prefix (e.g., `com.plcoding.convention`) from the existing convention plugins in the project.

### Version Catalog Entry

Convention plugins always use `version = "unspecified"` — they are built locally, not fetched from a repository:

```toml
[plugins]
convention-room = { id = "com.plcoding.convention.room", version = "unspecified" }
```

Applied in a feature module:

```kotlin
plugins {
    alias(libs.plugins.convention.room)
}
```

### When to Suggest a Convention Plugin

Suggest creating one (don't force) when the library involves:
- KSP annotation processing (Room, Moshi, Hilt)
- Compiler plugins (Compose, Serialization)
- Complex multi-artifact setup with BOM
- Platform-specific configurations (KMP targets needing different KSP configs)
- Config that would be copy-pasted across 2+ modules

If the library is a simple `implementation` dependency with no special Gradle config, a convention plugin is unnecessary — just add it to the version catalog.

---

## Workflow: Adding a New Library

1. **Look up the latest stable version** on [mvnrepository.com](https://mvnrepository.com). Prefer stable releases. Only use RC/beta if the user explicitly asks or no stable version exists yet.
2. **Check related toolchain versions** — if the library depends on KSP, verify the KSP version is compatible with the project's Kotlin version. If not, update both. Always look up the latest stable KSP and Kotlin versions when they are involved. The KSP version format is `<kotlin-version>-<ksp-version>` (e.g., `2.1.20-1.0.32`), so when Kotlin updates, KSP must update too.
3. **Add or reuse a version entry** in `[versions]`. Use the shortest unambiguous key for the library family.
4. **Add library entries** in `[libraries]` with `module` and `version.ref`. Alias = kebab-case from the artifactId.
5. **Create a bundle** if multiple artifacts from this library will always be used together.
6. **Add a Gradle plugin entry** in `[plugins]` with `version.ref` if the library ships a Gradle plugin (KSP, Room, Serialization, etc.).
7. **If the library involves non-trivial Gradle config**, suggest creating a convention plugin:
   a. Create the plugin class in `build-logic/convention/src/main/kotlin/`
   b. Register in `build-logic/convention/build.gradle.kts` via `gradlePlugin { plugins { register(...) } }`
   c. Add a `convention-<name>` entry in `[plugins]` with `version = "unspecified"`
8. **Reference in `build.gradle.kts`**:
   - Libraries: `implementation(libs.<alias>)` or `implementation(libs.bundles.<bundle>)`
   - Plugins: `alias(libs.plugins.<alias>)`
9. **Sync Gradle** to verify resolution.

**Important:** Always look up every version on mvnrepository.com — never rely on version numbers from memory or from this skill's examples, as they become outdated quickly.

---

## Checklist

### Adding a Dependency

- [ ] All versions looked up on mvnrepository.com — not from memory or skill examples
- [ ] Related toolchain versions (KSP, Kotlin) checked and updated if needed
- [ ] Version entry exists in `[versions]` — no inline versions anywhere
- [ ] Library alias uses kebab-case derived from the artifactId
- [ ] Library definition uses `version.ref`, not a hardcoded version string
- [ ] Bundle created if 2+ artifacts from the same library are always used together
- [ ] External Gradle plugin added to `[plugins]` with `version.ref` if applicable
- [ ] `build.gradle.kts` uses typed accessors (`libs.<alias>`, `libs.bundles.<alias>`, `libs.plugins.<alias>`)

### Creating a Convention Plugin (when applicable)

- [ ] Plugin class implements `Plugin<Project>` and applies relevant plugins
- [ ] Dependencies pulled from version catalog via `libs.findLibrary(...)` — no hardcoded coordinates
- [ ] Plugin registered in `build-logic/convention/build.gradle.kts`
- [ ] Convention plugin entry in `[plugins]` with `version = "unspecified"`
- [ ] Namespace matches existing convention plugins in the project
