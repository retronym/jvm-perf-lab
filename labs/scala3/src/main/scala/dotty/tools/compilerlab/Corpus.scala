package dotty.tools.compilerlab

import java.nio.file.{Files, Path}
import scala.jdk.CollectionConverters.*

import dotty.tools.io.{AbstractFile, VirtualFile}

/** Sources compiled together, read into memory once, with the options they need.
 *
 *  @param sourcePath       an in-memory directory of sources that dotc finds as on `-sourcepath`, or null
 *  @param withScalaLibrary the scala-library jar is on the classpath (not for the library itself)
 *  @param deps             jars on the classpath besides the JDK and the standard library
 */
final case class Corpus(name: String, files: List[AbstractFile], options: List[String],
    sourcePath: AbstractFile | Null = null, withScalaLibrary: Boolean = true, deps: List[Path] = Nil)

object Corpus:
  // Options from lampepfl/scala3-benchmarks' build.sbt, without -Werror.
  private val shared = List("-feature", "-deprecation")
  private val options = Map(
    "small" -> Nil,
    "dottyUtil" -> Nil,
    "re2s" -> Nil,
    "tastyQuery" -> List("-Yexplicit-nulls", "-Wconf:msg=Unnecessary .nn:s"),
    "scalaz" -> List("-nowarn", "-source", "3.0", "-Xkind-projector", "-language:implicitConversions"),
  )

  /** A corpus from a lampepfl/scala3-benchmarks checkout (`compilerlab.corpora` is its `bench-sources`), or, given an
   *  absolute path, the sources under that directory, with the options of the known corpus of the same name, if any.
   *
   *  A directory exported from a build (as the zinc integration campaigns' `export-build` lays a module out) has
   *  `src/` with Scala and Java sources, `lib/` with the jars of its classpath, and `incOptions.properties` with a
   *  `scalac.options` line. Its options are used in place of the known ones, less those that would turn a warning
   *  into an error (`ExportedOptions`); standard library jars in `lib/` are left out, since the compiler's own go on
   *  the classpath.
   */
  def load(name: String): Corpus =
    if name == "scalaLibrary" then return scalaLibrary
    val absolute = Path.of(name).isAbsolute
    val dir =
      if absolute then Path.of(name)
      else Path.of(sys.props.getOrElse("compilerlab.corpora", sys.error("-Dcompilerlab.corpora=<scala3-benchmarks>/bench-sources not set"))).resolve(name)
    val exported = ExportedOptions.read(dir)
    val opts = options.get(dir.getFileName.toString) match
      case _ if exported.isDefined => exported.get
      case Some(o) => shared ++ o
      case None if absolute => shared
      case None => sys.error(s"unknown corpus $name; known: ${(options.keys.toList :+ "scalaLibrary").sorted.mkString(", ")}, or an absolute path")
    val lib = dir.resolve("lib")
    val paths = Files.walk(dir).iterator.asScala
      .filter(p => !p.startsWith(lib) && (p.toString.endsWith(".scala") || (exported.isDefined && p.toString.endsWith(".java"))))
      .toList.sorted
    if paths.isEmpty then sys.error(s"no sources in $dir")
    Corpus(name, paths.map(p => VirtualFile(dir.relativize(p).toString, Files.readAllBytes(p))), opts, deps = ExportedOptions.deps(dir))

  /** The standard library of this checkout (`compilerlab.scalaLibrarySources`, its source directories), compiled as
   *  `scala-library-bootstrapped` compiles it (`compilerlab.scalaLibraryOptions`, a file of its options, one per line,
   *  without `-Werror`, `-opt` and `-sourcepath`), with no scala-library jar on the classpath. Its sources are also the
   *  in-memory sourcepath, for the library classes `Definitions` loads before the run enters the compilation units.
   */
  def scalaLibrary: Corpus =
    def prop(key: String): String = sys.props.getOrElse(key, sys.error(s"-D$key not set")).nn
    val dirs = prop("compilerlab.scalaLibrarySources").split(java.io.File.pathSeparator).toList.map(Path.of(_)).filter(Files.isDirectory(_))
    val options = Files.readAllLines(Path.of(prop("compilerlab.scalaLibraryOptions"))).asScala.toList.filter(_.nonEmpty)
    val root = dotty.tools.io.virtualDirectory("memory-scala-library-sources")
    val files =
      for
        dir <- dirs
        p <- Files.walk(dir).iterator.asScala.toList.sorted
        rel = dir.relativize(p).toString
        if rel.endsWith(".scala") || rel.endsWith(".java")
      yield
        val parts = rel.split('/').toList
        val file = parts.init.foldLeft(root)(_.subdirectoryNamed(_)).fileNamed(parts.last)
        val out = file.output
        try out.write(Files.readAllBytes(p)) finally out.close()
        file
    if files.isEmpty then sys.error(s"no sources in ${dirs.mkString(", ")}")
    Corpus("scalaLibrary", files, options, sourcePath = root, withScalaLibrary = false)

  /** A corpus from sources given inline, for micro benchmarks. */
  def inline(name: String, sources: (String, String)*): Corpus =
    Corpus(name, sources.toList.map((path, text) => VirtualFile(path, text.getBytes("UTF-8"))), shared)

/** The options and jars of a module directory exported from a build (`Corpus.load`). */
object ExportedOptions:
  /** `scalac.options` of `<dir>/incOptions.properties`, if there: `[basedir]` replaced by the directory, and without
   *  the options that make warnings errors (`-Werror`, `-Xfatal-warnings`, `-Wconf`), which differ by compiler version.
   */
  def read(dir: Path): Option[List[String]] =
    val f = dir.resolve("incOptions.properties")
    if !Files.exists(f) then None
    else
      val props = java.util.Properties()
      val in = Files.newInputStream(f)
      try props.load(in) finally in.close()
      val line = props.getProperty("scalac.options", "")
      Some(line.split("\\s+").toList.filter(_.nonEmpty).map(_.replace("[basedir]", dir.toString))
        .filterNot(o => o == "-Werror" || o == "-Xfatal-warnings" || o.startsWith("-Wconf")))

  /** The jars in `<dir>/lib`, except the standard library's (the compiler's own are on the classpath). */
  def deps(dir: Path): List[Path] =
    val lib = dir.resolve("lib")
    if !Files.isDirectory(lib) then Nil
    else
      val list = Files.list(lib)
      try list.iterator.asScala.filter(p => p.toString.endsWith(".jar") && !isStandardLibrary(p.getFileName.toString)).toList.sorted
      finally list.close()

  def isStandardLibrary(jar: String): Boolean =
    jar.startsWith("scala-library-") || jar.startsWith("scala3-library_3-") || jar.startsWith("scala-reflect-")
