import sbt._
import sbt.Keys._
import sbt.plugins.JvmPlugin

/** The zinc lab's changes to Pekko's build: the Scala optimizer is off (sbt-pekko-build turns it on with
 *  `-opt:l:inline -opt-inline-from:...`; it is not what the lab compares), and warnings are not fatal. Pekko compiles with `-Xfatal-warnings` and
 *  `-Wconf:any:e`, which a JDK newer than the ones it targets (SecurityManager is deprecated) or a different compiler
 *  breaks; the lab compares compile times, not warning counts. Runs after PekkoDisciplinePlugin's settings. */
object LabRelax extends AutoPlugin {
  override lazy val trigger: PluginTrigger = allRequirements
  override lazy val requires: Plugins = JvmPlugin && PekkoDisciplinePlugin && com.github.pjfanning.pekkobuild.PekkoInlinePlugin
  override lazy val projectSettings = Seq(
    Compile / scalacOptions ~= (_.filterNot(o => o == "-Xfatal-warnings" || o.startsWith("-Wconf:any:e") || o.startsWith("-opt"))),
    Test / scalacOptions ~= (_.filterNot(o => o == "-Xfatal-warnings" || o.startsWith("-Wconf:any:e") || o.startsWith("-opt"))),
    Compile / javacOptions ~= (_.filterNot(_ == "-Werror")),
    Test / javacOptions ~= (_.filterNot(_ == "-Werror")))
}
