package scala.tools.nsc.compilerlab

import java.util.concurrent.TimeUnit

import io.github.retronym.perflab.jmh.Announce
import org.openjdk.jmh.annotations._
import org.openjdk.jmh.infra.Blackhole

import scala.collection.mutable.ArrayBuffer
import scala.tools.nsc.Global

/** The compiler's symbol and type operations, without the rest of a compile: one op applies one workload to the classes
 *  of a compiled corpus, to amplify what a change to those operations does.
 *
 *  Setup runs one full compile in the fork, and the op works on the symbols it left. That is what keeps this honest
 *  about dispatch: the receiver profiles of `Symbol.info`, `TypeRef.mapOver` and so on are filled by a real compile, so
 *  their call sites are as megamorphic as they are in one. On a benchmark that only called these from a clean start,
 *  C2 would inline a receiver or two and the cost of a vtable stub would not show.
 *
 *  An op stays in one phase for a whole pass over the classes: flipping per symbol would measure `rawInfo`'s walk of the
 *  info history. The first op of a fork forces the infos it needs, so warmup pays for those.
 */
@State(Scope.Benchmark)
@BenchmarkMode(Array(Mode.AverageTime))
@OutputTimeUnit(TimeUnit.MILLISECONDS)
@Fork(value = 1, jvmArgsAppend = Array("-Xms4G", "-Xmx4G", "-Xss2M"))
@Warmup(iterations = 5, time = 10)
@Measurement(iterations = 5, time = 10)
class SymbolOpsBenchmark {
  /** The workload. It is this parameter because a campaign's `corpora` set it, which gives each its column.
   *
   *  - `findMember`: `members`, `member` and `nonPrivateMember` on each class's type, after pickler
   *  - `overridingPairs`: the pairs of each class and their member types, as RefChecks walks them
   *  - `subst`: `memberInfo` of inherited members (`AsSeenFromMap`), `instantiateTypeParams` and `substSym` (`SubstMap`)
   *  - `erasure`: member lookups after erasure, and the erasure map and other generic `TypeMap`s before it, which take
   *    the slow path of a dispatch that favours the maps above
   *  - `subtype`: `<:<` and `=:=` of each class's type against each type in its base type sequence (true) and against
   *    the next class's type (mostly false): the subtype checker on its own
   *  - `all`: each of those in turn, weighted by repetition, for one number per commit of a branch
   *  - `unweighted`: one pass of each, so `findMember` and `overridingPairs` take most of the op
   */
  @Param(Array("findMember", "overridingPairs", "subst", "erasure", "subtype", "all", "unweighted"))
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
    Announce.jvm(s"SymbolOpsBenchmark($corpus, $sources)")
    CompileBenchmark.useJdk(jdkHome)
    val compiler = new InMemoryCompiler(Corpus.load(sources), resident = true)
    compiler.compile()
    val ops = new SymbolOps(compiler.residentGlobal)
    println(s"\n[compiler-lab] $sources: ${ops.summary}")
    ops.dumpBaseTypeSeqs()
    op = corpus match {
      case "findMember" => ops.findMember
      case "overridingPairs" => ops.overridingPairs
      case "subst" => ops.subst
      case "erasure" => ops.erasedOps
      case "subtype" => ops.subtype
      case "unweighted" => bh => {
        ops.findMember(bh)
        ops.overridingPairs(bh)
        ops.subst(bh)
        ops.erasedOps(bh)
      }
      case "all" => bh => {
        ops.findMember(bh)
        ops.overridingPairs(bh)
        // repeated so that on the scala corpus each takes a similar share of the op: one pass of `subst` is under 10%
        // of a pass of `findMember` there, and a change to it would not show otherwise
        for (_ <- 1 to 16) ops.subst(bh)
        for (_ <- 1 to 5) ops.erasedOps(bh)
      }
      case other => sys.error(s"corpus=$other: expected a workload")
    }
  }

  @Benchmark
  def run(bh: Blackhole): Unit = op(bh)
}

/** The workloads, over the classes a finished `Run` of `global` knows, with lists of what to apply them to. */
final class SymbolOps(val global: Global) {
  import global._

  private val classes: Array[Symbol] = exitingPickler {
    val out = new ArrayBuffer[Symbol]
    val seen = new scala.collection.mutable.HashSet[Symbol] // the root package has itself as a member, `_root_`
    def walk(owner: Symbol): Unit = owner.info.decls.foreach { m =>
      val c = if (m.isModule) m.moduleClass else if (m.isClass) m else NoSymbol
      // what the compile loaded: going further would load the rest of the classpath
      if (c != NoSymbol && c.rawInfo.isComplete && seen.add(c)) {
        if (!c.isPackageClass) out += c
        walk(c)
      }
    }
    walk(rootMirror.RootClass)
    out.toArray
  }

  private def isOrdinaryTerm(m: Symbol) = m.isTerm && !m.isConstructor && !m.isModule

  /** Names to look up per class: some of its own, one inherited from everything and one found nowhere. */
  private val names: Array[List[Name]] = exitingPickler {
    val absent = TermName("symbolOpsAbsent")
    classes.map(c => absent :: nme.toString_ :: c.info.decls.toList.take(6).map(_.name))
  }

  private val own: Array[List[Symbol]] = exitingPickler(classes.map(c => c.info.decls.toList.filter(isOrdinaryTerm).take(8)))

  private val inherited: Array[List[Symbol]] = exitingPickler {
    classes.map { c =>
      val bases = c.info.baseClasses.drop(1).filter(b => b != definitions.ObjectClass && b != definitions.AnyClass).take(4)
      bases.flatMap(_.info.decls.toList.filter(isOrdinaryTerm).take(4))
    }
  }

  private val typeArgs: Array[List[Type]] = exitingPickler(classes.map(_.typeParams.map(_ => definitions.AnyTpe)))
  private val clones: Array[List[Symbol]] = exitingPickler(classes.map(c => cloneSymbols(c.typeParams)))

  /** Pairs for `subtype`: each class's type with each of its base types, then with the next class's type. */
  private val subtypePairs: Array[(Type, Type)] = exitingPickler {
    val out = new ArrayBuffer[(Type, Type)]
    for (i <- classes.indices) {
      val tp = classes(i).tpe
      // `apply`, not `toList`: `toList` returns lazy elements (the intersection of several instantiations of one base
      // class, e.g. `SetLike[A, HashSet[A]] with SetLike[A, Set[A]]`) unresolved if nothing has asked for them yet, so
      // the pairs would depend on what the compile happened to force (retronym/scala integration f207 changed that).
      val bts = tp.baseTypeSeq
      for (j <- 0 until bts.length) out += ((tp, bts(j)))
      out += ((tp, classes((i + 1) % classes.length).tpe))
    }
    out.toArray
  }

  /** `-Dcompilerlab.subtype.dump=HashSet,BitSet`: each named class's base type sequence, at the op's phase. */
  def dumpBaseTypeSeqs(): Unit = sys.props.get("compilerlab.subtype.dump").foreach { names =>
    val wanted = names.split(',').toSet
    exitingPickler {
      for (c <- classes if wanted(c.name.toString)) {
        val bts = c.tpe.baseTypeSeq
        println(s"[bts] ${c.fullName} (${bts.length}):")
        bts.toList.foreach(t => println(s"[bts]   ${t.getClass.getSimpleName}  $t"))
      }
    }
  }

  def summary: String =
    s"${classes.length} classes, ${names.iterator.map(_.size).sum} lookups, ${own.iterator.map(_.size).sum} own and " +
      s"${inherited.iterator.map(_.size).sum} inherited members, ${classes.count(c => exitingPickler(c.typeParams.nonEmpty))} generic classes, ${subtypePairs.length} subtype pairs"

  private object idMap extends TypeMap {
    def apply(tp: Type): Type = mapOver(tp)
  }

  private object dealiasMap extends TypeMap {
    def apply(tp: Type): Type = mapOver(tp.dealias)
  }

  val subtype: Blackhole => Unit = bh => exitingPickler {
    val ps = subtypePairs
    var i = 0
    while (i < ps.length) {
      val p = ps(i)
      bh.consume(p._1 <:< p._2)
      bh.consume(p._2 <:< p._1)
      bh.consume(p._1 =:= p._2)
      i += 1
    }
  }

  val findMember: Blackhole => Unit = bh => exitingPickler {
    for (i <- classes.indices) {
      val c = classes(i)
      val tp = c.tpe
      bh.consume(c.typeOfThis)
      bh.consume(tp.members)
      for (name <- names(i)) {
        bh.consume(tp.member(name))
        bh.consume(tp.nonPrivateMember(name))
      }
    }
  }

  val overridingPairs: Blackhole => Unit = bh => exitingPickler {
    for (c <- classes) {
      val cursor = new global.overridingPairs.Cursor(c)
      while (cursor.hasNext) {
        val pair = cursor.currentPair
        bh.consume(pair.lowType)
        bh.consume(pair.highType)
        cursor.next()
      }
    }
  }

  val subst: Blackhole => Unit = bh => exitingPickler {
    for (i <- classes.indices) {
      val c = classes(i)
      val tp = c.tpe
      for (m <- inherited(i)) bh.consume(tp.memberInfo(m))
      val tparams = c.typeParams
      for (m <- own(i)) {
        val info = m.info
        if (tparams.nonEmpty) {
          bh.consume(info.instantiateTypeParams(tparams, typeArgs(i)))
          bh.consume(info.substSym(tparams, clones(i)))
        }
        val mparams = info.typeParams
        if (mparams.nonEmpty) bh.consume(info.instantiateTypeParams(mparams, mparams.map(_ => definitions.AnyTpe)))
      }
    }
  }

  val erasedOps: Blackhole => Unit = bh => {
    exitingErasure {
      for (i <- classes.indices) {
        val c = classes(i)
        val tp = c.tpe
        bh.consume(tp.members)
        for (name <- names(i)) bh.consume(tp.member(name))
        for (m <- inherited(i)) bh.consume(tp.memberInfo(m))
      }
    }
    enteringErasure {
      for (i <- classes.indices; m <- own(i)) {
        val info = m.info
        bh.consume(erasure.erasure(m)(info))
        bh.consume(idMap(info))
        bh.consume(dealiasMap(info))
      }
    }
  }
}
