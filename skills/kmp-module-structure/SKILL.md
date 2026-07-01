---
name: kmp-module-structure
description: Module layout, dependency rules, Gradle 9 convention plugins, and Compose Multiplatform setup for Kotlin Multiplatform (KMP) projects. Use this skill whenever setting up a new KMP project, deciding where a new module should live, asking "how should I structure this", creating a new feature module, adding a core submodule, configuring Gradle convention plugins, working with version catalogs, setting up build-logic, configuring Compose Multiplatform, fixing Android preview issues in KMP, or making any decision about project-level architecture. Trigger on phrases like "set up the project", "add a module", "create a feature", "how should I structure", "project structure", "convention plugin", "build-logic", "where does X live", "Gradle 9", "KMP module", "Compose Multiplatform setup", "Android preview in KMP", or "composeApp".
---

# KMP Module Structure (Gradle 9)

## Core Philosophy

- **Feature-layered modularization**: split by feature first, then by layer within each feature.
- **Clean Architecture layers**: `presentation` → `domain` ← `data`. Domain is innermost and depends on nothing.
- **Code lives in a feature module unless it is needed by more than one feature** — then it moves to the appropriate `core` submodule.
- Features **never depend on each other**. Cross-feature shared data belongs in `core:domain` (domain models) or `core:presentation` (shared composables/UI logic), not in the owning feature.
- **Target platforms**: Android + iOS are always present. Desktop (JVM) is optional.

---

## Gradle 9 Breaking Changes

Gradle 9 fundamentally changes how Android works in KMP projects:

1. **New AGP plugin**: KMP library modules use `com.android.kotlin.multiplatform.library` instead of the old `com.android.library`. The old plugin no longer works for KMP modules in Gradle 9.

2. **Mandatory `:composeApp` + `:androidApp` split**: Android-specific Gradle plugins (`com.android.application`, `com.google.gms.google-services`, etc.) **cannot** be applied in a Kotlin Multiplatform module. Therefore:
   - `:composeApp` is a **KMP library module** (not an application module) that holds all shared Compose UI, navigation, and DI wiring.
   - `:androidApp` is a **thin Android application module** that depends on `:composeApp`. It contains only the `Activity`, Android manifest, Android-only plugins (Google Services, Firebase), and the splash screen setup.

   This split is **not optional** — it is a hard requirement from Gradle 9. When you encounter a project with this split, or need to create one, this is why.

3. **Android config in KMP modules** uses `KotlinMultiplatformAndroidLibraryExtension` instead of `LibraryExtension`:
   ```kotlin
   extensions.configure<KotlinMultiplatformExtension> {
       extensions.configure<KotlinMultiplatformAndroidLibraryExtension> {
           compileSdk = 36
           minSdk = 26
           namespace = "com.<company>.module.name"
       }
   }
   ```

---

## Module Layout

```
:composeApp                     ← Shared KMP Compose app (library module, NOT application)
:androidApp                     ← Thin Android shell (Activity, manifest, Google Services)
:build-logic                    ← Gradle convention plugins
:core:domain                    ← Shared domain models, repository interfaces, error types, Result
:core:data                      ← Shared data logic, Ktor HttpClient factory, DataStore
:core:presentation              ← Shared UI utilities (ObserveAsEvents, UiText, permissions, etc.)
:core:designsystem              ← Reusable Compose components, colors, theme, typography, Coil
:feature:<name>:domain          ← Feature-specific domain models, repo interfaces, error types
:feature:<name>:data            ← Repo implementations, DTOs, mappers
:feature:<name>:presentation    ← ViewModel, screen composables, state, actions, events
:feature:<name>:database        ← Feature-scoped Room DB (if only this feature needs it)
```

**Database modules**: Use `:core:database` for a shared database accessed by multiple features. Use `:feature:<name>:database` when only one feature owns the database. The database module contains the `@Database` class, entity definitions, DAOs, and migrations.

For standalone, self-contained concerns that involve meaningful complexity (multiple classes, configuration, or a non-trivial API surface), create a dedicated module under `:core` (e.g., `:core:location`, `:core:analytics`). Do not create a separate module for a single class or a trivial utility — that belongs in an existing `core` module instead.

---

## Dependency Rules

| Layer | May depend on |
|---|---|
| `presentation` | `domain` (own feature), `core:domain`, `core:presentation`, `core:designsystem` |
| `data` | `domain` (own feature), `core:domain`, `core:data` |
| `domain` | `core:domain` only — never `data` or `presentation` |
| `database` | `core:data` (for shared DB utilities), `core:domain` |
| `:composeApp` | everything (wires all modules, navigation, DI) |
| `:androidApp` | `:composeApp` only (thin shell) |

**Every** layer and module may access `core:domain`.

---

## Convention Plugin Architecture (3-Tier)

Convention plugins eliminate boilerplate from module build files. They are layered:

```
kmp.library          ← Base: KMP + Android target + iOS targets + Desktop target + serialization
    └── cmp.library  ← Adds: Compose Multiplatform + Compose deps + Android preview tooling
        └── cmp.feature  ← Adds: Koin + Navigation + Lifecycle + auto-depends core:presentation & core:designsystem
```

Additional standalone plugins:
- `android.application` — Android app module config (applicationId, SDK versions, build types)
- `android.application.compose` — Android app + Compose (BOM, debugImplementation tooling)
- `cmp.application` — The `:composeApp` module plugin (KMP + Compose + all platform targets + serialization)
- `room` — Room + KSP for all platforms
- `buildkonfig` — BuildKonfig with auto-derived package name from module path

### Which plugin to apply per module type

| Module | Convention plugin(s) |
|---|---|
| `core:domain` | `kmp.library` |
| `core:data` | `kmp.library` + `buildkonfig` |
| `core:presentation` | `cmp.library` |
| `core:designsystem` | `cmp.library` |
| `feature:<name>:domain` | `kmp.library` |
| `feature:<name>:data` | `kmp.library` + `buildkonfig` (if API keys needed) |
| `feature:<name>:presentation` | `cmp.feature` |
| `feature:<name>:database` | `kmp.library` + `room` |
| `:composeApp` | `cmp.application` |
| `:androidApp` | `android.application` or `android.application.compose` |

---

## Compose Multiplatform Previews on Android

**Problem**: KMP modules use `com.android.kotlin.multiplatform.library`, which has no Android build type awareness (no `debug`/`release` variants). This means `debugImplementation` does not work in KMP source sets. Without the Compose UI tooling dependency, `@Preview` annotations will not render in Android Studio.

**Solution**: In convention plugins that enable Compose (`cmp.library`, `cmp.application`), add the tooling dependency to `androidMainImplementation` instead of `debugImplementation`:

```kotlin
dependencies {
    "androidMainImplementation"(libs.findLibrary("androidx-compose-ui-tooling").get())
}
```

The `:androidApp` module (which is a pure Android module, not KMP) **can** use `debugImplementation` normally via the `android.application.compose` convention plugin.

This is why both `CmpLibraryConventionPlugin` and `CmpApplicationConventionPlugin` include `androidMainImplementation` for the tooling library — it is the only way to enable Compose previews in KMP modules.

---

## Build-Logic Infrastructure

The `:build-logic` module is an included build that contains all convention plugins.

### build-logic/settings.gradle.kts
```kotlin
rootProject.name = "build-logic"

dependencyResolutionManagement {
    repositories {
        google()
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

### build-logic/gradle.properties
```properties
org.gradle.parallel=true
org.gradle.caching=true
org.gradle.configureondemand=true
```

### build-logic/convention/build.gradle.kts

In Gradle 9, convention plugins need Gradle plugin artifacts (not the plugins themselves) on the compile classpath. These are declared as `compileOnly` dependencies using special `-gradlePlugin` library aliases in the version catalog.

```kotlin
plugins {
    alias(libs.plugins.kotlin.gradlePlugin)
    alias(libs.plugins.android.gradlePlugin)
    alias(libs.plugins.compose.gradlePlugin)
    alias(libs.plugins.ksp.gradlePlugin)
    alias(libs.plugins.room)
    alias(libs.plugins.buildkonfig)
}

dependencies {
    compileOnly(libs.android.gradlePlugin)
    compileOnly(libs.kotlin.gradlePlugin)
    compileOnly(libs.compose.gradlePlugin)
    compileOnly(libs.ksp.gradlePlugin)
    compileOnly(libs.androidx.room.gradle.plugin)
    compileOnly(libs.buildkonfig.gradlePlugin)
}

gradlePlugin {
    plugins {
        register("androidApplication") {
            id = "com.<company>.convention.android.application"
            implementationClass = "AndroidApplicationConventionPlugin"
        }
        register("androidApplicationCompose") {
            id = "com.<company>.convention.android.application.compose"
            implementationClass = "AndroidApplicationComposeConventionPlugin"
        }
        register("cmpApplication") {
            id = "com.<company>.convention.cmp.application"
            implementationClass = "CmpApplicationConventionPlugin"
        }
        register("kmpLibrary") {
            id = "com.<company>.convention.kmp.library"
            implementationClass = "KmpLibraryConventionPlugin"
        }
        register("cmpLibrary") {
            id = "com.<company>.convention.cmp.library"
            implementationClass = "CmpLibraryConventionPlugin"
        }
        register("cmpFeature") {
            id = "com.<company>.convention.cmp.feature"
            implementationClass = "CmpFeatureConventionPlugin"
        }
        register("buildkonfig") {
            id = "com.<company>.convention.buildkonfig"
            implementationClass = "BuildKonfigConventionPlugin"
        }
        register("room") {
            id = "com.<company>.convention.room"
            implementationClass = "RoomConventionPlugin"
        }
    }
}

java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}

kotlin {
    jvmToolchain(17)
}

validatePlugins {
    enableStricterValidation = true
    failOnWarning = true
}
```

The version catalog needs these library entries for the Gradle plugin artifacts:

```toml
[libraries]
android-gradlePlugin = { group = "com.android.tools.build", name = "gradle", version.ref = "agp" }
kotlin-gradlePlugin = { module = "org.jetbrains.kotlin:kotlin-gradle-plugin", version.ref = "kotlin" }
compose-gradlePlugin = { group = "org.jetbrains.kotlin", name = "compose-compiler-gradle-plugin", version.ref = "kotlin" }
ksp-gradlePlugin = { group = "com.google.devtools.ksp", name = "com.google.devtools.ksp.gradle.plugin", version.ref = "ksp" }
androidx-room-gradle-plugin = { module = "androidx.room:room-gradle-plugin", version.ref = "room" }
buildkonfig-gradlePlugin = { group = "com.codingfeline.buildkonfig", name = "buildkonfig-gradle-plugin", version.ref = "buildkonfig" }
```

---

## Convention Plugin Source Code

### Helper: ProjectExt.kt

```kotlin
package com.<company>.convention

import org.gradle.api.Project
import org.gradle.api.artifacts.VersionCatalog
import org.gradle.api.artifacts.VersionCatalogsExtension
import org.gradle.kotlin.dsl.getByType

val Project.libs: VersionCatalog
    get() = extensions.getByType<VersionCatalogsExtension>().named("libs")
```

### Helper: PathUtil.kt

```kotlin
package com.<company>.convention

import org.gradle.api.Project
import java.util.Locale

fun Project.pathToPackageName(): String {
    val relativePackageName = path
        .replace(':', '.')
        .lowercase()
    return "com.<company>$relativePackageName"
}

fun Project.pathToResourcePrefix(): String {
    return path
        .replace(':', '_')
        .lowercase()
        .drop(1) + "_"
}

fun Project.pathToFrameworkName(): String {
    val parts = this.path.split(":", "-", "_", " ")
    return parts.joinToString("") { part ->
        part.replaceFirstChar { it.titlecase(Locale.ROOT) }
    }
}
```

### Helper: KotlinAndroid.kt

```kotlin
package com.<company>.convention

import com.android.build.api.dsl.ApplicationExtension
import org.gradle.api.JavaVersion
import org.gradle.api.Project
import org.gradle.kotlin.dsl.dependencies
import org.gradle.kotlin.dsl.withType
import org.jetbrains.kotlin.gradle.dsl.JvmTarget
import org.jetbrains.kotlin.gradle.tasks.KotlinCompile

internal fun Project.configureKotlinAndroid(
    applicationExtension: ApplicationExtension
) {
    with(applicationExtension) {
        compileSdk = libs.findVersion("projectCompileSdkVersion").get().toString().toInt()
        defaultConfig.minSdk = libs.findVersion("projectMinSdkVersion").get().toString().toInt()

        compileOptions {
            sourceCompatibility = JavaVersion.VERSION_17
            targetCompatibility = JavaVersion.VERSION_17
            isCoreLibraryDesugaringEnabled = true
        }

        configureKotlin()

        dependencies {
            "coreLibraryDesugaring"(libs.findLibrary("android-desugarJdkLibs").get())
        }
    }
}

internal fun Project.configureKotlin() {
    tasks.withType<KotlinCompile>().configureEach {
        compilerOptions {
            jvmTarget.set(JvmTarget.JVM_17)
            freeCompilerArgs.add("-opt-in=kotlinx.coroutines.ExperimentalCoroutinesApi")
        }
    }
}
```

### Helper: AndroidCompose.kt

```kotlin
package com.<company>.convention

import com.android.build.api.dsl.ApplicationExtension
import org.gradle.api.Project
import org.gradle.kotlin.dsl.dependencies

internal fun Project.configureAndroidCompose(
    applicationExtension: ApplicationExtension
) {
    with(applicationExtension) {
        buildFeatures {
            compose = true
        }

        dependencies {
            val bom = libs.findLibrary("androidx-compose-bom").get()
            "implementation"(platform(bom))
            "testImplementation"(platform(bom))
            "debugImplementation"(libs.findLibrary("androidx-compose-ui-tooling-preview").get())
            "debugImplementation"(libs.findLibrary("androidx-compose-ui-tooling").get())
        }
    }
}
```

### Helper: KotlinMultiplatform.kt

```kotlin
package com.<company>.convention

import com.android.build.api.dsl.KotlinMultiplatformAndroidLibraryExtension
import org.gradle.api.Project
import org.gradle.kotlin.dsl.configure
import org.jetbrains.kotlin.gradle.dsl.KotlinMultiplatformExtension

internal fun Project.configureKotlinMultiplatform() {
    configureAndroidLibraryTarget()
    configureDesktopTarget()

    extensions.configure<KotlinMultiplatformExtension> {
        extensions.configure<KotlinMultiplatformAndroidLibraryExtension> {
            compileSdk = libs.findVersion("projectCompileSdkVersion").get().toString().toInt()
            minSdk = libs.findVersion("projectMinSdkVersion").get().toString().toInt()
            namespace = pathToPackageName()
            experimentalProperties["android.experimental.kmp.enableAndroidResources"] = true
        }

        listOf(
            iosX64(),
            iosArm64(),
            iosSimulatorArm64()
        ).forEach { iosTarget ->
            iosTarget.binaries.framework {
                baseName = this@configureKotlinMultiplatform.pathToFrameworkName()
            }
        }

        applyDefaultHierarchyTemplate()

        compilerOptions {
            freeCompilerArgs.add("-Xexpect-actual-classes")
            freeCompilerArgs.add("-opt-in=kotlin.RequiresOptIn")
            freeCompilerArgs.add("-opt-in=kotlin.time.ExperimentalTime")
        }
    }
}
```

### Helper: KotlinAndroidTarget.kt

```kotlin
package com.<company>.convention

import org.gradle.api.Project
import org.gradle.kotlin.dsl.dependencies

internal fun Project.configureAndroidLibraryTarget() {
    dependencies {
        "coreLibraryDesugaring"(libs.findLibrary("android-desugarJdkLibs").get())
    }
}
```

### Helper: KotlinDesktopTarget.kt

```kotlin
package com.<company>.convention

import org.gradle.api.Project
import org.gradle.kotlin.dsl.configure
import org.jetbrains.kotlin.gradle.dsl.JvmTarget
import org.jetbrains.kotlin.gradle.dsl.KotlinMultiplatformExtension

internal fun Project.configureDesktopTarget() {
    extensions.configure<KotlinMultiplatformExtension> {
        jvm("desktop") {
            compilations.all {
                compileTaskProvider.configure {
                    compilerOptions {
                        jvmTarget.set(JvmTarget.JVM_17)
                    }
                }
            }
        }
    }
}
```

### Helper: KotlinIosTargets.kt

```kotlin
package com.<company>.convention

import org.gradle.api.Project
import org.gradle.kotlin.dsl.configure
import org.jetbrains.kotlin.gradle.dsl.KotlinMultiplatformExtension

internal fun Project.configureIosTargets() {
    extensions.configure<KotlinMultiplatformExtension> {
        listOf(
            iosX64(),
            iosArm64(),
            iosSimulatorArm64()
        ).forEach { iosTarget ->
            iosTarget.binaries.framework {
                baseName = "ComposeApp"
                isStatic = true
            }
        }
    }
}
```

### Plugin: AndroidApplicationConventionPlugin

```kotlin
import com.android.build.api.dsl.ApplicationExtension
import com.<company>.convention.configureKotlinAndroid
import com.<company>.convention.libs
import org.gradle.api.Plugin
import org.gradle.api.Project
import org.gradle.kotlin.dsl.configure

class AndroidApplicationConventionPlugin : Plugin<Project> {
    override fun apply(target: Project) {
        with(target) {
            with(pluginManager) {
                apply("com.android.application")
            }

            extensions.configure<ApplicationExtension> {
                namespace = "com.<company>.appname"

                defaultConfig {
                    applicationId = libs.findVersion("projectApplicationId").get().toString()
                    targetSdk = libs.findVersion("projectTargetSdkVersion").get().toString().toInt()
                    versionCode = libs.findVersion("projectVersionCode").get().toString().toInt()
                    versionName = libs.findVersion("projectVersionName").get().toString()
                }
                packaging {
                    resources {
                        excludes += "/META-INF/{AL2.0,LGPL2.1}"
                    }
                }
                buildTypes {
                    getByName("release") {
                        isMinifyEnabled = false
                    }
                }

                configureKotlinAndroid(this)
            }
        }
    }
}
```

### Plugin: AndroidApplicationComposeConventionPlugin

```kotlin
import com.android.build.api.dsl.ApplicationExtension
import com.<company>.convention.configureAndroidCompose
import org.gradle.api.Plugin
import org.gradle.api.Project
import org.gradle.kotlin.dsl.getByType

class AndroidApplicationComposeConventionPlugin : Plugin<Project> {
    override fun apply(target: Project) {
        with(target) {
            with(pluginManager) {
                apply("com.<company>.convention.android.application")
                apply("org.jetbrains.kotlin.plugin.compose")
            }

            val extension = extensions.getByType<ApplicationExtension>()
            configureAndroidCompose(extension)
        }
    }
}
```

### Plugin: KmpLibraryConventionPlugin

The base plugin for all KMP modules without Compose. Uses the new Gradle 9 `com.android.kotlin.multiplatform.library` plugin.

```kotlin
import com.<company>.convention.configureKotlinMultiplatform
import com.<company>.convention.libs
import org.gradle.api.Plugin
import org.gradle.api.Project
import org.gradle.kotlin.dsl.dependencies

class KmpLibraryConventionPlugin : Plugin<Project> {
    override fun apply(target: Project) {
        with(target) {
            with(pluginManager) {
                apply("com.android.kotlin.multiplatform.library")
                apply("org.jetbrains.kotlin.multiplatform")
                apply("org.jetbrains.kotlin.plugin.serialization")
            }

            configureKotlinMultiplatform()

            dependencies {
                "commonMainImplementation"(libs.findLibrary("kotlinx-serialization-json").get())
                "commonTestImplementation"(libs.findLibrary("kotlin-test").get())
            }
        }
    }
}
```

### Plugin: CmpLibraryConventionPlugin

Extends `kmp.library` with Compose Multiplatform. Adds `androidMainImplementation` for tooling to enable previews.

```kotlin
import com.<company>.convention.libs
import org.gradle.api.Plugin
import org.gradle.api.Project
import org.gradle.kotlin.dsl.dependencies

class CmpLibraryConventionPlugin : Plugin<Project> {
    override fun apply(target: Project) {
        with(target) {
            with(pluginManager) {
                apply("com.<company>.convention.kmp.library")
                apply("org.jetbrains.kotlin.plugin.compose")
                apply("org.jetbrains.compose")
            }

            dependencies {
                "commonMainImplementation"(libs.findLibrary("jetbrains-compose-ui").get())
                "commonMainImplementation"(libs.findLibrary("jetbrains-compose-foundation").get())
                "commonMainImplementation"(libs.findLibrary("jetbrains-compose-material3").get())
                "commonMainImplementation"(libs.findLibrary("jetbrains-compose-material-icons-core").get())

                // Android previews: KMP modules cannot use debugImplementation (no build type awareness).
                // Use androidMainImplementation instead.
                "androidMainImplementation"(libs.findLibrary("androidx-compose-ui-tooling").get())
            }
        }
    }
}
```

### Plugin: CmpFeatureConventionPlugin

Extends `cmp.library` with presentation-layer dependencies: Koin, Navigation, Lifecycle, SavedStateHandle. Auto-depends on `:core:presentation` and `:core:designsystem`.

```kotlin
import com.<company>.convention.libs
import org.gradle.api.Plugin
import org.gradle.api.Project
import org.gradle.kotlin.dsl.dependencies

class CmpFeatureConventionPlugin : Plugin<Project> {
    override fun apply(target: Project) {
        with(target) {
            with(pluginManager) {
                apply("com.<company>.convention.cmp.library")
            }

            dependencies {
                "commonMainImplementation"(project(":core:presentation"))
                "commonMainImplementation"(project(":core:designsystem"))

                "commonMainImplementation"(platform(libs.findLibrary("koin-bom").get()))
                "androidMainImplementation"(platform(libs.findLibrary("koin-bom").get()))

                "commonMainImplementation"(libs.findLibrary("koin-compose").get())
                "commonMainImplementation"(libs.findLibrary("koin-compose-viewmodel").get())

                "commonMainImplementation"(libs.findLibrary("jetbrains-compose-runtime").get())
                "commonMainImplementation"(libs.findLibrary("jetbrains-compose-viewmodel").get())
                "commonMainImplementation"(libs.findLibrary("jetbrains-lifecycle-viewmodel").get())
                "commonMainImplementation"(libs.findLibrary("jetbrains-lifecycle-compose").get())

                "commonMainImplementation"(libs.findLibrary("jetbrains-lifecycle-viewmodel-savedstate").get())
                "commonMainImplementation"(libs.findLibrary("jetbrains-savedstate").get())
                "commonMainImplementation"(libs.findLibrary("jetbrains-bundle").get())
                "commonMainImplementation"(libs.findLibrary("jetbrains-compose-navigation").get())

                "androidMainImplementation"(libs.findLibrary("koin-android").get())
                "androidMainImplementation"(libs.findLibrary("koin-androidx-compose").get())
                "androidMainImplementation"(libs.findLibrary("koin-androidx-navigation").get())
                "androidMainImplementation"(libs.findLibrary("koin-core-viewmodel").get())
            }
        }
    }
}
```

### Plugin: CmpApplicationConventionPlugin

For the `:composeApp` module. Sets up KMP with Compose, all platform targets, and serialization.

```kotlin
import com.<company>.convention.configureAndroidLibraryTarget
import com.<company>.convention.configureDesktopTarget
import com.<company>.convention.configureIosTargets
import com.<company>.convention.libs
import org.gradle.api.Plugin
import org.gradle.api.Project
import org.gradle.kotlin.dsl.configure
import org.gradle.kotlin.dsl.dependencies
import org.jetbrains.kotlin.gradle.dsl.KotlinMultiplatformExtension

class CmpApplicationConventionPlugin : Plugin<Project> {
    override fun apply(target: Project) {
        with(target) {
            with(pluginManager) {
                apply("com.android.kotlin.multiplatform.library")
                apply("org.jetbrains.kotlin.multiplatform")
                apply("org.jetbrains.compose")
                apply("org.jetbrains.kotlin.plugin.compose")
                apply("org.jetbrains.kotlin.plugin.serialization")
            }

            configureAndroidLibraryTarget()
            configureIosTargets()
            configureDesktopTarget()

            extensions.configure<KotlinMultiplatformExtension> {
                applyDefaultHierarchyTemplate()
            }

            dependencies {
                // Android previews workaround for KMP modules
                "androidMainImplementation"(libs.findLibrary("androidx-compose-ui-tooling").get())
            }
        }
    }
}
```

### Plugin: RoomConventionPlugin

```kotlin
import androidx.room.gradle.RoomExtension
import com.<company>.convention.libs
import org.gradle.api.Plugin
import org.gradle.api.Project
import org.gradle.kotlin.dsl.configure
import org.gradle.kotlin.dsl.dependencies

class RoomConventionPlugin : Plugin<Project> {
    override fun apply(target: Project) {
        with(target) {
            with(pluginManager) {
                apply("com.google.devtools.ksp")
                apply("androidx.room")
            }

            extensions.configure<RoomExtension> {
                schemaDirectory("$projectDir/schemas")
            }

            dependencies {
                "commonMainApi"(libs.findLibrary("androidx-room-runtime").get())
                "commonMainApi"(libs.findLibrary("sqlite-bundled").get())
                "kspAndroid"(libs.findLibrary("androidx-room-compiler").get())
                "kspIosSimulatorArm64"(libs.findLibrary("androidx-room-compiler").get())
                "kspIosArm64"(libs.findLibrary("androidx-room-compiler").get())
                "kspIosX64"(libs.findLibrary("androidx-room-compiler").get())
                "kspDesktop"(libs.findLibrary("androidx-room-compiler").get())
            }
        }
    }
}
```

### Plugin: BuildKonfigConventionPlugin

```kotlin
import com.android.build.gradle.internal.cxx.configure.gradleLocalProperties
import com.codingfeline.buildkonfig.compiler.FieldSpec
import com.codingfeline.buildkonfig.gradle.BuildKonfigExtension
import com.<company>.convention.pathToPackageName
import org.gradle.api.Plugin
import org.gradle.api.Project
import org.gradle.kotlin.dsl.configure

class BuildKonfigConventionPlugin : Plugin<Project> {
    override fun apply(target: Project) {
        with(target) {
            with(pluginManager) {
                apply("com.codingfeline.buildkonfig")
            }

            extensions.configure<BuildKonfigExtension> {
                packageName = target.pathToPackageName()
                defaultConfigs {
                    val apiKey = gradleLocalProperties(rootDir, rootProject.providers)
                        .getProperty("API_KEY")
                        ?: throw IllegalStateException(
                            "Missing API_KEY property in local.properties"
                        )
                    buildConfigField(FieldSpec.Type.STRING, "API_KEY", apiKey)
                }
            }
        }
    }
}
```

---

## Version Catalog Conventions

Store all versions, dependencies, and plugin references in `gradle/libs.versions.toml`. No hardcoded versions in build files.

**Project config as version entries**:
```toml
[versions]
projectApplicationId = "com.<company>.appname"
projectVersionName = "1.0"
projectMinSdkVersion = "26"
projectTargetSdkVersion = "36"
projectCompileSdkVersion = "36"
projectVersionCode = "1"
```

**Convention plugin IDs** in the `[plugins]` section with `version = "unspecified"`:
```toml
[plugins]
convention-kmp-library = { id = "com.<company>.convention.kmp.library", version = "unspecified" }
convention-cmp-library = { id = "com.<company>.convention.cmp.library", version = "unspecified" }
convention-cmp-feature = { id = "com.<company>.convention.cmp.feature", version = "unspecified" }
convention-cmp-application = { id = "com.<company>.convention.cmp.application", version = "unspecified" }
convention-android-application = { id = "com.<company>.convention.android.application", version = "unspecified" }
convention-android-application-compose = { id = "com.<company>.convention.android.application.compose", version = "unspecified" }
convention-buildkonfig = { id = "com.<company>.convention.buildkonfig", version = "unspecified" }
convention-room = { id = "com.<company>.convention.room", version = "unspecified" }
```

**Dependency bundles** for common groups:
```toml
[bundles]
koin-common = ["koin-core", "koin-compose", "koin-compose-viewmodel"]
ktor-common = ["ktor-client-core", "ktor-client-content-negotiation", "ktor-serialization-kotlinx-json", "ktor-client-auth", "ktor-client-logging"]
```

---

## Root-Level Build Files

### settings.gradle.kts
```kotlin
rootProject.name = "AppName"
enableFeaturePreview("TYPESAFE_PROJECT_ACCESSORS")

pluginManagement {
    includeBuild("build-logic")
    repositories {
        google {
            mavenContent {
                includeGroupAndSubgroups("androidx")
                includeGroupAndSubgroups("com.android")
                includeGroupAndSubgroups("com.google")
            }
        }
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositories {
        google {
            mavenContent {
                includeGroupAndSubgroups("androidx")
                includeGroupAndSubgroups("com.android")
                includeGroupAndSubgroups("com.google")
            }
        }
        mavenCentral()
    }
}

include(":composeApp")
include(":androidApp")
include(":core:domain")
include(":core:data")
include(":core:presentation")
include(":core:designsystem")
// include feature modules...
```

### build.gradle.kts (root)

All plugins declared with `apply false` to load them once in the root classloader:
```kotlin
plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.android.library) apply false
    alias(libs.plugins.compose.multiplatform) apply false
    alias(libs.plugins.compose.compiler) apply false
    alias(libs.plugins.kotlin.multiplatform) apply false
    alias(libs.plugins.android.kotlin.multiplatform.library) apply false
    alias(libs.plugins.kotlin.serialization) apply false
    alias(libs.plugins.ksp) apply false
    alias(libs.plugins.room) apply false
    alias(libs.plugins.google.services) apply false
}
```

### gradle.properties
```properties
kotlin.code.style=official
kotlin.daemon.jvmargs=-Xmx3072M
org.gradle.jvmargs=-Xmx4096M -Dfile.encoding=UTF-8
org.gradle.configuration-cache=true
org.gradle.caching=true
android.nonTransitiveRClass=true
android.useAndroidX=true
kotlin.mpp.enableCInteropCommonization=true
```

---

## Example Module Build Files

After convention plugins are applied, individual module build files are minimal:

### core/domain/build.gradle.kts (kmp.library)
```kotlin
plugins {
    alias(libs.plugins.convention.kmp.library)
}

kotlin {
    sourceSets {
        commonMain {
            dependencies {
                implementation(libs.kotlinx.coroutines.core)
            }
        }
    }
}
```

### core/presentation/build.gradle.kts (cmp.library)
```kotlin
plugins {
    alias(libs.plugins.convention.cmp.library)
}

kotlin {
    sourceSets {
        commonMain {
            dependencies {
                implementation(projects.core.domain)
                implementation(libs.bundles.koin.common)
                implementation(compose.components.resources)
            }
        }
    }
}
```

### feature/auth/presentation/build.gradle.kts (cmp.feature)
```kotlin
plugins {
    alias(libs.plugins.convention.cmp.feature)
}

kotlin {
    sourceSets {
        commonMain {
            dependencies {
                implementation(projects.feature.auth.domain)
                implementation(projects.core.domain)
                implementation(compose.components.resources)
                implementation(compose.components.uiToolingPreview)
            }
        }
    }
}
```

### feature/chat/data/build.gradle.kts (kmp.library + buildkonfig)
```kotlin
plugins {
    alias(libs.plugins.convention.kmp.library)
    alias(libs.plugins.convention.buildkonfig)
}

kotlin {
    sourceSets {
        commonMain {
            dependencies {
                implementation(projects.core.data)
                implementation(projects.core.domain)
                implementation(projects.feature.chat.domain)
                implementation(libs.bundles.ktor.common)
                implementation(libs.koin.core)
            }
        }
        androidMain {
            dependencies {
                implementation(libs.ktor.client.okhttp)
                implementation(libs.koin.android)
            }
        }
        iosMain {
            dependencies {
                implementation(libs.ktor.client.darwin)
            }
        }
    }
}
```

### feature/chat/database/build.gradle.kts (kmp.library + room)
```kotlin
plugins {
    alias(libs.plugins.convention.kmp.library)
    alias(libs.plugins.convention.room)
}

kotlin {
    sourceSets {
        commonMain {
            dependencies {
                implementation(projects.core.data)
            }
        }
    }
}
```

---

## Key Libraries

| Concern | Library |
|---|---|
| DI | Koin |
| Networking | Ktor Client |
| Local DB | Room (KMP) |
| Preferences | DataStore |
| Navigation | Compose Navigation (type-safe, JetBrains) |
| Serialization | KotlinX Serialization (Ktor + Nav routes) |
| Image loading | Coil |
| Logging | Kermit |
| Async | Coroutines + Flow |
| Permissions | Moko Permissions |
| Adaptive layouts | Material3 Adaptive (JetBrains) |
| Secrets | BuildKonfig (reads from `local.properties`) |
| Background tasks | WorkManager (Android-only) — see **android-background** skill |
| Testing | JUnit5, Turbine, AssertK, `kotlinx-coroutines-test` |
| UI testing | `ComposeTestRule` |

---

## Checklist: Adding a New Feature Module

- [ ] Create `:feature:<name>:domain`, `:feature:<name>:data`, `:feature:<name>:presentation` modules
- [ ] Apply `convention.kmp.library` to domain and data, `convention.cmp.feature` to presentation
- [ ] Add modules to `settings.gradle.kts`
- [ ] Verify no cross-feature dependencies are introduced
- [ ] If logic is shared across 2+ features, extract to the appropriate `core` submodule
- [ ] If the feature needs a local DB, create `:feature:<name>:database` with `convention.kmp.library` + `convention.room`
- [ ] Wire module in `:composeApp` (add dependency + navigation + DI module)
