import com.android.build.api.dsl.ApplicationExtension
import com.android.build.api.dsl.LibraryExtension
import org.gradle.api.Plugin
import org.gradle.api.Project
import org.gradle.api.artifacts.VersionCatalogsExtension
import org.gradle.kotlin.dsl.configure
import org.gradle.kotlin.dsl.getByType
import org.gradle.testing.jacoco.plugins.JacocoPluginExtension

/**
 * Sets up JaCoCo coverage for whichever module applies this plugin:
 *
 *  - applies the `jacoco` plugin and pins its tool version from the version catalog
 *    (`[versions] jacoco`), so reports use a known JaCoCo release;
 *  - for Android library/application modules, enables unit-test AND
 *    instrumentation-test coverage on the `debug` build type. Those flags are what
 *    make AGP instrument the bytecode and generate the coverage report tasks
 *    (`createDebugUnitTestCoverageReport`, the androidTest coverage report, etc.).
 *
 * Pure Kotlin/JVM modules just get the `jacoco` plugin (its default `test` +
 * `jacocoTestReport` wiring), since the AGP build-type flags don't apply to them.
 */
class JacocoConventionPlugin : Plugin<Project> {
    override fun apply(target: Project) = with(target) {
        pluginManager.apply("jacoco")

        val libs = extensions.getByType<VersionCatalogsExtension>().named("libs")
        extensions.configure<JacocoPluginExtension> {
            toolVersion = libs.findVersion("jacoco").get().requiredVersion
        }

        pluginManager.withPlugin("com.android.library") {
            extensions.configure<LibraryExtension> {
                buildTypes.getByName("debug") {
                    enableUnitTestCoverage = true
                    enableAndroidTestCoverage = true
                }
            }
        }
        pluginManager.withPlugin("com.android.application") {
            extensions.configure<ApplicationExtension> {
                buildTypes.getByName("debug") {
                    enableUnitTestCoverage = true
                    enableAndroidTestCoverage = true
                }
            }
        }
    }
}
