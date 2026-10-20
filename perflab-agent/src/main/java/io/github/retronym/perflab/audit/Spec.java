package io.github.retronym.perflab.audit;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

/**
 * An audit spec: one probe per line, `<kind> <name> key=value...`; `#` starts a comment.
 *
 * <pre>
 * count  envelope.ctor  at=dotty.tools.dotc.ast.Positioned#envelope  from=dotty.tools.dotc.ast.Positioned#&lt;init&gt;  onStack=copier:dotty.tools.dotc.ast.Trees$Instance$TreeCopier
 * sites  fill  at=dotty.tools.dotc.ast.Positioned#envelope  from=dotty.tools.dotc.ast.Positioned#include$1  depth=4  skip=^dotty\.tools\.dotc\.ast\.Positioned\.  qualify=class,tag
 * tag    origin  at=dotty.tools.dotc.ast.Positioned#&lt;init&gt;  exit  when=io.github.retronym.perflab.audit.Predicates#spanless  depth=3  skip=...
 * </pre>
 *
 * Kinds: `count` counts hits under `name`, split by `onStack`; `sites` counts the distinct call sites reaching the
 * probe; `tag` tags the receiver with its site, for a later `sites` probe to read with `qualify=tag`; `hook` calls a
 * static method of the program's at entry (`call=Class#method`, given the receiver and the method's arguments) and,
 * with `exit=Class#method`, another before each return and when the method throws.
 *
 * Keys: `at=Class#method` (every overload, or `Class#method(desc-prefix` for some), woven at `entry` (default) or `exit`
 * (before each return; required for constructors, whose receiver is not usable before `super()`); `from=Class#method`,
 * only when called from there; `when=Class#staticMethod`, a `static boolean m(Object)` on the receiver, only when it
 * holds; `depth=N` caller frames per site (default 3) after dropping frames whose `Class.method` the regex `skip`
 * finds; `qualify=class,tag` adds the receiver's class and its tag to the site; `onStack=label:where,...` classifies a
 * hit by the first label whose `where` (a class name prefix, or `Class#method`) is on the stack (else `other`);
 * `sample=N` records one site in N.
 */
record Spec(List<Line> lines) {
    enum Kind { COUNT, SITES, TAG, HOOK }

    record Line(Kind kind, String name, String owner, String method, String descPrefix, boolean exit, String from,
                String when, int depth, String skip, List<String> qualify, LinkedHashMap<String, String> onStack, int sample,
                String call, String exitCall) {}

    static Spec read(Path file) throws IOException {
        List<Line> lines = new ArrayList<>();
        int n = 0;
        for (String raw : Files.readAllLines(file)) {
            n++;
            String l = raw.replaceFirst("(^|\\s)#.*", "").trim();
            if (l.isEmpty()) continue;
            String[] ws = l.split("\\s+");
            if (ws.length < 3) throw new IllegalArgumentException(file + ":" + n + ": expected <kind> <name> at=...");
            Kind kind = Kind.valueOf(ws[0].toUpperCase());
            Map<String, String> kv = new HashMap<>();
            boolean exit = false;
            for (int i = 2; i < ws.length; i++) {
                if (ws[i].equals("exit")) exit = true;
                else if (ws[i].equals("entry")) exit = false;
                else {
                    int eq = ws[i].indexOf('=');
                    if (eq < 0) throw new IllegalArgumentException(file + ":" + n + ": not key=value: " + ws[i]);
                    kv.put(ws[i].substring(0, eq), ws[i].substring(eq + 1));
                }
            }
            String at = kv.get("at");
            if (at == null || !at.contains("#")) throw new IllegalArgumentException(file + ":" + n + ": at=Class#method missing");
            String owner = at.substring(0, at.indexOf('#')), m = at.substring(at.indexOf('#') + 1);
            String desc = null;
            if (m.contains("(")) { desc = m.substring(m.indexOf('(')); m = m.substring(0, m.indexOf('(')); }
            if (kind == Kind.HOOK) {
                if (kv.get("call") == null || !kv.get("call").contains("#")) throw new IllegalArgumentException(file + ":" + n + ": a hook needs call=Class#method");
                if (kv.containsKey("exit") && !kv.get("exit").contains("#")) throw new IllegalArgumentException(file + ":" + n + ": exit=Class#method");
                if (m.equals("<init>")) throw new IllegalArgumentException(file + ":" + n + ": no hooks in constructors");
            } else if (m.equals("<init>") && !exit) throw new IllegalArgumentException(file + ":" + n + ": a constructor probe needs `exit`");
            LinkedHashMap<String, String> onStack = new LinkedHashMap<>();
            if (kv.containsKey("onStack"))
                for (String e : kv.get("onStack").split(",")) onStack.put(e.substring(0, e.indexOf(':')), e.substring(e.indexOf(':') + 1));
            lines.add(new Line(kind, ws[1], owner, m, desc, exit, kv.get("from"), kv.get("when"),
                Integer.parseInt(kv.getOrDefault("depth", "3")), kv.get("skip"),
                kv.containsKey("qualify") ? List.of(kv.get("qualify").split(",")) : List.of(), onStack,
                Integer.parseInt(kv.getOrDefault("sample", "1")), kv.get("call"), kv.get("exit")));
        }
        return new Spec(lines);
    }
}
