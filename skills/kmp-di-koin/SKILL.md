---
name: kmp-di-koin
description: |
  Koin dependency injection setup for Kotlin Multiplatform (Android + iOS) - module definitions per layer, ViewModel injection, assembling modules in :composeApp, platform modules for Android/iOS, and koinViewModel() in composables. Use this skill whenever setting up Koin, defining a DI module, providing a repository or ViewModel, injecting a dependency, or starting Koin from the Android Application class and the iOS entry point. Trigger on phrases like "set up Koin", "add a Koin module", "inject a dependency", "DI module", "koinViewModel", "provide a ViewModel", "startKoin", or "single/viewModel/factory".
---

# KMP Dependency Injection (Koin)

## Principles

- One Koin module per feature layer — create it only if there are dependencies to provide.
- Modules are assembled in `:composeApp` (the shared umbrella module), never in feature modules themselves.
- Modules are defined in `commonMain`. Dependencies that only exist per platform (Ktor engine, Room builder, DataStore path, anything needing `Context`) go into an `expect`/`actual` platform module.
- In Compose root composables, always inject ViewModels via `koinViewModel()`.

---

## Dependencies

| Source set | Artifact | Provides |
|---|---|---|
| `commonMain` | `io.insert-koin:koin-core` | `module`, `singleOf`, `factoryOf`, `bind`, `startKoin` |
| `commonMain` (presentation) | `io.insert-koin:koin-compose` | `koinInject()` |
| `commonMain` (presentation) | `io.insert-koin:koin-compose-viewmodel` | `viewModelOf`, `koinViewModel()` |
| `androidMain` | `io.insert-koin:koin-android` | `androidContext()`, `androidLogger()` |

Imports in common code — never the `org.koin.androidx.*` variants:

```kotlin
import org.koin.core.module.dsl.singleOf
import org.koin.core.module.dsl.factoryOf
import org.koin.core.module.dsl.bind
import org.koin.core.module.dsl.viewModelOf        // viewModelOf / viewModel { }
import org.koin.compose.viewmodel.koinViewModel    // koinViewModel()
```

---

## Module Definitions

Prefer the constructor-reference overloads (`singleOf`, `viewModelOf`, `factoryOf`) — they are more concise and let Koin resolve parameters automatically. Only fall back to the lambda overloads (`single { ... }`, `viewModel { ... }`, `factory { ... }`) when constructor injection alone is not enough, e.g. when you need to call a factory method, pass a named/qualified dependency, or do post-construction setup.

### Data layer module

```kotlin
// feature:notes:data
val notesDataModule = module {
    singleOf(::RoomNoteRepository) { bind<NoteRepository>() }
}
```

### Presentation layer module

```kotlin
// feature:notes:presentation
val notesPresentationModule = module {
    viewModelOf(::NoteListViewModel)
    viewModelOf(::NoteDetailViewModel)
}
```

### Core data module (example)

```kotlin
// core:data — commonMain
val coreDataModule = module {
    includes(coreDataPlatformModule)

    // singleOf works when the class has a single injectable constructor
    singleOf(::SessionPreferences)

    // Lambda overload needed here — calling a factory method, not a constructor
    single { HttpClientFactory.create(get()) }
}
```

### Platform module (`expect`/`actual`)

Anything that is constructed differently per platform is provided by a platform module that the common module includes:

```kotlin
// core:data — commonMain
expect val coreDataPlatformModule: Module

// core:data — androidMain
actual val coreDataPlatformModule = module {
    single<HttpClientEngine> { OkHttp.create() }
    single { createDataStore(androidContext()) }
}

// core:data — iosMain
actual val coreDataPlatformModule = module {
    single<HttpClientEngine> { Darwin.create() }
    single { createDataStore() }
}
```

Only create a platform module when a module actually has platform-specific dependencies.

---

## Assembly in `:composeApp`

Register all modules in a shared `initKoin` function in `:composeApp`'s `commonMain`. Each platform calls it exactly once at startup:

```kotlin
// :composeApp — commonMain
fun initKoin(config: KoinAppDeclaration? = null) {
    startKoin {
        config?.invoke(this)
        modules(
            // core
            coreDataModule,
            // features
            notesDataModule,
            notesPresentationModule,
            authDataModule,
            authPresentationModule,
            // ...
        )
    }
}
```

### Android (`:androidApp`)

```kotlin
class App : Application() {
    override fun onCreate() {
        super.onCreate()
        initKoin {
            androidContext(this@App)
        }
    }
}
```

### iOS (`iosApp/iOSApp.swift`)

Start Koin in the `init` of the SwiftUI `App` struct, so it runs once at app launch before any view controller exists:

```swift
import SwiftUI
import ComposeApp

@main
struct iOSApp: App {
    init() {
        InitKoinKt.doInitKoin(config: nil)
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}
```

Kotlin/Native exports a top-level function from `InitKoin.kt` on the `InitKoinKt` class and prefixes names that start with `init` with `do`, so `initKoin` becomes `doInitKoin`. Swift doesn't see Kotlin default arguments, so pass `config: nil` explicitly.

`MainViewController()` in `iosMain` stays a plain `ComposeUIViewController { App() }`. Don't start Koin there with `configure`: the view controller can be created more than once, and a second `startKoin` throws. Start Koin in exactly one place per platform.

---

## Injecting in Composables

Always use `koinViewModel()` in Root composables:

```kotlin
@Composable
fun NoteListRoot(
    onNavigateToDetail: (String) -> Unit,
    viewModel: NoteListViewModel = koinViewModel()
) { ... }
```

Never pass ViewModels down the composable tree — inject at the Root level only.

`koinViewModel()` comes from `org.koin.compose.viewmodel` and works on both platforms. A `SavedStateHandle` constructor parameter is resolved automatically by `viewModelOf`.

---

## Scoping Rules

| Scope | Preferred form | Fallback form | When to use |
|---|---|---|---|
| Singleton | `singleOf(::Impl) { bind<Interface>() }` | `single { ... }` | One instance for the app lifetime (repositories, HttpClient, DB) |
| ViewModel | `viewModelOf(::MyViewModel)` | `viewModel { ... }` | ViewModel instances scoped to their lifecycle |
| Factory | `factoryOf(::Impl)` | `factory { ... }` | New instance on every injection (rare — prefer singleton or ViewModel) |

Use the `*Of` constructor-reference form by default. Only use the lambda form when you cannot express the binding with a constructor reference (factory methods, named qualifiers, manual setup).

---

## Naming Conventions

| Thing | Convention | Example |
|---|---|---|
| Koin module | `<feature><Layer>Module` | `notesDataModule`, `notesPresentationModule` |

---

## Worker DI

WorkManager is Android-only. Worker bindings (`worker { }` scope, `KoinWorkerFactory`) go into an `androidMain` platform module, never into a common module; the iOS counterpart (e.g. `BGTaskScheduler`) is wired in the `iosMain` platform module behind the same common interface. For the Android side, see the **android-background** skill.

---

## Checklist: Adding DI for a New Feature

- [ ] Define `val <feature>DataModule = module { ... }` in `feature:data`
- [ ] Define `val <feature>PresentationModule = module { ... }` in `feature:presentation`
- [ ] Add an `expect`/`actual` platform module if the feature has platform-specific dependencies — with actuals in `androidMain` **and** `iosMain`
- [ ] Register the modules in `:composeApp`'s `initKoin { modules(...) }`
- [ ] Use `koinViewModel()` in all Root composables
