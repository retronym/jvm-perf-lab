package io.github.retronym.perflab.jmh;

import org.junit.jupiter.api.Test;

import java.util.*;

import static org.junit.jupiter.api.Assertions.*;

class VariantsTest {
    @Test
    void parsesNamesAndOptions() {
        Variants v = Variants.parse("base=-Yno-prime-spans  -Yx | prime= |nocheck=-Yno-check-positions");
        assertEquals(List.of("base", "prime", "nocheck"), v.names());
        assertEquals(List.of("-Yno-prime-spans", "-Yx"), v.all().get(0).options());
        assertEquals(List.of(), v.all().get(1).options());
        assertTrue(Variants.parse("").isEmpty());
        assertThrows(IllegalArgumentException.class, () -> Variants.parse("=x"));
    }

    @Test
    void twoVariantsAlternateABBA() {
        assertArrayEquals(new int[]{0, 1}, Variants.order(2, 0));
        assertArrayEquals(new int[]{1, 0}, Variants.order(2, 1));
        Variants v = Variants.parse("a=|b=");
        assertEquals(List.of("a", "b", "b", "a", "a", "b"),
            java.util.stream.IntStream.range(0, 6).mapToObj(i -> v.forIteration(i).name()).toList());
    }

    /** Over a whole design (n rows for even n, 2n for odd), each variant takes each position equally often, and each
     *  ordered pair of different variants appears as neighbours equally often. */
    @Test
    void williamsDesignIsBalanced() {
        for (int n = 2; n <= 7; n++) {
            int rows = n % 2 == 0 ? n : 2 * n;
            int[][] pos = new int[n][n];
            Map<List<Integer>, Integer> pairs = new HashMap<>();
            for (int k = 0; k < rows; k++) {
                int[] row = Variants.order(n, k);
                assertEquals(n, Arrays.stream(row).distinct().count(), "row " + k + " is a permutation");
                for (int p = 0; p < n; p++) pos[row[p]][p]++;
                for (int p = 0; p + 1 < n; p++) pairs.merge(List.of(row[p], row[p + 1]), 1, Integer::sum);
            }
            for (int[] byPos : pos) assertEquals(1, Arrays.stream(byPos).distinct().count(), "positions balanced for n=" + n);
            assertEquals(n * (n - 1), pairs.size(), "every ordered pair occurs for n=" + n);
            assertEquals(1, new HashSet<>(pairs.values()).size(), "pairs balanced for n=" + n);
        }
    }
}
