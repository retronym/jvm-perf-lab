package dotty.tools.compilerlab

import io.github.retronym.perflab.jmh.Announce
import java.util.concurrent.TimeUnit

import org.openjdk.jmh.annotations.*

import dotty.tools.dotc.ast.tpd
import dotty.tools.dotc.ast.tpd.TreeOps
import dotty.tools.dotc.core.Contexts.*
import dotty.tools.dotc.core.Phases.picklerPhase
import dotty.tools.dotc.core.Symbols.*
import dotty.tools.dotc.core.TypeOps
import dotty.tools.dotc.core.Types.*

/** `asSeenFrom` of lambda types (method, poly and type lambda infos), as `memberInfo`, `SingleDenotation.derived` and
 *  RefChecks do it for inherited members. The corpus is compiled up to the pickler once; the items are the declarations
 *  of every base class of every class defined in the corpus whose info is (or is bounded by) a lambda type.
 *
 *  - `inherited`: each item's info as seen from the subclass's `this` type, from the base class.
 *  - `unchanged`: each base class's own declarations as seen from its own `this` type (through `TypeOps.asSeenFrom`,
 *    past `membersNeedAsSeenFrom`'s shortcut), those for which this changes nothing (all but references to an outer
 *    class's `this`), so the map must return the type it was given.
 *
 *  Each op maps every item once and returns how many results are `eq` to their input.
 */
@State(Scope.Benchmark)
@BenchmarkMode(Array(Mode.AverageTime))
@OutputTimeUnit(TimeUnit.MICROSECONDS)
@Fork(value = 1, jvmArgsAppend = Array("-Xms4G", "-Xmx4G", "-Xss2M"))
@Warmup(iterations = 10, time = 2)
@Measurement(iterations = 10, time = 2)
class LambdaMapBenchmark:
  @Param(Array("re2s", "scalaz"))
  var corpus: String = compiletime.uninitialized

  /** Extra compiler options, space separated, read by the maps through the run's context. */
  @Param(Array(""))
  var scalacOptions: String = compiletime.uninitialized

  private var ctx: Context = compiletime.uninitialized
  private var infos: Array[Type] = compiletime.uninitialized
  private var pres: Array[Type] = compiletime.uninitialized
  private var owners: Array[Symbol] = compiletime.uninitialized
  private var ownInfos: Array[Type] = compiletime.uninitialized
  private var ownClasses: Array[Symbol] = compiletime.uninitialized

  private def isLambda(tp: Type): Boolean = tp match
    case _: LambdaType => true
    case TypeBounds(lo, hi) => lo.isInstanceOf[LambdaType] || hi.isInstanceOf[LambdaType]
    case _ => false

  @Setup(Level.Trial)
  def setup(): Unit =
    Announce.jvm(s"LambdaMapBenchmark($corpus)")
    val options = List("-Ystop-after:pickler") ::: scalacOptions.split(" ").toList.filter(_.nonEmpty)
    val run = InMemoryCompiler(Corpus.load(corpus), options).compileRun()
    given Context = run.runContext.fresh.setPhase(picklerPhase(using run.runContext))
    ctx = summon[Context]
    val classes = scala.collection.mutable.LinkedHashSet[ClassSymbol]()
    for unit <- run.units do
      unit.tpdTree.foreachSubTree:
        case td: tpd.TypeDef if td.symbol.isClass => classes += td.symbol.asClass
        case _ =>
    val is, ps, os = scala.collection.mutable.ArrayBuffer[AnyRef]()
    val bases = scala.collection.mutable.LinkedHashSet[ClassSymbol]()
    for cls <- classes; bc <- cls.baseClasses.tail do
      bases += bc
      for d <- bc.info.decls.toList if !d.isConstructor && isLambda(d.info) && bc.membersNeedAsSeenFrom(cls.thisType) do
        is += d.info; ps += cls.thisType; os += bc
    infos = is.map(_.asInstanceOf[Type]).toArray
    pres = ps.map(_.asInstanceOf[Type]).toArray
    owners = os.map(_.asInstanceOf[Symbol]).toArray
    val oi, oc = scala.collection.mutable.ArrayBuffer[AnyRef]()
    for bc <- bases; d <- bc.info.decls.toList if !d.isConstructor && isLambda(d.info) do
      oi += d.info; oc += bc
    // Some declarations refer to an outer class's `this` through the class, and change; keep the others
    val keep = oi.indices.filter(i => TypeOps.asSeenFrom(oi(i).asInstanceOf[Type], oc(i).asInstanceOf[Symbol].thisType, oc(i).asInstanceOf[Symbol]) eq oi(i))
    ownInfos = keep.map(oi(_).asInstanceOf[Type]).toArray
    ownClasses = keep.map(oc(_).asInstanceOf[Symbol]).toArray
    val sameInherited = inherited()
    if sys.props.contains("compilerlab.lambdaDiff") then
      var shown = 0
      for i <- infos.indices do
        val ref = new TypeOps.AsSeenFromMap(pres(i), owners(i)) { fuseRebinding = false }
        val a = ref(infos(i))
        val b = TypeOps.asSeenFrom(infos(i), pres(i), owners(i))
        if (a eq infos(i)) != (b eq infos(i)) && shown < 10 then
          shown += 1
          println(s"[lambdaDiff] ${owners(i)} from ${pres(i)}:\n  info: ${infos(i)}\n  two-pass eq=${a eq infos(i)}: $a\n  fused eq=${b eq infos(i)}: $b")
    println(s"\n[compiler-lab] $corpus: ${classes.size} classes, ${bases.size} base classes; inherited: ${infos.length} items, $sameInherited unchanged; own: ${oi.length} items, ${ownInfos.length} unchanged")

  @Benchmark
  def inherited(): Int =
    given Context = ctx
    var same = 0
    var i = 0
    while i < infos.length do
      val tp = infos(i)
      if TypeOps.asSeenFrom(tp, pres(i), owners(i)) eq tp then same += 1
      i += 1
    same

  @Benchmark
  def unchanged(): Int =
    given Context = ctx
    var same = 0
    var i = 0
    while i < ownInfos.length do
      val tp = ownInfos(i)
      val cls = ownClasses(i)
      if TypeOps.asSeenFrom(tp, cls.thisType, cls) eq tp then same += 1
      i += 1
    same
