// Benchmarks and profiles of a scala/scala compiler, run through perflab (README.md).
//
// The compiler is one of:
// - a checkout, loaded as a source dependency: this build loads its build and compiles its library, reflect and
//   compiler (quick), so a compiler branch needs no lab commits. Name it with SCALA_CHECKOUT (or -Dscala.checkout)
//   when the sbt server starts.
// - a published compiler, from Maven Central or publishLocal (`setupPublishBuild publishLocal` in a checkout, which
//   turns the optimizer on as a release does): SCALA_VERSION, -Dscala.version, or the version in an untracked
//   `.lab-version` file here (which holds across sbt server restarts, unlike an environment variable).

val published: Option[String] = sys.props.get("scala.version").orElse(sys.env.get("SCALA_VERSION"))
  .orElse(Some(file(".lab-version")).filter(_.exists).map(IO.read(_).trim).filter(_.nonEmpty))

val checkout: Option[File] =
  if (published.isDefined) None
  else Some(sys.props.get("scala.checkout").orElse(sys.env.get("SCALA_CHECKOUT")).map(file(_).getCanonicalFile)
    .getOrElse(sys.error("set SCALA_CHECKOUT to a scala/scala checkout, or SCALA_VERSION to a published compiler")))

// The checkout's build reads versions.properties from the working directory (project/VersionUtil.scala), not from its
// base directory; copy it here before that build loads.
val versionsCopied = checkout.forall { c => IO.copyFile(c / "versions.properties", file("versions.properties")); true }

// retronym/jvm-perf-lab's JMH driver and profilers, and async-profiler's Span API: this checkout's, `mise run install`
// at its root, or -Dperflab.version=<version>
val perflabVersion = sys.props.getOrElse("perflab.version", "0.1.0-SNAPSHOT")

// Corpora live in a scala/compiler-benchmark checkout, beside the compiler checkout by default.
def corpora(near: File): String =
  sys.env.getOrElse("COMPILER_BENCHMARK", (near / ".." / "compiler-benchmark").getCanonicalPath) + "/corpus"

lazy val common = Seq(
  resolvers += Resolver.mavenLocal,
  libraryDependencies ++= Seq(
    "io.github.retronym.perflab" % "perflab-jmh" % perflabVersion,
    "io.github.retronym.perflab" % "perflab-spans" % perflabVersion,
  ),
  // JMH with perflab's default profilers and @file arguments
  Jmh / run / mainClass := Some("io.github.retronym.perflab.jmh.Main"),
  Jmh / run / javaOptions ++= {
    if (!scala.util.Properties.isJavaAtLeast("17")) sys.error("the lab needs Java 17 or later (perflab-jmh)")
    Seq(
      "-Xss2M", // for CompileLoop; JMH's forks get it from @Fork too
      s"-Dcompilerlab.deps=${target.value / "deps"}",
    )
  },
)

lazy val lab: Project = checkout match {
  case Some(checkout) =>
    val library = ProjectRef(checkout, "library")
    val reflect = ProjectRef(checkout, "reflect")
    val compiler = ProjectRef(checkout, "compiler")
    Project("lab", file("."))
      .dependsOn(library, reflect, compiler)
      .enablePlugins(JmhPlugin)
      .settings(common)
      .settings(
        // compiled as the checkout compiles quick: with STARR
        scalaVersion := (compiler / scalaVersion).value,
        managedScalaInstance := false,
        scalaInstance := (compiler / scalaInstance).value,
        scalaModuleInfo ~= (_.map(_.withOverrideScalaVersion(false))),
        autoScalaLibrary := false,
        crossPaths := false,
        Jmh / run / javaOptions ++= Seq(
          s"-Dcompilerlab.checkout=$checkout",
          s"-Dcompilerlab.corpora=${corpora(checkout)}",
          s"-Dcompilerlab.scalaClasspath=${Seq((library / Compile / classDirectory).value, (reflect / Compile / classDirectory).value, (compiler / Compile / classDirectory).value).mkString(java.io.File.pathSeparator)}",
        ),
      )
  case None =>
    val version = published.get
    Project("lab", file("."))
      .enablePlugins(JmhPlugin)
      .settings(common)
      .settings(
        scalaVersion := version,
        crossPaths := false,
        libraryDependencies ++= Seq(
          "org.scala-lang" % "scala-compiler" % version,
          "org.scala-lang" % "scala-reflect" % version,
        ),
        Jmh / run / javaOptions ++= {
          val jars = (Compile / dependencyClasspath).value.map(_.data)
            .filter(f => f.getName.matches("(scala-library|scala-reflect|scala-compiler)(-[^/]*)?\\.jar")) // Maven's name-version.jar, Ivy's name.jar
          if (jars.size < 3) sys.error(s"expected the scala-library, scala-reflect and scala-compiler jars on the dependency classpath, found $jars")
          Seq(
            s"-Dcompilerlab.corpora=${corpora(baseDirectory.value / ".." / ".." / "..")}",
            s"-Dcompilerlab.scalaClasspath=${jars.mkString(java.io.File.pathSeparator)}",
          )
        },
      )
}
