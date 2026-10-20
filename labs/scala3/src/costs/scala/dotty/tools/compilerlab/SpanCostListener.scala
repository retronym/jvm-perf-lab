package dotty.tools.compilerlab

import dotty.tools.dotc.profile.{CostFrame, CostListener}
import one.profiler.{Recording, Span}

/** Records the compiler's cost frames as nested async-profiler spans, one per frame (a phase, a unit, a class, a
 *  member, a completion, an implicit search, ...), tagged with a short name the compiler already has as a string:
 *  the phase's name, the source path, the symbol's name, "implicit". A frame's span is recorded only if a sample was
 *  taken during it, and costs no new string.
 *
 *  `jfrconv --spans` rebuilds the path of each sample from the spans enclosing it (`typer > Foo.scala > Foo > bar >
 *  implicit`) and adds it as a leaf, for the flame graph's span panel; the innermost span owns the sample, so the
 *  completion of `b` triggered while typing `a` is `... > a > b`, and grouping by definition charges it to `b`.
 *
 *    -p scalacOptions=-Yprofile-defs-listener:dotty.tools.compilerlab.SpanCostListener
 *
 *  with an async-profiler that has the Span API recording JFR; without a recording, each frame costs a check of a
 *  static field.
 *
 *  `SpanCostListener$All` records every frame's span, sampled or not. Needed for kperf events: async-profiler only
 *  advances a thread's last-sample time for samples it takes on that thread, so with kperf `hasSamplesSince` is always
 *  false and every span would be dropped.
 */
class SpanCostListener(all: Boolean) extends CostListener:
  def this() = this(false)

  def enter(frame: CostFrame): Unit =
    frame.listenerData = Span.start()  // 0 unless a recording is running

  def exit(frame: CostFrame): Unit =
    val start = frame.listenerData
    if start != 0 && (all || Span.hasSamplesSince(start)) then Span.emit(start, Recording.timestamp(), frame.label)

object SpanCostListener:
  /** `-Yprofile-defs-listener:dotty.tools.compilerlab.SpanCostListener$All` */
  final class All extends SpanCostListener(true)
