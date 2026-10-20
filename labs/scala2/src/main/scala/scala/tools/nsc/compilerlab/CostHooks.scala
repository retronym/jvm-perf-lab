package scala.tools.nsc.compilerlab

import java.nio.file.Paths
import java.util.IdentityHashMap

import io.github.retronym.perflab.costs.{CostKind, CostStack}
import io.github.retronym.perflab.costs.CostKind.Phases

import scala.reflect.internal.Phase
import scala.reflect.io.AbstractFile
import scala.tools.nsc.Global

/** The cost per definition (`../def-costs.md`), from the lab: perflab-agent weaves calls to these hooks into the
 *  compiler (`def-costs.hooks`), and they keep a `CostStack` in step with it. Each enter hook is called with the woven
 *  method's receiver and arguments; each exit hook leaves the innermost frame of its kind.
 *
 *  Frames are those of the `-Yprofile-defs` patch (retronym/scala `cost-per-definition`): a phase, a compilation unit
 *  in a phase, typing a definition (`transform` after the typer: erasure's retyping), its Namer completion, a load from
 *  a classfile, an implicit search and a macro expansion, charged to the innermost definition. Only class members and
 *  top-level definitions are tracked; a local definition's frame is transparent, part of its owner's.
 *
 *  The stack is on only between `start` and `finish`, for the `Global` that `start` was given, on its thread.
 */
object CostHooks {
  val Phase = new CostKind("phase", Phases.OWN, false)
  val Unit = new CostKind("unit", Phases.OWN, false)
  val TypedDef = new CostKind("def", Phases.NONE, false)
  val Completion = new CostKind("complete", Phases.NONE, false)
  val Load = new CostKind("load", Phases.NONE, false)
  val Implicit = new CostKind("implicit", Phases.ENCLOSING, true)
  val Macro = new CostKind("macro", Phases.ENCLOSING, true)
  val Transform = new CostKind("transform", Phases.ENCLOSING, false)
  private val kinds = java.util.List.of(Phase, Unit, TypedDef, Completion, Load, Implicit, Macro, Transform)

  private[this] var stack: CostStack = null
  private[this] var global: Global = null
  private[this] var typerId = -1
  // a definition's size in characters, from the range position of its Namer completer's tree
  private[this] val sizes = new IdentityHashMap[AnyRef, Integer]()

  /** Starts a stack for `g`'s next run: a table at `path` (or none, if null) and/or a listener (a `CostListener`'s
   *  class name, or null). */
  def start(g: Global, path: String, listener: String): Unit = {
    global = g
    typerId = -1
    sizes.clear()
    val l = if (listener == null) null else CostStack.listener(listener, getClass.getClassLoader)
    stack = new CostStack(kinds, new Keys(g), if (path == null) null else Paths.get(path), l)
  }

  /** Writes the table; fails if no frame was entered, i.e. the hooks are not woven. */
  def finish(): Unit = {
    val s = stack
    stack = null
    global = null
    if (s != null) {
      s.finished()
      if (s.entered == 0)
        throw new IllegalStateException("--defs: no cost frames; the hooks are not woven: run with -javaagent:<perflab-agent.jar>=spec=<labs/scala2>/def-costs.hooks")
    }
  }

  private def tracked(sym: AnyRef): AnyRef = {
    val s = sym.asInstanceOf[Global#Symbol]
    // not `exists`, which completes the symbol
    if ((s ne global.NoSymbol) && s.owner.isClass) s else null
  }

  private def defKind: CostKind = {
    if (typerId < 0) typerId = global.currentRun.typerPhase.id
    if (global.globalPhase.id > typerId) Transform else TypedDef
  }

  // Profiler's hooks, as NoOpProfiler has them

  def beforePhase(self: AnyRef, phase: AnyRef): Unit = { val s = stack; if (s != null) s.enter(Phase, phase, phase) }
  def afterPhase(self: AnyRef, phase: AnyRef, snap: AnyRef): Unit = { val s = stack; if (s != null) s.exit(Phase) }
  def beforeUnit(self: AnyRef, phase: AnyRef, file: AnyRef): Unit = { val s = stack; if (s != null) s.enter(Unit, file, phase) }
  def afterUnit(self: AnyRef, phase: AnyRef, file: AnyRef): Unit = { val s = stack; if (s != null) s.exit(Unit) }
  def beforeTypedImplDef(self: AnyRef, sym: AnyRef): Unit = { val s = stack; if (s != null) s.enter(defKind, tracked(sym), global.globalPhase) }
  def afterTypedImplDef(self: AnyRef, sym: AnyRef): Unit = { val s = stack; if (s != null) s.exit(defKind) }
  def beforeImplicitSearch(self: AnyRef, pt: AnyRef): Unit = { val s = stack; if (s != null) s.enter(Implicit, null, global.globalPhase) }
  def afterImplicitSearch(self: AnyRef, pt: AnyRef): Unit = { val s = stack; if (s != null) s.exit(Implicit) }
  def beforeMacroExpansion(self: AnyRef, sym: AnyRef): Unit = { val s = stack; if (s != null) s.enter(Macro, null, global.globalPhase) }
  def afterMacroExpansion(self: AnyRef, sym: AnyRef): Unit = { val s = stack; if (s != null) s.exit(Macro) }
  def beforeCompletion(self: AnyRef, root: AnyRef, file: AnyRef): Unit = { val s = stack; if (s != null) s.enter(Load, tracked(root), null) }
  def afterCompletion(self: AnyRef, root: AnyRef, file: AnyRef): Unit = { val s = stack; if (s != null) s.exit(Load) }

  // around Namers#TypeCompleterBase.complete(sym)

  def enterCompletion(self: AnyRef, sym: AnyRef): Unit = {
    val s = stack
    if (s != null) {
      val key = tracked(sym)
      if (key != null) {
        val pos = self.asInstanceOf[scala.tools.nsc.typechecker.Namers#TypeCompleterBase[_]].tree.asInstanceOf[Global#Tree].pos
        if (pos.isRange) {
          val size = Integer.valueOf(pos.end - pos.start)
          sizes.put(key, size)
          val k = key.asInstanceOf[Global#Symbol]
          if (k.isModuleNotMethod) sizes.put(k.moduleClass, size) // completed with the module, not on its own
        }
      }
      s.enter(Completion, key, null)
    }
  }
  def exitCompletion(): Unit = { val s = stack; if (s != null) s.exit(Completion) }

  private final class Keys(global: Global) extends CostStack.Keys {
    def name(key: AnyRef): String = key match {
      case sym: Global#Symbol => if (sym.isModuleClass) sym.fullName + "$" else sym.fullName
      case phase: Phase => phase.name
      case file: AbstractFile => file.path
      case other => String.valueOf(other)
    }
    def label(key: AnyRef): String = key match {
      case sym: Global#Symbol => sym.name.decode
      case _ => name(key)
    }
    def where(key: AnyRef): Array[String] = key match {
      case file: AbstractFile => Array(file.path, "", "")
      case sym: Global#Symbol =>
        val pos = sym.pos
        if (!pos.isDefined) Array("", "", "")
        else {
          val size = sizes.get(sym)
          Array(pos.source.path, pos.line.toString, if (size == null) "" else size.toString)
        }
      case _ => Array("", "", "")
    }
    def phaseName(phase: AnyRef): String = phase.asInstanceOf[Phase].name
  }
}
