import sbt._
import sbt.Keys._
import sbt.plugins.JvmPlugin

/** The zinc lab's one change to Pekko's build: warnings are not fatal. Pekko compiles with `-Xfatal-warnings` and
 *  `-Wconf:any:e`, which a JDK newer than the ones it targets (SecurityManager is deprecated) or a different compiler
 *  breaks; the lab compares compile times, not warning counts. Runs after PekkoDisciplinePlugin's settings. */
object LabRelax extends AutoPlugin {
  override lazy val trigger: PluginTrigger = allRequirements
  override lazy val requires: Plugins = JvmPlugin && PekkoDisciplinePlugin
  override lazy val projectSettings = Seq(
    Compile / scalacOptions ~= (_.filterNot(o => o == "-Xfatal-warnings" || o.startsWith("-Wconf:any:e"))),
    Test / scalacOptions ~= (_.filterNot(o => o == "-Xfatal-warnings" || o.startsWith("-Wconf:any:e"))),
    Compile / javacOptions ~= (_.filterNot(_ == "-Werror")),
    Test / javacOptions ~= (_.filterNot(_ == "-Werror")))
}
