package io.github.retronym.perflab.costs;

/**
 * What a frame on a {@link CostStack} measures: a phase, typing a definition, an implicit search, ... A program's kinds
 * are given to its stack in order, which is also their order in the table.
 */
public final class CostKind {
    /** How a frame of this kind is split by phase in the table. */
    public enum Phases {
        /** not per phase: one row per key */
        NONE,
        /** per phase, the frame's own (a phase, or a unit in a phase) */
        OWN,
        /** per phase, that of the innermost {@link #OWN} frame enclosing it (else the one given on entry) */
        ENCLOSING
    }

    public final String label;
    public final Phases phases;
    /** Keyed by the innermost frame's key (an implicit search is charged to the definition it is in) */
    public final boolean inheritsKey;
    int ordinal = -1;

    public CostKind(String label, Phases phases, boolean inheritsKey) {
        this.label = label;
        this.phases = phases;
        this.inheritsKey = inheritsKey;
    }

    @Override
    public String toString() { return label; }
}
