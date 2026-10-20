package io.github.retronym.perflab.audit;

import org.objectweb.asm.ClassReader;
import org.objectweb.asm.ClassVisitor;
import org.objectweb.asm.ClassWriter;
import org.objectweb.asm.Label;
import org.objectweb.asm.MethodVisitor;
import org.objectweb.asm.Opcodes;
import org.objectweb.asm.Type;

import java.lang.instrument.ClassFileTransformer;
import java.lang.instrument.Instrumentation;
import java.nio.file.Path;
import java.security.ProtectionDomain;
import java.util.*;

/**
 * `-javaagent:audit-agent.jar=spec=<file>,out=<report.json>` ({@code {pid}} in it is the JVM's pid): weaves the probes of an audit spec ({@link Spec}) into
 * the classes they name as those load, and writes the report ({@link Audit}) at exit. A probe becomes a call to
 * {@code Audit.hit(id, receiver)} at the method's entry, or before each of its returns; a hook, into calls to the
 * program's own static methods (see {@link Spec}).
 *
 * Weaves with ASM, shaded and relocated into the agent's jar.
 */
public final class AuditAgent {
    private AuditAgent() {}

    public static void premain(String args, Instrumentation inst) throws Exception {
        Map<String, String> kv = new HashMap<>();
        for (String a : (args == null ? "" : args).split(","))
            if (a.contains("=")) kv.put(a.substring(0, a.indexOf('=')), a.substring(a.indexOf('=') + 1));
        if (!kv.containsKey("spec")) throw new IllegalArgumentException("audit agent: spec=<file> missing");
        Spec spec = Spec.read(Path.of(kv.get("spec")));
        // {pid}: one report per JVM, e.g. per JMH fork
        Path out = Path.of(kv.getOrDefault("out", "audit-{pid}.json").replace("{pid}", Long.toString(ProcessHandle.current().pid())));
        Map<String, List<Integer>> byOwner = new HashMap<>();  // internal class name -> probe ids
        for (Spec.Line l : spec.lines()) byOwner.computeIfAbsent(l.owner().replace('.', '/'), k -> new ArrayList<>()).add(Audit.register(l));
        // a spec of hooks alone writes no report
        if (spec.lines().stream().anyMatch(l -> l.kind() != Spec.Kind.HOOK)) Audit.start(out);
        Set<String> woven = Collections.synchronizedSet(new TreeSet<>());
        inst.addTransformer(new ClassFileTransformer() {
            @Override
            public byte[] transform(ClassLoader loader, String name, Class<?> redefining, ProtectionDomain pd, byte[] bytes) {
                List<Integer> ids = byOwner.get(name);
                if (ids == null) return null;
                try {
                    byte[] b = weave(bytes, ids, woven);
                    return b;
                } catch (Throwable t) {
                    System.err.println("[audit] cannot weave " + name + ": " + t);
                    return null;
                }
            }
        });
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            for (Spec.Line l : spec.lines())
                if (woven.stream().noneMatch(w -> w.startsWith(l.name() + " ")))
                    System.err.println("[audit] probe " + l.name() + " was never woven: no method " + l.owner() + "#" + l.method()
                        + (l.descPrefix() == null ? "" : l.descPrefix()) + " loaded");
        }, "audit-check"));
        System.err.println("[audit] " + spec.lines().size() + " probes, report to " + out);
    }

    static byte[] weave(byte[] bytes, List<Integer> ids, Set<String> woven) {
        ClassReader r = new ClassReader(bytes);
        // Code at method entry and before returns is stack-neutral, so existing frames stay valid and only max stack
        // changes. A hook's exit handler needs a frame of its own, so frames are read expanded (F_NEW throughout).
        ClassWriter w = new ClassWriter(r, ClassWriter.COMPUTE_MAXS);
        r.accept(new ClassVisitor(Opcodes.ASM9, w) {
            @Override
            public MethodVisitor visitMethod(int access, String name, String desc, String sig, String[] exc) {
                MethodVisitor mv = super.visitMethod(access, name, desc, sig, exc);
                List<Spec.Line> here = new ArrayList<>();
                List<Integer> hereIds = new ArrayList<>();
                for (int id : ids) {
                    Spec.Line l = Audit.probes.get(id).spec;
                    if (l.method().equals(name) && (l.descPrefix() == null || desc.startsWith(l.descPrefix()))) {
                        here.add(l);
                        hereIds.add(id);
                        woven.add(l.name() + " " + name + desc);
                    }
                }
                if (here.isEmpty()) return mv;
                boolean isStatic = (access & Opcodes.ACC_STATIC) != 0;
                boolean anyExitHook = here.stream().anyMatch(l -> l.kind() == Spec.Kind.HOOK && l.exitCall() != null);
                return new MethodVisitor(Opcodes.ASM9, mv) {
                    private final Label start = new Label(), handler = new Label();
                    private boolean hasCode;

                    private void hit(int id) {
                        super.visitLdcInsn(id);
                        if (isStatic) super.visitInsn(Opcodes.ACONST_NULL);
                        else super.visitVarInsn(Opcodes.ALOAD, 0);
                        super.visitMethodInsn(Opcodes.INVOKESTATIC, "io/github/retronym/perflab/audit/Audit", "hit", "(ILjava/lang/Object;)V", false);
                    }

                    // `call`: the receiver (null in a static method) and the arguments, references as Object
                    private void enterHook(Spec.Line l) {
                        if (isStatic) super.visitInsn(Opcodes.ACONST_NULL);
                        else super.visitVarInsn(Opcodes.ALOAD, 0);
                        StringBuilder hd = new StringBuilder("(Ljava/lang/Object;");
                        int slot = isStatic ? 0 : 1;
                        for (Type t : Type.getArgumentTypes(desc)) {
                            super.visitVarInsn(t.getOpcode(Opcodes.ILOAD), slot);
                            slot += t.getSize();
                            hd.append(t.getSort() == Type.OBJECT || t.getSort() == Type.ARRAY ? "Ljava/lang/Object;" : t.getDescriptor());
                        }
                        staticCall(l.call(), hd.append(")V").toString());
                    }

                    private void staticCall(String target, String hookDesc) {
                        int hash = target.indexOf('#');
                        super.visitMethodInsn(Opcodes.INVOKESTATIC, target.substring(0, hash).replace('.', '/'), target.substring(hash + 1), hookDesc, false);
                    }

                    // exit hooks in the reverse order of their entries, so nested hooks unwind as they nest
                    private void exitHooks() {
                        for (int i = here.size() - 1; i >= 0; i--) {
                            Spec.Line l = here.get(i);
                            if (l.kind() == Spec.Kind.HOOK && l.exitCall() != null) staticCall(l.exitCall(), "()V");
                        }
                    }

                    @Override
                    public void visitCode() {
                        super.visitCode();
                        hasCode = true;
                        for (int i = 0; i < here.size(); i++) {
                            Spec.Line l = here.get(i);
                            if (l.kind() == Spec.Kind.HOOK) enterHook(l);
                            else if (!l.exit()) hit(hereIds.get(i));
                        }
                        if (anyExitHook) super.visitLabel(start);
                    }

                    @Override
                    public void visitInsn(int opcode) {
                        if (opcode >= Opcodes.IRETURN && opcode <= Opcodes.RETURN) {
                            for (int i = 0; i < here.size(); i++)
                                if (here.get(i).kind() != Spec.Kind.HOOK && here.get(i).exit()) hit(hereIds.get(i));
                            exitHooks();
                        }
                        super.visitInsn(opcode);
                    }

                    @Override
                    public void visitMaxs(int maxStack, int maxLocals) {
                        if (hasCode && anyExitHook) {
                            // A catch-all handler after the method's own code: last in the exception table, so the
                            // method's handlers take precedence. Its frame declares no locals (all TOP), which every
                            // frame in the range is assignable to, whatever the method stores in its slots.
                            super.visitLabel(handler);
                            super.visitFrame(Opcodes.F_NEW, 0, new Object[0], 1, new Object[]{"java/lang/Throwable"});
                            exitHooks();
                            super.visitInsn(Opcodes.ATHROW);
                            super.visitTryCatchBlock(start, handler, handler, null);
                        }
                        super.visitMaxs(maxStack, maxLocals);
                    }
                };
            }
        }, ClassReader.EXPAND_FRAMES);
        return w.toByteArray();
    }
}
