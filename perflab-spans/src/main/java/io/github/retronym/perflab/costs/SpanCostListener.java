package io.github.retronym.perflab.costs;

import one.profiler.Recording;
import one.profiler.Span;

/**
 * Records a cost stack's frames as nested async-profiler spans, one per frame, tagged with the frame's short label (a
 * phase's name, a source path, a symbol's name, "implicit"). A frame's span is recorded (and its label made) only if
 * a sample was taken during it.
 *
 * `jfrconv --spans` rebuilds the path of each sample from the spans enclosing it (`typer > Foo.scala > Foo > bar >
 * implicit`) and adds it as a leaf, for the flame graph's span panel; the innermost span owns the sample, so a
 * completion of `b` triggered while typing `a` is `... > a > b`, and grouping by definition charges it to `b`.
 *
 * Without a recording, each frame costs a check of a static field. {@link All} records every frame's span, sampled or
 * not: with kperf events async-profiler does not advance the thread's last-sample time, so `hasSamplesSince` is always
 * false and every span would be dropped.
 */
public class SpanCostListener implements CostListener {
    private final boolean all;

    public SpanCostListener() { this(false); }

    protected SpanCostListener(boolean all) { this.all = all; }

    @Override
    public void enter(CostStack.Frame frame) {
        frame.listenerData = Span.start(); // 0 unless a recording is running
    }

    @Override
    public void exit(CostStack.Frame frame) {
        long start = frame.listenerData;
        if (start != 0 && (all || Span.hasSamplesSince(start))) Span.emit(start, Recording.timestamp(), frame.label());
    }

    /** Every frame's span, for kperf events */
    public static final class All extends SpanCostListener {
        public All() { super(true); }
    }
}
