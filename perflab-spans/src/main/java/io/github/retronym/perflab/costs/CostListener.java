package io.github.retronym.perflab.costs;

/**
 * Told about each frame of a {@link CostStack} as it is entered and left, on the measured thread: e.g. to record
 * async-profiler spans nested as the frames are ({@link SpanCostListener}). Created by name; needs a public
 * no-argument constructor. Transparent frames (untracked keys) are not reported.
 */
public interface CostListener {
    /** `frame` was entered, inside its parent */
    void enter(CostStack.Frame frame);

    /** `frame` was left; it is reused afterwards, so it must not be kept */
    void exit(CostStack.Frame frame);

    default void finished() {}
}
