// Benchmarks and profiles of a scala/scala3 checkout's bootstrapped compiler, run through perflab (README.md).
//
// The checkout is a source dependency: this build loads its build and compiles its compiler, so a compiler branch
// needs no lab commits. Name it with SCALA3_CHECKOUT (or -Dscala3.checkout) when the sbt server starts.

val checkout = sys.props.get("scala3.checkout").orElse(sys.env.get("SCALA3_CHECKOUT")).map(file(_).getCanonicalFile)
  .getOrElse(sys.error("set SCALA3_CHECKOUT to a scala/scala3 checkout"))

val compiler = ProjectRef(checkout, "scala3-compiler-bootstrapped")
val library = ProjectRef(checkout, "scala-library-bootstrapped")


// retronym/jvm-perf-lab's JMH driver and profilers, and async-profiler's Span API: this checkout's, `mise run install`
// at its root, or -Dperflab.version=<version>
val perflabVersion = sys.props.getOrElse("perflab.version", "0.1.0-SNAPSHOT")

lazy val lab = project.in(file("."))
  .dependsOn(compiler)
  .enablePlugins(JmhPlugin)
  .settings(
    // compiled as the checkout compiles its bootstrapped projects: with its non-bootstrapped compiler
    scalaVersion := (compiler / scalaVersion).value,
    managedScalaInstance := false,
    scalaInstance := (compiler / scalaInstance).value,
    scalaCompilerBridgeBinaryJar := (compiler / scalaCompilerBridgeBinaryJar).value,
    autoScalaLibrary := false,
    crossPaths := false,
    scalacOptions ++= Seq("-feature", "-deprecation", "-Yexplicit-nulls", "-language:implicitConversions", "-encoding", "UTF8"),
    resolvers += Resolver.mavenLocal,
    libraryDependencies ++= Seq(
      "io.github.retronym.perflab" % "perflab-jmh" % perflabVersion,
      "io.github.retronym.perflab" % "perflab-spans" % perflabVersion,
    ),
    // JMH with perflab's default profilers (allocation, JIT activity) and @file arguments
    Jmh / run / mainClass := Some("io.github.retronym.perflab.jmh.Main"),
    // .jvmopts (sbt's, as the checkout's; add e.g. -XX:+DebugNonSafepoints for profilers) reaches the benchmark forks
    // too: JMH starts them with its launcher's JVM options, then the benchmark's @Fork(jvmArgsAppend), which win (heap,
    // stack size).
    Jmh / run / javaOptions ++= {
      val f = baseDirectory.value / ".jvmopts"
      if (f.exists) IO.readLines(f).map(_.trim).filter(l => l.nonEmpty && !l.startsWith("#")) else Nil
    },
    // The scalaLibrary corpus: the checkout's library sources, with the options its build compiles them with, minus
    // -Werror, the optimizer (benchmarked without it) and -sourcepath (the corpus is its own in-memory sourcepath)
    Jmh / run / javaOptions ++= {
      val opts = (library / Compile / compile / scalacOptions).value
      val kept = opts.zipWithIndex.collect {
        case (o, i) if o != "-Werror" && !o.startsWith("-opt") && o != "-sourcepath" && (i == 0 || opts(i - 1) != "-sourcepath") => o
      }
      val f = target.value / "scala-library-options.txt"
      IO.writeLines(f, kept)
      Seq(
        s"-Dcompilerlab.scalaLibraryOptions=$f",
        s"-Dcompilerlab.scalaLibrarySources=${(library / Compile / unmanagedSourceDirectories).value.mkString(java.io.File.pathSeparator)}",
      )
    },
    // Corpora live in a lampepfl/scala3-benchmarks checkout, beside the compiler checkout by default.
    Jmh / run / javaOptions ++= Seq(
      s"-Dcompilerlab.scalaLibrary=${(library / Compile / packageBin).value}",
      s"-Dcompilerlab.corpora=${sys.env.getOrElse("SCALA3_BENCHMARKS", (checkout / ".." / "scala3-benchmarks").getCanonicalPath)}/bench-sources",
    ),
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
