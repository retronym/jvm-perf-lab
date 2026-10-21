// Benchmarks and profiles of a scala/scala3 compiler, run through perflab (README.md).
//
// The compiler is one of:
// - a checkout, loaded as a source dependency: this build loads its build and compiles its bootstrapped compiler, so
//   a compiler branch needs no lab commits. Name it with SCALA3_CHECKOUT (or -Dscala3.checkout) when the sbt server
//   starts.
// - a published compiler, from Maven Central or publishLocal (`scala3-bootstrapped/publishLocal` in a checkout), as
//   released: SCALA3_VERSION, -Dscala3.version, or the version in an untracked `.lab-version` file here (which holds
//   across sbt server restarts, unlike an environment variable).

val published: Option[String] = sys.props.get("scala3.version").orElse(sys.env.get("SCALA3_VERSION"))
  .orElse(Some(file(".lab-version")).filter(_.exists).map(IO.read(_).trim).filter(_.nonEmpty))

val checkout: Option[File] =
  if (published.isDefined) None
  else Some(sys.props.get("scala3.checkout").orElse(sys.env.get("SCALA3_CHECKOUT")).map(file(_).getCanonicalFile)
    .getOrElse(sys.error("set SCALA3_CHECKOUT to a scala/scala3 checkout, or SCALA3_VERSION to a published compiler")))

// retronym/jvm-perf-lab's JMH driver and profilers, and async-profiler's Span API: this checkout's, `mise run install`
// at its root, or -Dperflab.version=<version>
val perflabVersion = sys.props.getOrElse("perflab.version", "0.1.0-SNAPSHOT")

// Corpora live in a lampepfl/scala3-benchmarks checkout, beside the compiler checkout by default.
def corpora(near: File): String =
  sys.env.getOrElse("SCALA3_BENCHMARKS", (near / ".." / "scala3-benchmarks").getCanonicalPath) + "/bench-sources"

lazy val common = Seq(
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
)

lazy val lab: Project = checkout match {
  case Some(checkout) =>
    val compiler = ProjectRef(checkout, "scala3-compiler-bootstrapped")
    val library = ProjectRef(checkout, "scala-library-bootstrapped")
    project.in(file("."))
      .dependsOn(compiler)
      .enablePlugins(JmhPlugin)
      .settings(common)
      .settings(
        // compiled as the checkout compiles its bootstrapped projects: with its non-bootstrapped compiler
        scalaVersion := (compiler / scalaVersion).value,
        managedScalaInstance := false,
        scalaInstance := (compiler / scalaInstance).value,
        scalaCompilerBridgeBinaryJar := (compiler / scalaCompilerBridgeBinaryJar).value,
        autoScalaLibrary := false,
        crossPaths := false,
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
        Jmh / run / javaOptions ++= Seq(
          s"-Dcompilerlab.scalaLibrary=${(library / Compile / packageBin).value}",
          s"-Dcompilerlab.corpora=${corpora(checkout)}",
        ),
      )
  case None =>
    val version = published.get
    project.in(file("."))
      .enablePlugins(JmhPlugin)
      .settings(common)
      .settings(
        scalaVersion := version,
        libraryDependencies += "org.scala-lang" %% "scala3-compiler" % version,
        // the standard library as the published compiler ships it: scala3-library_3 and the scala-library it depends on
        Jmh / run / javaOptions ++= {
          val jars = (Compile / dependencyClasspath).value.map(_.data)
            .filter(f => f.getName.startsWith("scala3-library_3-") || f.getName.startsWith("scala-library-"))
          if (jars.isEmpty) sys.error("no scala3-library_3 / scala-library jar on the dependency classpath")
          Seq(
            s"-Dcompilerlab.scalaLibrary=${jars.mkString(java.io.File.pathSeparator)}",
            s"-Dcompilerlab.corpora=${corpora(baseDirectory.value / ".." / ".." / "..")}",
          )
        },
      )
}
