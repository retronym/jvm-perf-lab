// Whole-build compile benchmark: hosts sbt in the benchmark JVM (README.md). The lab itself is plain Java; the sbt
// under test is chosen per fork (`sbtVersion`), booted by the launcher from the build's project/build.properties.

val perflabVersion = sys.props.getOrElse("perflab.version", "0.1.0-SNAPSHOT")

lazy val lab = project.in(file("."))
  .enablePlugins(JmhPlugin)
  .settings(
    scalaVersion := "2.12.21",
    autoScalaLibrary := false,
    crossPaths := false,
    resolvers += Resolver.mavenLocal,
    libraryDependencies ++= Seq(
      "io.github.retronym.perflab" % "perflab-jmh" % perflabVersion,
      // the launcher boots whichever sbt the workspace's build.properties names; any 1.x launcher does
      "org.scala-sbt" % "sbt-launch" % "1.12.15",
    ),
    Compile / javacOptions ++= Seq("--release", "21"),
    Jmh / run / mainClass := Some("io.github.retronym.perflab.jmh.Main"),
    Jmh / run / javaOptions ++= {
      if (!scala.util.Properties.isJavaAtLeast("21")) sys.error("the lab needs Java 21 or later")
      Seq("-Xss2M")
    },
  )
