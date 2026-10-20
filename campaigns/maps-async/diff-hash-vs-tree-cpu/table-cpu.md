cpu per op (benchmark threads): a 991, b 806, -18.6%  (ms/op a 3965, b 40770; ops a 6, b 6; a = hash/1, b = tree/1)

self cpu per op, biggest decreases then increases (b − a):

| Δ | a | b | Δ of a's total | method |
|---|---|---|---|---|
| -164 | 208 | 44 | -16.50% | `java/lang/StringLatin1.toLowerCase` |
| -133 | 162 | 29.3 | -13.41% | `sample/WordCount.count` |
| -98.3 | 98.3 | 0 | -9.92% | `java/util/HashMap.merge` |
| -60.7 | 60.7 | 0 | -6.12% | `java/util/HashMap.resize` |
| -24.5 | 24.7 | 0.167 | -2.47% | `sample/WordCount.<init>` |
| -23.5 | 23.5 | 0 | -2.37% | `java/lang/StringLatin1.hashCode` |
| -8.5 | 8.5 | 0 | -0.86% | `java/lang/String.equals` |
| -8 | 8.67 | 0.667 | -0.81% | `java/util/ArrayList$Itr.next` |
| -2.67 | 3.5 | 0.833 | -0.27% | `StackWalker::walkVM` |
| -2.5 | 2.5 | 0 | -0.25% | `java/util/HashMap$Node.<init>` |
| -2.5 | 2.5 | 0 | -0.25% | `java/util/HashMap.hash` |
| -1.83 | 1.83 | 0 | -0.19% | `java/lang/String.isLatin1` |
| -1.67 | 1.67 | 0 | -0.17% | `java/lang/String.hashCode` |
| -1.67 | 1.67 | 0 | -0.17% | `java/util/Locale.getLanguage` |
| -0.833 | 0.833 | 0 | -0.08% | `java/util/HashMap.newNode` |
| -0.833 | 0.833 | 0 | -0.08% | `java/lang/CharacterDataLatin1.toLowerCase` |
| -0.667 | 0.833 | 0.167 | -0.07% | `thread_self_trap` |
| -0.5 | 0.833 | 0.333 | -0.05% | `_kernelrpc_mach_port_deallocate_trap` |
| -0.333 | 0.5 | 0.167 | -0.03% | `sigprocmask` |
| -0.333 | 0.333 | 0 | -0.03% | `__sigaltstack` |
| -0.333 | 0.333 | 0 | -0.03% | `zero_blocks` |
| -0.333 | 0.333 | 0 | -0.03% | `mach_absolute_time` |
| -0.167 | 0.167 | 0 | -0.02% | `_xzm_free_main` |
| -0.167 | 0.167 | 0 | -0.02% | `JvmtiThreadState::state_for` |
| -0.167 | 0.167 | 0 | -0.02% | `Java_one_profiler_Recording_emitSpan` |
| … | | | | |
| +280 | 375 | 656 | +28.31% | `sample/WordCount$$Lambda.apply` |
| +39.5 | 0 | 39.5 | +3.99% | `java/util/TreeMap.merge` |
| +15.5 | 0 | 15.5 | +1.56% | `java/lang/String.compareTo` |
| +4.67 | 0 | 4.67 | +0.47% | `java/lang/String.coder` |
| +2.17 | 0 | 2.17 | +0.22% | `java/util/TreeMap.rightOf` |
| +2.17 | 0 | 2.17 | +0.22% | `java/util/TreeMap.fixAfterInsertion` |
| +1.83 | 0 | 1.83 | +0.19% | `java/util/TreeMap.rotateRight` |
| +1.33 | 0 | 1.33 | +0.13% | `java/util/TreeMap.rotateLeft` |
| +1.17 | 0 | 1.17 | +0.12% | `java/util/TreeMap.mergeValue` |
| +0.667 | 0 | 0.667 | +0.07% | `__psynch_cvwait` |
| +0.667 | 0 | 0.667 | +0.07% | `java/util/TreeMap.addEntry` |
| +0.5 | 0 | 0.5 | +0.05% | `java/util/TreeMap.parentOf` |
| +0.333 | 0 | 0.333 | +0.03% | `ObjArrayAllocator::initialize` |
| +0.333 | 0 | 0.333 | +0.03% | `MemAllocator::allocate` |
| +0.333 | 0 | 0.333 | +0.03% | `java/util/Objects.checkIndex` |
| +0.333 | 0 | 0.333 | +0.03% | `JvmtiExport::post_sampled_object_alloc` |
| +0.333 | 0 | 0.333 | +0.03% | `semaphore_wait_trap` |
| +0.167 | 0 | 0.167 | +0.02% | `jdk/internal/misc/Unsafe.convEndian` |
| +0.167 | 0 | 0.167 | +0.02% | `jvmti_GetClassSignature` |
| +0.167 | 0 | 0.167 | +0.02% | `_tlv_get_addr` |
| +0.167 | 0 | 0.167 | +0.02% | `jni_ReleaseStringUTFChars` |
| +0.167 | 0 | 0.167 | +0.02% | `bool startsWith<16ul>` |
| +0.167 | 0 | 0.167 | +0.02% | `JfrAllocationTracer::JfrAllocationTracer` |
| +0.167 | 0 | 0.167 | +0.02% | `G1NUMA::is_enabled` |
| +0.167 | 0 | 0.167 | +0.02% | `ObjectSampler::SampledObjectAlloc` |
