package scala.tools.nsc.compilerlab

import scala.reflect.internal.Reporter.ERROR
import scala.reflect.io.VirtualDirectory
import scala.tools.nsc.{Global, Settings}
import scala.tools.nsc.reporters.StoreReporter

/** Compiles one corpus, again and again, with no file I/O after construction.
 *
 *  Sources are in-memory files read up front, the classpath is an `InMemoryClasspath` snapshot installed as the
 *  platform's classpath (bypassing `PathResolver`), and class files are generated and serialized into an output
 *  directory that keeps no bytes, as one on `/dev/null` would (`DiscardingDirectory`), so a compilation's output is
 *  not live while the next one runs. With `keepOutput` (`-Dcompilerlab.output=keep`) the output is an in-memory
 *  directory that holds every class file until the next compilation.
 *
 *  By default each compilation starts from scratch, with a new `Global`: it pays for everything a cold compile does
 *  (definitions, classpath indexing, symbol loading) except reading files and JIT warmup, and nothing survives from
 *  one compilation to the next. With `resident = true`, compilations share one `Global`, each a new `Run`, as a
 *  compile server or the REPL does.
 *
 *  `--defs:<file>` and `--defs-listener:<class>` among the options turn on the cost per definition (`CostHooks`), with
 *  perflab-agent weaving its hooks.
 */
final class InMemoryCompiler(val corpus: Corpus, options: List[String] = Nil, resident: Boolean = false,
                             keepOutput: Boolean = InMemoryCompiler.keepOutputByDefault) extends Compiling {
  // the lab's options for the cost per definition (CostHooks), which scalac does not see
  private val (costOptions, extraOptions) = options.partition(_.startsWith("--defs"))
  private val (defsTable, defsListener) = {
    def value(name: String) = costOptions.collectFirst { case o if o.startsWith(name + ":") => o.stripPrefix(name + ":") }.orNull
    costOptions.find(o => !o.startsWith("--defs:") && !o.startsWith("--defs-listener:")).foreach(o => throw new IllegalArgumentException(s"unknown option $o"))
    (value("--defs"), value("--defs-listener"))
  }

  /** The classpath snapshot this compiler reads. */
  val classpathSnapshot: InMemoryClasspath = InMemoryClasspath.forCorpus(corpus)

  /** The output of the latest compilation. */
  var output: VirtualDirectory = newOutput()

  private def newOutput(): VirtualDirectory =
    if (keepOutput) new VirtualDirectory("compiler-lab-output", None)
    else new DiscardingDirectory("compiler-lab-output", None)

  private def newGlobal(out: VirtualDirectory): Global = {
    val args = corpus.options ::: extraOptions
    val settings = new Settings(msg => throw new IllegalArgumentException(s"${corpus.name}: $msg"))
    val (ok, residual) = settings.processArguments(args, processAll = true)
    if (!ok || residual.nonEmpty) throw new IllegalArgumentException(s"bad options: ${args.mkString(" ")}")
    settings.outputDirs.setSingleOutput(out)
    val cp = classpathSnapshot.classPath(corpus.sourcePath)
    new Global(settings, new StoreReporter(settings)) {
      override lazy val platform: ThisPlatform = new GlobalPlatform {
        currentClassPath = Some(cp)
      }
    }
  }

  lazy val residentGlobal: Global = newGlobal(output)

  /** One full compilation of the corpus. */
  def compile(): Unit = {
    val global =
      if (resident) residentGlobal
      else {
        output = newOutput()
        newGlobal(output)
      }
    val reporter = global.reporter.asInstanceOf[StoreReporter]
    reporter.reset()
    val costs = defsTable != null || defsListener != null
    try {
      // from before the run, as the compiler's -Yprofile-defs: making it loads the root classes
      if (costs) CostHooks.start(global, defsTable, defsListener)
      try new global.Run().compileFiles(corpus.files)
      finally if (costs) CostHooks.finish()
    } catch {
      case e: Exception =>
        throw new IllegalStateException(s"${corpus.name}: compiler crashed after:\n${errors(reporter).mkString("\n")}", e)
    } finally if (!resident) global.close()
    if (reporter.hasErrors) throw new IllegalStateException(s"${corpus.name} failed to compile:\n${errors(reporter).mkString("\n")}")
  }

  private def errors(r: StoreReporter) = r.infos.iterator.filter(_.severity == ERROR).take(10).map(i => s"${i.pos}: ${i.msg}").toList

  /** Number of files in the latest output, to check the backend ran. */
  def outputCount: Int = {
    def count(f: scala.reflect.io.AbstractFile): Int = if (f.isDirectory) f.iterator.map(count).sum else 1
    count(output)
  }
}

object InMemoryCompiler {
  /** `-Dcompilerlab.output=keep` keeps every class file of the latest compilation in memory. By default output is
   *  discarded as written: an 8-compile census found the kept class files were most of the `byte[]` that young
   *  collections copied and promoted, about 90 MB per compile, a cost a build writing to disk does not pay.
   */
  val keepOutputByDefault: Boolean = sys.props.get("compilerlab.output").contains("keep")
}

/** An in-memory output directory whose files keep no content: what is written to them is counted and dropped. The file
 *  entries are kept, so `outputCount` still checks that the backend ran. */
final class DiscardingDirectory(name: String, maybeContainer: Option[VirtualDirectory])
    extends scala.reflect.io.VirtualDirectory(name, maybeContainer) {
  private[this] val entries = scala.collection.mutable.Map.empty[String, scala.reflect.io.AbstractFile]
  /** Bytes written to this directory's files, not counting subdirectories. */
  @volatile var bytesWritten: Long = 0L

  override def iterator = entries.values.toList.iterator
  override def lookupName(name: String, directory: Boolean): scala.reflect.io.AbstractFile =
    entries.get(name).filter(_.isDirectory == directory).orNull
  override def fileNamed(name: String): scala.reflect.io.AbstractFile = synchronized {
    Option(lookupName(name, directory = false)).getOrElse {
      val f = new scala.reflect.io.VirtualFile(name, path + '/' + name) {
        override def output: java.io.OutputStream = new java.io.OutputStream {
          override def write(b: Int): Unit = bytesWritten += 1
          override def write(b: Array[Byte], off: Int, len: Int): Unit = bytesWritten += len
        }
      }
      entries(name) = f
      f
    }
  }
  override def subdirectoryNamed(name: String): scala.reflect.io.AbstractFile = synchronized {
    Option(lookupName(name, directory = true)).getOrElse {
      val d = new DiscardingDirectory(name, Some(this))
      entries(name) = d
      d
    }
  }
  override def clear(): Unit = entries.clear()
}
