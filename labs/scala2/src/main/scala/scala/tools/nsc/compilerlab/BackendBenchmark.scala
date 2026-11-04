package scala.tools.nsc.compilerlab

import java.util.concurrent.TimeUnit

import io.github.retronym.perflab.jmh.Announce
import org.openjdk.jmh.annotations._
import org.openjdk.jmh.infra.Blackhole

import scala.collection.mutable
import scala.collection.mutable.ArrayBuffer
import scala.jdk.CollectionConverters._
import scala.tools.asm.{AnnotationVisitor, ClassReader, ClassVisitor, ClassWriter, FieldVisitor, Label, LabelFlags, MethodVisitor, Opcodes, TypePath}
import scala.tools.asm.tree.{ClassNode, JumpInsnNode, LookupSwitchInsnNode, MethodNode, TableSwitchInsnNode}
import scala.tools.nsc.{Global, Phase}

/** The backend without the rest of a compile: one op takes the trees or class nodes of a compiled corpus to classfiles,
 *  to amplify what a change to code generation or classfile writing does.
 *
 *  Setup runs one full compile in the fork, which fills the receiver profiles as a real compile does and leaves the
 *  trees in the `Run`, as `SymbolOpsBenchmark` does for its symbols. The compiler is resident, so these ops run with
 *  the live heap of a finished compile, and `phase` writes to the same in-memory directory as `CompileBenchmark`.
 */
@State(Scope.Benchmark)
@BenchmarkMode(Array(Mode.AverageTime))
@OutputTimeUnit(TimeUnit.MILLISECONDS)
@Fork(value = 1, jvmArgsAppend = Array("-Xms4G", "-Xmx4G", "-Xss2M"))
@Warmup(iterations = 10, time = 5)
@Measurement(iterations = 10, time = 5)
class BackendBenchmark {
  /** The workload. It is this parameter because a campaign's `corpora` set it, which gives each its column.
   *
   *  From trees, the whole path and its first half:
   *
   *  - `phase`: the jvm phase over the trees, with the per-run state reset as a new run would
   *  - `codegen`: trees to `ClassNode`s only, with no local optimisation or writing
   *
   *  From class nodes, `ClassNode` to bytes only:
   *
   *  - `write`: the nodes codegen and post-processing leave, with the flags `serializeClass` uses
   *  - `readFrames`: as `write`, from nodes read back from those classfiles, to show what reading back changes
   *  - `readMaxs`: nodes read back with their frames, which ASM takes as given while it computes the maximum stack and
   *    locals. What the writer would cost if something else supplied perfect frames, for nothing.
   *  - `readNone`: as `readMaxs`, with the maximums given too
   *  - `readCompressedMaxs`: as `readMaxs`, with the frames in compressed form, which `visitFrame` writes directly. For
   *    an expanded frame it turns each internal name into a descriptor and parses that back.
   *  - `branchFreeFrames`, `branchFreeMaxs`: `readFrames` and `readMaxs` of only the methods with no jump, switch or
   *    handler, which need no frames, so the difference is what they pay for frame computation
   *
   *  What a `ClassNode` costs, to bound writing straight to a `ClassWriter` from codegen. Each reads the classfiles,
   *  so with `readFrames` these separate decoding, building the tree, walking it and the writer's own work:
   *
   *  - `decode`: `ClassReader` into visitors that do nothing
   *  - `decodeTree`: `ClassReader` into a new `ClassNode`
   *  - `replay`: `ClassReader` straight into a `ClassWriter`, computing frames as `readFrames` does. The reader flags
   *    the labels of line numbers and local variables as debug-only, and `MethodWriter` starts no basic block for those.
   *  - `replayBlocks`: as `replay` with that flag cleared, as for the labels codegen makes, so each starts a basic block
   *  - `nestedClasses`: `collectNestedClasses` of the nodes `write` uses, which walks them for `setInnerClasses`
   */
  @Param(Array("phase", "codegen", "write", "readFrames", "readMaxs", "readNone", "readCompressedMaxs", "branchFreeFrames", "branchFreeMaxs", "decode", "decodeTree", "replay", "replayBlocks", "nestedClasses"))
  var corpus: String = _

  /** The corpus to compile in setup. */
  @Param(Array("scala"))
  var sources: String = _

  /** As `CompileBenchmark.jdkHome`. */
  @Param(Array(""))
  var jdkHome: String = _

  private var op: Blackhole => Unit = _

  @Setup(Level.Trial)
  def setup(): Unit = {
    Announce.jvm(s"BackendBenchmark($corpus, $sources)")
    CompileBenchmark.useJdk(jdkHome)
    op = BackendOps.compile(sources).workload(corpus)
  }

  @Benchmark
  def run(bh: Blackhole): Unit = op(bh)
}

object BackendOps {
  /** Compiles `sources` and prepares the ops over what the compile left. */
  def compile(sources: String): BackendOps = {
    val compiler = new InMemoryCompiler(Corpus.load(sources), resident = true)
    val ops = new BackendOps(compiler)
    println(s"\n[compiler-lab] $sources: ${ops.summary}")
    ops
  }
}

/** The workloads, over the units of a finished `Run` of `compiler`'s resident `Global`. */
final class BackendOps(compiler: InMemoryCompiler) {
  val global: Global = compiler.residentGlobal
  import global._
  import genBCode.{bTypes, codeGen, postProcessor, postProcessorFrontendAccess}

  /** The pickles of the corpus, as the jvm phase started: it removes each as it writes the `ScalaSignature`. */
  private var pickles: Map[Symbol, scala.reflect.internal.pickling.PickleBuffer] = _

  /** A run clears these at its end, but the backend reads them, so a rerun needs them kept. */
  private def keepFrontendCaches(): Unit = {
    def field(c: Class[_]): java.lang.reflect.Field =
      c.getDeclaredFields.find(_.getName.endsWith("originalOwnerMap")).getOrElse(field(c.getSuperclass))
    val originalOwners = field(global.getClass)
    originalOwners.setAccessible(true)
    perRunCaches.unrecordCache(originalOwners.get(global).asInstanceOf[mutable.AnyRefMap[Symbol, Symbol]])
    perRunCaches.unrecordCache(erasure.requiredDirectInterfaces)
  }

  locally {
    keepFrontendCaches()
    val run = new Run {
      override def informUnitStarting(phase: Phase, unit: CompilationUnit): Unit =
        if (pickles == null && phase.name == genBCode.phaseName) pickles = symData.toMap
    }
    run.compileFiles(compiler.corpus.files)
    if (reporter.hasErrors) sys.error(s"${compiler.corpus.name} failed to compile")
  }

  private val jvm = currentRun.jvmPhase
  private val frames = ClassWriter.COMPUTE_MAXS | ClassWriter.COMPUTE_FRAMES

  private def startRun(): Unit = currentRun.symData ++= pickles

  /** Done by the end of a real run; without it a rerun would find the `BType`s of the previous one. `icode` is the sbt
   *  shim's set, which codegen adds to and nothing else reads.
   */
  private def endRun(): Unit = {
    currentRun.units.foreach(_.icode.clear())
    perRunCaches.clearAll()
  }

  def phase(bh: Blackhole): Unit = {
    startRun()
    enteringPhase(jvm)(jvm.run())
    endRun()
    bh.consume(jvm)
  }

  /** What `BCodePhase.initialize` does, less the handler that codegen's output goes to, which this leaves out. */
  private def initBackend(): Unit = {
    startRun()
    scalaPrimitives.init()
    bTypes.initialize()
    codeGen.initialize()
    postProcessorFrontendAccess.initialize()
    postProcessor.initialize(global)
  }

  /** As `CodeGen.genUnit`, with each class given to `f` in place of the handler. */
  private def genClasses(f: (ClassNode, Boolean) => Unit): Unit = enteringPhase(jvm) {
    def gen(unit: CompilationUnit, tree: Tree): Unit = tree match {
      case EmptyTree =>
      case PackageDef(_, stats) => stats.foreach(gen(unit, _))
      case cd: ClassDef =>
        f(codeGen.genClass(cd, unit), false)
        val sym = cd.symbol
        if (bTypes.isTopLevelModuleClass(sym) && sym.companionClass == NoSymbol)
          f(codeGen.genMirrorClass(sym, unit), true)
      case x => throw new MatchError(x)
    }
    currentRun.units.filterNot(_.isJava).foreach { unit => // as `GlobalPhase.cancelled`
      currentRun.currentUnit = unit
      gen(unit, unit.body)
    }
  }

  def codegen(bh: Blackhole): Unit = {
    initBackend()
    genClasses((node, _) => bh.consume(node))
    endRun()
  }

  /** The nodes as `PostProcessor.sendToDisk` gives them to `serializeClass`. The backend's per-run state stays, as
   *  writing a class looks up `BType`s for its frames.
   */
  private lazy val nodes: Array[ClassNode] = {
    initBackend()
    val out = new ArrayBuffer[ClassNode]
    genClasses { (node, isArtifact) =>
      if (!isArtifact) {
        postProcessor.localOptimizations(node)
        val lambdas = postProcessor.backendUtils.indyLambdaBodyMethods(node.name)
        if (lambdas.nonEmpty) postProcessor.backendUtils.addLambdaDeserialize(node, lambdas)
      }
      postProcessor.setInnerClasses(node)
      out += node
    }
    out.toArray
  }

  private lazy val classfiles: Array[Array[Byte]] = nodes.map(serialize(_, frames))

  private def serialize(node: ClassNode, flags: Int): Array[Byte] = {
    val cw = new postProcessor.ClassWriterWithBTypeLub(flags)
    node.accept(cw)
    cw.toByteArray
  }

  private def read(readerFlags: Int)(keep: MethodNode => Boolean = _ => true): Array[ClassNode] = classfiles.map { bytes =>
    val node = new ClassNode()
    new ClassReader(bytes).accept(node, readerFlags)
    node.methods.removeIf(m => !keep(m))
    node
  }

  private def isBranchFree(m: MethodNode): Boolean =
    m.tryCatchBlocks.isEmpty && !m.instructions.iterator.asScala.exists {
      case _: JumpInsnNode | _: LookupSwitchInsnNode | _: TableSwitchInsnNode => true
      case _ => false
    }

  private def sizes(name: String, nodes: Array[ClassNode], flags: Int): Unit = {
    val bytes = nodes.iterator.map(serialize(_, flags).length.toLong).sum
    val insns = nodes.iterator.flatMap(_.methods.asScala).map(_.instructions.size.toLong).sum
    println(s"[compiler-lab] $name: ${nodes.length} classes, ${nodes.iterator.map(_.methods.size).sum} methods, $insns insns, $bytes bytes")
  }

  private def writing(name: String, nodes: Array[ClassNode], flags: Int): Blackhole => Unit = {
    sizes(name, nodes, flags)
    bh => {
      var i = 0
      while (i < nodes.length) {
        bh.consume(serialize(nodes(i), flags))
        i += 1
      }
    }
  }

  /** Takes everything a `ClassReader` offers and does nothing with it. */
  private object Discard extends ClassVisitor(Opcodes.ASM9) {
    private object annotation extends AnnotationVisitor(Opcodes.ASM9) {
      override def visitAnnotation(name: String, desc: String): AnnotationVisitor = this
      override def visitArray(name: String): AnnotationVisitor = this
    }
    private object field extends FieldVisitor(Opcodes.ASM9) {
      override def visitAnnotation(desc: String, visible: Boolean): AnnotationVisitor = annotation
      override def visitTypeAnnotation(ref: Int, path: TypePath, desc: String, visible: Boolean): AnnotationVisitor = annotation
    }
    private object method extends MethodVisitor(Opcodes.ASM9) {
      override def visitAnnotationDefault(): AnnotationVisitor = annotation
      override def visitAnnotation(desc: String, visible: Boolean): AnnotationVisitor = annotation
      override def visitTypeAnnotation(ref: Int, path: TypePath, desc: String, visible: Boolean): AnnotationVisitor = annotation
      override def visitParameterAnnotation(param: Int, desc: String, visible: Boolean): AnnotationVisitor = annotation
      override def visitInsnAnnotation(ref: Int, path: TypePath, desc: String, visible: Boolean): AnnotationVisitor = annotation
      override def visitTryCatchAnnotation(ref: Int, path: TypePath, desc: String, visible: Boolean): AnnotationVisitor = annotation
    }
    override def visitAnnotation(desc: String, visible: Boolean): AnnotationVisitor = annotation
    override def visitTypeAnnotation(ref: Int, path: TypePath, desc: String, visible: Boolean): AnnotationVisitor = annotation
    override def visitField(access: Int, name: String, desc: String, signature: String, value: Object): FieldVisitor = field
    override def visitMethod(access: Int, name: String, desc: String, signature: String, exceptions: Array[String]): MethodVisitor = method
  }

  private def overClassfiles(f: Array[Byte] => AnyRef): Blackhole => Unit = {
    val files = classfiles
    bh => {
      var i = 0
      while (i < files.length) {
        bh.consume(f(files(i)))
        i += 1
      }
    }
  }

  private def replayed(bytes: Array[Byte]): Array[Byte] = {
    val cw = new postProcessor.ClassWriterWithBTypeLub(frames)
    new ClassReader(bytes).accept(cw, ClassReader.SKIP_FRAMES)
    cw.toByteArray
  }

  private def replayedWithBlocks(bytes: Array[Byte]): Array[Byte] = {
    val cw = new postProcessor.ClassWriterWithBTypeLub(frames)
    val clearing = new ClassVisitor(Opcodes.ASM9, cw) {
      override def visitMethod(access: Int, name: String, desc: String, signature: String, exceptions: Array[String]): MethodVisitor =
        new MethodVisitor(Opcodes.ASM9, super.visitMethod(access, name, desc, signature, exceptions)) {
          override def visitLabel(label: Label): Unit = {
            LabelFlags.clearDebugOnly(label)
            super.visitLabel(label)
          }
        }
    }
    new ClassReader(bytes).accept(clearing, ClassReader.SKIP_FRAMES)
    cw.toByteArray
  }

  private def checkReplay(name: String, f: Array[Byte] => Array[Byte]): Unit = {
    val same = classfiles.count(bytes => java.util.Arrays.equals(bytes, f(bytes)))
    println(s"[compiler-lab] $name: ${classfiles.length} classes, ${classfiles.iterator.map(f(_).length.toLong).sum} bytes against ${classfiles.iterator.map(_.length.toLong).sum}, $same byte-identical")
  }

  def workload(name: String): Blackhole => Unit = name match {
    case "phase" => checkRerun(); phase
    case "codegen" => codegen
    case "write" => writing(name, nodes, frames)
    case "readFrames" => writing(name, read(ClassReader.SKIP_FRAMES)(), frames)
    case "readMaxs" => writing(name, read(ClassReader.EXPAND_FRAMES)(), ClassWriter.COMPUTE_MAXS)
    case "readNone" => writing(name, read(ClassReader.EXPAND_FRAMES)(), 0)
    case "readCompressedMaxs" => writing(name, read(0)(), ClassWriter.COMPUTE_MAXS)
    case "branchFreeFrames" => writing(name, read(ClassReader.SKIP_FRAMES)(isBranchFree), frames)
    case "branchFreeMaxs" => writing(name, read(ClassReader.EXPAND_FRAMES)(isBranchFree), ClassWriter.COMPUTE_MAXS)
    case "decode" => overClassfiles { bytes => new ClassReader(bytes).accept(Discard, ClassReader.SKIP_FRAMES); bytes }
    case "decodeTree" => overClassfiles { bytes => val node = new ClassNode(); new ClassReader(bytes).accept(node, ClassReader.SKIP_FRAMES); node }
    case "replay" => checkReplay(name, replayed); overClassfiles(replayed)
    case "replayBlocks" => checkReplay(name, replayedWithBlocks); overClassfiles(replayedWithBlocks)
    case "nestedClasses" =>
      val ns = nodes
      bh => {
        var i = 0
        while (i < ns.length) {
          bh.consume(postProcessor.backendUtils.collectNestedClasses(ns(i)))
          i += 1
        }
      }
    case other => sys.error(s"corpus=$other: expected a workload")
  }

  private def output: Map[String, Array[Byte]] = {
    def walk(f: scala.reflect.io.AbstractFile): Iterator[(String, Array[Byte])] =
      if (f.isDirectory) f.iterator.flatMap(walk) else Iterator(f.path -> f.toByteArray)
    walk(compiler.output).toMap
  }

  /** `phase` is only worth measuring if it does what the first compile did, so compare the classfiles it writes. */
  private def checkRerun(): Unit = {
    def differ(a: Map[String, Array[Byte]], b: Map[String, Array[Byte]]) =
      (a.keySet ++ b.keySet).toList.sorted.filter(k => !(a.contains(k) && b.contains(k) && java.util.Arrays.equals(a(k), b(k))))
    val noBlackhole = new Blackhole("Today's password is swordfish. I understand instantiating Blackholes directly is dangerous.")
    val first = output
    phase(noBlackhole)
    val second = output
    phase(noBlackhole)
    val third = output
    val vsCompile = differ(first, second)
    val vsRerun = differ(second, third)
    println(s"[compiler-lab] rerun of the jvm phase: ${first.size} files, ${vsCompile.size} differ from the compile's (${vsCompile.take(5).mkString(", ")}), ${vsRerun.size} differ between reruns (${vsRerun.take(5).mkString(", ")})")
    noBlackhole.evaporate("Yes, I am Stephen Hawking, and know a thing or two about black holes.")
  }

  def summary: String = {
    val units = currentRun.units.size
    s"$units units, jvm phase $jvm"
  }
}

/** The workloads outside JMH, printing each pass's time.
 *
 *  `BackendLoop [sources] [passes] [workloads...]`
 */
object BackendLoop {
  def main(args: Array[String]): Unit = {
    val sources = args.headOption.getOrElse("scalap")
    val n = args.lift(1).fold(5)(_.toInt)
    val all = List("phase", "codegen", "write", "readFrames", "readMaxs", "readNone", "readCompressedMaxs", "branchFreeFrames", "branchFreeMaxs", "decode", "decodeTree", "replay", "replayBlocks", "nestedClasses")
    val names = if (args.length > 2) args.drop(2).toList else all
    val ops = BackendOps.compile(sources)
    val bh = new Blackhole("Today's password is swordfish. I understand instantiating Blackholes directly is dangerous.")
    for (name <- names) {
      val op = ops.workload(name)
      val times = for (_ <- 1 to n) yield {
        val t0 = System.nanoTime
        op(bh)
        (System.nanoTime - t0) / 1e6
      }
      println(f"$name%-18s ${times.map(t => f"$t%8.1f").mkString(" ")} ms")
    }
    bh.evaporate("Yes, I am Stephen Hawking, and know a thing or two about black holes.")
  }
}
