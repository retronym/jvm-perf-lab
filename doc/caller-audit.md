# Caller audits

`perflab-agent` counts which callers reach a method, how often, and which code created the objects those callers work on. Probes are woven into classes as they load, from a spec file, so the audited program needs no change.

```
java -javaagent:perflab-agent.jar=spec=<file>,out=<report.json> ...
```

`{pid}` in `out` is replaced by the JVM's pid, for one report per JMH fork.

## Spec

One probe per line, `<kind> <name> key=value…`; `#` starts a comment.

| kind | effect |
|---|---|
| `count` | counts hits under `name`, split by `onStack` labels into `name.<label>` |
| `sites` | counts the distinct call sites reaching the probe |
| `tag` | tags the receiver with its call site, weakly and by identity, for a later `sites` probe to read with `qualify=tag` |

| key | meaning |
|---|---|
| `at=Class#method` | the method to probe; `Class#method(desc-prefix` selects overloads by descriptor |
| `entry` / `exit` | at the method's entry (default) or before each return; constructors need `exit` |
| `from=Class#method` | only when the probed method's immediate caller is this method |
| `when=Class#staticMethod` | only when `static boolean m(Object)` holds for the receiver; the method is loaded from the receiver's class loader, so it can use the program's types |
| `depth=N` | frames per site (default 3), counted after dropping frames whose `Class.method` the regex `skip` finds |
| `qualify=class,tag` | adds the receiver's class, and its tag, to the site |
| `onStack=label:classPrefix,…` | classifies a hit by the first label whose class prefix is on the stack, else `other` |
| `sample=N` | records the site of one hit in `N`; the hit count stays exact |

Example, from the Scala 3 compiler: how often `Positioned.envelope` fills in a child's span, and which code created the children it fills.

```
count fill      at=dotty.tools.dotc.ast.Positioned#envelope  from=dotty.tools.dotc.ast.Positioned#include$1  onStack=copier:dotty.tools.dotc.ast.Trees$Instance$TreeCopier
tag   origin    at=dotty.tools.dotc.ast.Positioned#<init>  exit  when=<helper>#spanless  depth=6  skip=^dotty\.tools\.dotc\.ast\.(Positioned|Trees\$)
sites filled-by at=dotty.tools.dotc.ast.Positioned#envelope  from=dotty.tools.dotc.ast.Positioned#include$1  depth=0  qualify=tag,class
```

## Report

JSON, written at exit: `{"counters": {name: n}, "probes": {name: {"kind", "hits", "sample", "sites": {site: n}}}}`. A site is `Class.method:line <- …`, followed by `  [qualifiers]` when the probe has any.

## Cost

Counts are `LongAdder`s in concurrent maps. A `from=` filter or a site walks the stack with `StackWalker`, so probes on hot methods should use `from=` to narrow them and `sample=N` for sites.
