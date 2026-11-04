package scala.tools.asm

/** In ASM's package for `Label.flags`, which is package-private: see `BackendOps.replayedWithBlocks`. */
object LabelFlags {
  def clearDebugOnly(label: Label): Unit = label.flags = (label.flags & ~Label.FLAG_DEBUG_ONLY).toShort
}
