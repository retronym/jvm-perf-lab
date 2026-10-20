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

// The cost per definition (-Yprofile-defs-listener) is not upstream yet: SpanCostListener only compiles against a
// checkout that has it.
val hasCostListener = (checkout / "src/compiler/scala/tools/nsc/profile/DefCosts.scala").exists

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
    Compile / unmanagedSourceDirectories ++= (if (hasCostListener) Seq(baseDirectory.value / "src/costs/scala") else Nil),
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
  )
