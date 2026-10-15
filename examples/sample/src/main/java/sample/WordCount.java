package sample;

import java.util.*;

/** Counts the words of a text in a map: the code under benchmark. */
public final class WordCount {
    private final Map<String, Integer> counts;

    public WordCount(String impl) {
        this.counts = switch (impl) {
            case "hash" -> new HashMap<>();
            case "linked" -> new LinkedHashMap<>();
            case "tree" -> new TreeMap<>();
            default -> throw new IllegalArgumentException("map " + impl);
        };
    }

    public int count(List<String> words) {
        for (String w : words) counts.merge(normalize(w), 1, Integer::sum);
        return counts.size();
    }

    public boolean contains(String word) {
        return counts.containsKey(normalize(word));
    }

    static String normalize(String w) {
        return w.toLowerCase(Locale.ROOT);
    }
}
