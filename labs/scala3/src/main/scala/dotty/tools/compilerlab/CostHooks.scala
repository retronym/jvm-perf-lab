package dotty.tools.compilerlab

import java.nio.file.{Files, Paths}
import java.util.IdentityHashMap

import io.github.retronym.perflab.costs.{CostKind, CostStack}
import io.github.retronym.perflab.costs.CostKind.Phases

import dotty.tools.dotc.CompilationUnit
import dotty.tools.dotc.ast.{Trees, tpd}
import dotty.tools.dotc.core.Contexts.*
import dotty.tools.dotc.core.Flags
import dotty.tools.dotc.core.Phases.Phase
import dotty.tools.dotc.core.Symbols.*
import dotty.tools.dotc.core.SymDenotations.SymDenotation
import dotty.tools.dotc.typer.Namer

/** The cost per definition (`../def-costs.md`), from the lab: perflab-agent weaves calls to these hooks into the
 *  compiler (`def-costs.hooks`), and they keep a `CostStack` in step with it. Each enter hook is called with the woven
 *  method's receiver and arguments.
 *
 *  Frames are those of the `-Yprofile-defs` patch (retronym/scala3 `cost-per-definition`): a phase, a compilation
 *  unit in a phase, typing a definition (`retype` after the typer and in rechecks), its Namer completion, a load from a
 *  classfile or TASTy, a definition's subtree in a MegaPhase or MacroTransform (`transform`), the growth of a
 *  hash-consing table (`rehash`), and implicit searches and inline expansions, charged to the innermost definition.
 *  Only class members and top-level definitions are tracked; other frames are transparent, part of what encloses them.
 *
 *  `arm` turns it on for the next compilations; each run makes its stack when it makes its profiler (`Profiler.apply`,
 *  with the run's context) and writes its table when the profiler finishes, as the patch does.
 */
object CostHooks:
  val Phase = CostKind("phase", Phases.OWN, false)
  val Unit = CostKind("unit", Phases.OWN, false)
  val TypedDef = CostKind("def", Phases.NONE, false)
  val Retype = CostKind("retype", Phases.ENCLOSING, false)
  val Transform = CostKind("transform", Phases.ENCLOSING, false)
  val Completion = CostKind("complete", Phases.NONE, false)
  val Load = CostKind("load", Phases.NONE, false)
  val Implicit = CostKind("implicit", Phases.ENCLOSING, true)
  val Inline = CostKind("inline", Phases.ENCLOSING, true)
  val Rehash = CostKind("rehash", Phases.ENCLOSING, false)
  private val kinds = java.util.List.of(Phase, Unit, TypedDef, Retype, Transform, Completion, Load, Implicit, Inline, Rehash)

  // the hash-consing tables, by class: a constant key and label
  private val uniques = Map(
    "dotty.tools.dotc.core.Uniques" -> "Uniques",
    "dotty.tools.dotc.core.Uniques$NamedTypeUniques" -> "NamedTypeUniques",
    "dotty.tools.dotc.core.Uniques$AppliedUniques" -> "AppliedUniques")

  private var path: String | Null = null
  private var listener: String | Null = null
  private var armed = false
  private var runs = 0
  private var entered = 0L
  private var stack: CostStack | Null = null
  // a definition's size in characters, the largest span of the trees it was typed or transformed from
  private val sizes = IdentityHashMap[AnyRef, Integer]()

  /** On for the compilations until `disarm`: a table at `path` (or none, if null) and/or a listener (a
   *  `CostListener`'s class name, or null). */
  def arm(path: String | Null, listener: String | Null): Unit =
    this.path = path
    this.listener = listener
    armed = true
    runs = 0
    entered = 0

  /** Off; fails if no frame was entered, i.e. the hooks are not woven. */
  def disarm(): Unit =
    armed = false
    stack = null
    if entered == 0 then
      throw IllegalStateException("--defs: no cost frames; the hooks are not woven: run with -javaagent:<perflab-agent.jar>=spec=<labs/scala3>/def-costs.hooks")

  // around Profiler.apply()(using Context) and NoOpProfiler.finished(): a run's stack

  def profilerCreated(self: AnyRef, c: AnyRef): Unit =
    if armed then
      given Context = c.asInstanceOf[Context]
      sizes.clear()
      runs += 1
      // a later run (a unit suspended for a macro) writes its own table beside the first, unless the target is not a
      // regular file (e.g. /dev/null)
      val table = path match
        case null => null
        case p: String =>
          val regular = !Files.exists(Paths.get(p)) || Files.isRegularFile(Paths.get(p))
          Paths.get(if runs > 1 && regular then s"$p.${runs - 1}" else p)
      val l = listener match
        case null => null
        case name: String => CostStack.listener(name, getClass.getClassLoader)
      stack = CostStack(kinds, Keys(ctx), table, l)

  def profilerFinished(self: AnyRef): Unit =
    val s = stack
    if s != null then
      stack = null
      entered += s.entered
      s.finished()

  private def tracked(sym: Symbol)(using Context): Symbol | Null =
    if !sym.exists then null
    else
      val owner = sym.maybeOwner
      if owner.exists && (owner.isClass || owner.is(Flags.Package)) then sym else null

  private def noteSize(sym: Symbol | Null, tree: AnyRef): Unit =
    if sym != null then
      val span = tree.asInstanceOf[Trees.Tree[?]].span
      if span.exists then
        val size = span.end - span.start
        val known = sizes.get(sym)
        if known == null || known.intValue < size then sizes.put(sym, Integer.valueOf(size))

  private def enterDef(tree: AnyRef, sym: AnyRef, c: AnyRef): Unit =
    val s = stack
    if s != null then
      given Context = c.asInstanceOf[Context]
      val key = tracked(sym.asInstanceOf[Symbol])
      noteSize(key, tree)
      s.enter(if ctx.phase.isTyper then TypedDef else Retype, key, null)

  /** Leaves the innermost frame: the exit of every hook around a method */
  def exit(): Unit =
    val s = stack
    if s != null then s.exit()

  // Profiler's own hooks: phases, units, implicit searches, inline expansions

  def beforePhase(self: AnyRef, phase: AnyRef): Unit = { val s = stack; if s != null then s.enter(Phase, phase, phase) }
  def afterPhase(self: AnyRef, event: AnyRef, phase: AnyRef, snap: AnyRef): Unit = { val s = stack; if s != null then s.exit(Phase) }
  def beforeUnit(self: AnyRef, phase: AnyRef, unit: AnyRef): Unit = { val s = stack; if s != null then s.enter(Unit, unit, phase) }
  def afterUnit(self: AnyRef, event: AnyRef): Unit = { val s = stack; if s != null then s.exit(Unit) }
  def beforeImplicitSearch(self: AnyRef, pt: AnyRef): Unit = { val s = stack; if s != null then s.enter(Implicit, null, null) }
  def afterImplicitSearch(self: AnyRef, event: AnyRef): Unit = { val s = stack; if s != null then s.exit(Implicit) }
  def beforeInlineCall(self: AnyRef, sym: AnyRef): Unit = { val s = stack; if s != null then s.enter(Inline, null, null) }
  def afterInlineCall(self: AnyRef, event: AnyRef): Unit = { val s = stack; if s != null then s.exit(Inline) }

  // around Typer.typed{Val,Def,Type,Class}Def(tree, sym)(using Context), and Recheck's recheckDef, recheckTypeDef

  def typedDef(self: AnyRef, tree: AnyRef, sym: AnyRef, c: AnyRef): Unit = enterDef(tree, sym, c)

  // around Recheck's recheckClassDef(tree, impl, sym)(using Context)
  def recheckClassDef(self: AnyRef, tree: AnyRef, impl: AnyRef, sym: AnyRef, c: AnyRef): Unit = enterDef(tree, sym, c)

  // around Namer.Completer.complete(denot)(using Context): completing a symbol from source

  def complete(self: AnyRef, denot: AnyRef, c: AnyRef): Unit =
    val s = stack
    if s != null then
      given Context = c.asInstanceOf[Context]
      val key = tracked(denot.asInstanceOf[SymDenotation].symbol)
      noteSize(key, self.asInstanceOf[Namer#Completer].original)
      s.enter(Completion, key, null)

  // around SymbolLoader.complete(root)(using Context): loading from a classfile or TASTy

  def load(self: AnyRef, root: AnyRef, c: AnyRef): Unit =
    val s = stack
    if s != null then
      given Context = c.asInstanceOf[Context]
      s.enter(Load, tracked(root.asInstanceOf[SymDenotation].symbol), null)

  // around MegaPhase.transformTree(tree, start)(using Context), MacroTransform's and Inlining's transform(tree)(using
  // Context): a member of a class, in a transform

  def transformTree(self: AnyRef, tree: AnyRef, start: Int, c: AnyRef): Unit = transform(self, tree, c)

  def transform(self: AnyRef, tree: AnyRef, c: AnyRef): Unit =
    val s = stack
    if s != null then
      given Context = c.asInstanceOf[Context]
      val key = tree match
        case t @ (_: Trees.ValDef[?] | _: Trees.DefDef[?] | _: Trees.TypeDef[?]) if ctx.owner.isClass => tracked(t.asInstanceOf[tpd.Tree].symbol)
        case _ => null
      noteSize(key, tree)
      s.enter(Transform, key, null)

  // around WeakHashSet.resize(): the growth of a hash-consing table

  def resize(self: AnyRef): Unit =
    val s = stack
    if s != null then s.enter(Rehash, uniques.getOrElse(self.getClass.getName, null), null)

  private final class Keys(ictx: Context) extends CostStack.Keys:
    given Context = ictx

    def name(key: AnyRef): String = key match
      case sym: Symbol => sym.fullName.toString
      case _ => label(key)

    def label(key: AnyRef): String = key match
      case sym: Symbol => sym.name.toString
      case phase: Phase => phase.phaseName
      case unit: CompilationUnit => unit.source.path
      case other => String.valueOf(other)

    def where(key: AnyRef): Array[String] = key match
      case unit: CompilationUnit => Array(unit.source.path, "", "")
      case sym: Symbol if sym.exists && sym.span.exists =>
        val pos = sym.sourcePos
        val size = sizes.get(sym)
        if pos.exists then Array(pos.source.path, (pos.line + 1).toString, if size == null then "" else size.toString)
        else Array("", "", "")
      case _ => Array("", "", "")

    def phaseName(phase: AnyRef): String = phase.asInstanceOf[Phase].phaseName
