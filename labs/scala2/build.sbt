// Benchmarks and profiles of a scala/scala checkout's quick compiler, run through perflab (README.md).
//
// The checkout is a source dependency: this build loads its build and compiles its library, reflect and compiler, so
// a compiler branch needs no lab commits. Name it with SCALA_CHECKOUT (or -Dscala.checkout) when the sbt server starts.

val checkout = sys.props.get("scala.checkout").orElse(sys.env.get("SCALA_CHECKOUT")).map(file(_).getCanonicalFile)
  .getOrElse(sys.error("set SCALA_CHECKOUT to a scala/scala checkout"))

// The checkout's build reads versions.properties from the working directory (project/VersionUtil.scala), not from its
// base directory; copy it here before that build loads.
val versionsCopied = { IO.copyFile(checkout / "versions.properties", file("versions.properties")); true }

val library = ProjectRef(checkout, "library")
val reflect = ProjectRef(checkout, "reflect")
val compiler = ProjectRef(checkout, "compiler")

// SCALA_RELEASE_OPT=1 (or -Dscala.releaseOpt=true): compile the checkout's library, reflect and compiler with the
// optimizer settings its published jars are built with (ScriptCommands.enableOptimizer), not quick's defaults
val releaseOpt = sys.props.get("scala.releaseOpt").orElse(sys.env.get("SCALA_RELEASE_OPT")).exists(Set("1", "true"))
Seq("library", "reflect", "compiler").filter(_ => releaseOpt).map(p => ProjectRef(checkout, p) / Compile / scalacOptions ++= Seq("-opt:l:inline", "-opt-inline-from:scala/**"))

// retronym/jvm-perf-lab's JMH driver and profilers, and async-profiler's Span API: this checkout's, `mise run install`
// at its root, or -Dperflab.version=<version>
val perflabVersion = sys.props.getOrElse("perflab.version", "0.1.0-SNAPSHOT")

lazy val lab = project.in(file("."))
  .dependsOn(library, reflect, compiler)
  .enablePlugins(JmhPlugin)
  .settings(
    // compiled as the checkout compiles quick: with STARR
    scalaVersion := (compiler / scalaVersion).value,
    managedScalaInstance := false,
    scalaInstance := (compiler / scalaInstance).value,
    scalaModuleInfo ~= (_.map(_.withOverrideScalaVersion(false))),
    autoScalaLibrary := false,
    crossPaths := false,
    resolvers += Resolver.mavenLocal,
    libraryDependencies ++= Seq(
      "io.github.retronym.perflab" % "perflab-jmh" % perflabVersion,
      "io.github.retronym.perflab" % "perflab-spans" % perflabVersion,
    ),
    // JMH with perflab's default profilers and @file arguments
    Jmh / run / mainClass := Some("io.github.retronym.perflab.jmh.Main"),
    Jmh / run / javaOptions ++= {
      if (!scala.util.Properties.isJavaAtLeast("17")) sys.error("the lab needs Java 17 or later (perflab-jmh)")
      // Corpora live in a scala/compiler-benchmark checkout, beside the compiler checkout by default.
      val corpora = sys.env.getOrElse("COMPILER_BENCHMARK", (checkout / ".." / "compiler-benchmark").getCanonicalPath)
      Seq(
        "-Xss2M", // for CompileLoop; JMH's forks get it from @Fork too
        s"-Dcompilerlab.checkout=$checkout",
        s"-Dcompilerlab.corpora=$corpora/corpus",
        s"-Dcompilerlab.scalaClasspath=${Seq((library / Compile / classDirectory).value, (reflect / Compile / classDirectory).value, (compiler / Compile / classDirectory).value).mkString(java.io.File.pathSeparator)}",
        s"-Dcompilerlab.deps=${target.value / "deps"}",
      )
    },
    // perflab's launch mode (doc/direct-launch.md in jvm-perf-lab): compiles the benchmarks and writes <dir>/launch.json,
    // what `Jmh/run` would run, for perflab to snapshot and start itself, with no sbt during the measurement
    perflabLaunch := {
      val out = file(complete.DefaultParsers.spaceDelimited("<dir>").parsed.headOption.getOrElse(sys.error("perflabLaunch <dir>")))
      val cp = (Jmh / fullClasspath).value.files.map(_.getCanonicalPath)
      val opts = (Jmh / run / javaOptions).value
      val main = (Jmh / run / mainClass).value.getOrElse(sys.error("no Jmh / run / mainClass"))
      val java = (Jmh / run / javaHome).value.getOrElse(file(sys.props("java.home"))) / "bin" / "java"
      def git(args: String*) = scala.util.Try(scala.sys.process.Process("git" +: "-C" +: checkout.getPath +: args).!!.trim).getOrElse("")
      def str(s: String) = "\"" + s.flatMap {
        case '"' => "\\\""; case '\\' => "\\\\"; case '\n' => "\\n"; case c if c < ' ' => f"\\u${c.toInt}%04x"; case c => c.toString
      } + "\""
      def arr(xs: Seq[String]) = xs.map(str).mkString("[", ", ", "]")
      val json = Seq(
        "\"mainClass\": " + str(main),
        "\"java\": " + str(java.getCanonicalPath),
        "\"classpath\": " + arr(cp),
        "\"javaOptions\": " + arr(opts),
        // the directories whose files are this build's own output, which perflab copies into its snapshot
        "\"roots\": " + arr(Seq(baseDirectory.value.getCanonicalPath, checkout.getPath)),
        "\"build\": {\"checkout\": " + str(checkout.getPath) + ", \"commit\": " + str(git("rev-parse", "HEAD"))
          + ", \"dirty\": " + git("status", "--porcelain", "--untracked-files=no").nonEmpty + "}",
      ).mkString("{\n  ", ",\n  ", "\n}\n")
      IO.write(out / "launch.json", json)
      streams.value.log.info(s"perflabLaunch: ${out / "launch.json"}")
    },
  )

lazy val perflabLaunch = inputKey[Unit]("compiles the benchmarks and writes <dir>/launch.json for perflab's launch mode")
