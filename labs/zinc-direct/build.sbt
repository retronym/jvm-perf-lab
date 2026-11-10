// Direct-Zinc compile benchmark (README.md): drives Zinc through its API, one class loader per Zinc version. The lab is
// plain Java; Zinc 1.12.1's API is on the compile classpath only (provided): the benchmark loads the driver
// (zincdirect.driver) in a loader of the Zinc under test, never in the benchmark's own.

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
      "org.scala-sbt" % "zinc_2.12" % "1.12.1" % Provided,
      "org.scala-lang" % "scala-library" % "2.12.21" % Provided,
    ),
    Compile / javacOptions ++= Seq("--release", "21"),
    Jmh / run / mainClass := Some("io.github.retronym.perflab.jmh.Main"),
    Jmh / run / javaOptions ++= {
      if (!scala.util.Properties.isJavaAtLeast("21")) sys.error("the lab needs Java 21 or later")
      Seq("-Xss4M")
    },
  )
