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
    // perflab's launch mode (doc/direct-launch.md in jvm-perf-lab): compiles the benchmark and writes <dir>/launch.json,
    // what `Jmh/run` would run, for perflab to snapshot and start itself; a remote worker has no sbt server to call
    perflabLaunch := {
      val out = file(complete.DefaultParsers.spaceDelimited("<dir>").parsed.headOption.getOrElse(sys.error("perflabLaunch <dir>")))
      val cp = (Jmh / fullClasspath).value.files.map(_.getCanonicalPath)
      val opts = (Jmh / run / javaOptions).value
      val main = (Jmh / run / mainClass).value.getOrElse(sys.error("no Jmh / run / mainClass"))
      val java = (Jmh / run / javaHome).value.getOrElse(file(sys.props("java.home"))) / "bin" / "java"
      val lab = baseDirectory.value
      def git(args: String*) = scala.util.Try(scala.sys.process.Process("git" +: "-C" +: lab.getPath +: args).!!.trim).getOrElse("")
      def str(s: String) = "\"" + s.flatMap {
        case '"' => "\\\""; case '\\' => "\\\\"; case '\n' => "\\n"; case c if c < ' ' => f"\\u${c.toInt}%04x"; case c => c.toString
      } + "\""
      def arr(xs: Seq[String]) = xs.map(str).mkString("[", ", ", "]")
      val json = Seq(
        "\"mainClass\": " + str(main),
        "\"java\": " + str(java.getCanonicalPath),
        "\"classpath\": " + arr(cp),
        "\"javaOptions\": " + arr(opts),
        // only the build's own output is snapshotted: out/ (inputs, bundles) is read where it is
        "\"roots\": " + arr(Seq(target.value.getCanonicalPath)),
        "\"build\": {\"checkout\": " + str(lab.getCanonicalPath) + ", \"commit\": " + str(git("rev-parse", "HEAD"))
          + ", \"dirty\": " + git("status", "--porcelain", "--untracked-files=no").nonEmpty + "}",
      ).mkString("{\n  ", ",\n  ", "\n}\n")
      IO.write(out / "launch.json", json)
      streams.value.log.info(s"perflabLaunch: ${out / "launch.json"}")
    },
  )

lazy val perflabLaunch = inputKey[Unit]("compiles the benchmark and writes <dir>/launch.json for perflab's launch mode")
