// JVM unit-test coverage — applied at runtime via `--init-script`.
//
// This is deliberately non-invasive: it does NOT write anything to the project's
// committed build files. It attaches JaCoCo to each subproject's JVM unit-test
// task (so the test run records execution data) and registers a `jvmCoverage`
// task that emits a JaCoCo XML report. A bundled Python script then renders that
// XML as the Android-Studio-style module → package → class table.
//
// Why JaCoCo: `testDebugUnitTest` / `test` produce no coverage on their own —
// Gradle has no built-in coverage engine. JaCoCo instruments the compiled
// bytecode in-process during the normal JVM test run (no device, no Android
// instrumented tests). This is the same engine AGP's `enableUnitTestCoverage`
// uses under the hood.

import org.gradle.testing.jacoco.tasks.JacocoReport

allprojects {
    afterEvaluate {
        // Pick the JVM unit-test task by applied plugin, NOT by task existence.
        // AGP creates `testDebugUnitTest` in its own afterEvaluate, which may run
        // after this one — so `tasks.findByName(...)` would miss it. Plugins, by
        // contrast, are already applied by the time any afterEvaluate runs.
        // We depend on the task by name (a String dependency Gradle resolves
        // lazily at execution time), so the task need not exist yet here.
        val isAndroid = pluginManager.hasPlugin("com.android.base")
        val isKotlinJvm = pluginManager.hasPlugin("org.jetbrains.kotlin.jvm") ||
            pluginManager.hasPlugin("java")
        val unitTestTaskName = when {
            isAndroid -> "testDebugUnitTest"
            isKotlinJvm -> "test"
            else -> return@afterEvaluate // no JVM unit-test task (e.g. an umbrella module)
        }

        // Applying `jacoco` makes the JaCoCo plugin attach its agent to every
        // `Test` task (enabled by default), so the unit-test run writes a `.exec`
        // execution-data file at build/jacoco/<taskName>.exec.
        pluginManager.apply("jacoco")

        // Class output dirs differ between Android and pure-Kotlin modules. We list
        // every plausible location and keep only the ones that exist for this module.
        val classDirCandidates = listOf(
            // Android Kotlin — AGP 9.x built-in Kotlin compiler output.
            "intermediates/built_in_kotlinc/debug/compileDebugKotlin/classes",
            "tmp/kotlin-classes/debug",                              // Android Kotlin (AGP 8.x and earlier)
            // Android Java.
            "intermediates/javac/debug/compileDebugJavaWithJavac/classes",
            "intermediates/javac/debug/classes",
            // Pure Kotlin/JVM and pure Java modules.
            "classes/kotlin/main",
            "classes/java/main",
        )

        // Exclude generated / non-meaningful code so the numbers match what a human
        // would consider "their code" — the same things Android Studio omits.
        val coverageExcludes = listOf(
            "**/R.class",
            "**/R$*.class",
            "**/BuildConfig.*",
            "**/Manifest*.*",
            "**/*_Factory.*",
            "**/*_MembersInjector.*",
            "**/Dagger*.*",
            "**/di/**",
            "**/*ComposableSingletons*.*",
            "**/*\$\$serializer.*",
        )

        val classDirectoriesTree = files(
            classDirCandidates.map { relativePath ->
                fileTree(layout.buildDirectory.dir(relativePath)) {
                    exclude(coverageExcludes)
                }
            }
        )

        val sourceDirs = files("src/main/java", "src/main/kotlin")
        val executionDataFile = files(
            layout.buildDirectory.file("jacoco/$unitTestTaskName.exec")
        )

        tasks.register("jvmCoverage", JacocoReport::class.java) {
            dependsOn(unitTestTaskName)
            group = "verification"
            description = "JVM unit-test coverage (JaCoCo XML for the render script)."

            sourceDirectories.setFrom(sourceDirs)
            classDirectories.setFrom(classDirectoriesTree)
            executionData.setFrom(executionDataFile)

            reports {
                xml.required.set(true)
                html.required.set(false)
                csv.required.set(false)
                xml.outputLocation.set(
                    layout.buildDirectory.file("reports/jvm-coverage/coverage.xml")
                )
            }
        }
    }
}
