package com.example.shop.common.util;

import java.text.Normalizer;
import java.util.Locale;
import java.util.regex.Pattern;

/** URL slug helpers shared by the catalogue. */
public final class Slugs {

    private static final Pattern DIACRITICS = Pattern.compile("\\p{M}+");
    private static final Pattern NON_ALPHANUMERIC = Pattern.compile("[^a-z0-9]+");
    private static final Pattern EDGE_DASHES = Pattern.compile("(^-+|-+$)");
    private static final int MAX_LENGTH = 200;

    private Slugs() {
    }

    public static String slugify(String input) {
        if (input == null || input.isBlank()) {
            throw new IllegalArgumentException("Cannot build a slug from a blank value");
        }
        String decomposed = Normalizer.normalize(input.trim(), Normalizer.Form.NFD);
        String ascii = DIACRITICS.matcher(decomposed).replaceAll("");
        String dashed = NON_ALPHANUMERIC.matcher(ascii.toLowerCase(Locale.ROOT)).replaceAll("-");
        String slug = EDGE_DASHES.matcher(dashed).replaceAll("");
        return slug.length() <= MAX_LENGTH ? slug : slug.substring(0, MAX_LENGTH);
    }

    public static String withSuffix(String slug, int suffix) {
        return slug + "-" + suffix;
    }
}
