package com.example.shop.common.util;

/** Null-safe string helpers. Kept deliberately tiny; we do not pull in commons-lang. */
public final class Texts {

    private Texts() {
    }

    public static String trimToNull(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }

    public static boolean isBlank(String value) {
        return value == null || value.isBlank();
    }

    public static String abbreviate(String value, int maxLength) {
        if (value == null || value.length() <= maxLength) {
            return value;
        }
        if (maxLength < 2) {
            return value.substring(0, maxLength);
        }
        return value.substring(0, maxLength - 1) + "…";
    }
}
