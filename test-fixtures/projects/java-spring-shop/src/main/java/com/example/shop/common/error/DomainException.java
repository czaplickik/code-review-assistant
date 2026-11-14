package com.example.shop.common.error;

/**
 * Base type for every business error. Subclasses decide the HTTP status in
 * {@link GlobalExceptionHandler}; the {@link #code()} is a stable identifier clients rely on.
 */
public abstract class DomainException extends RuntimeException {

    private final String code;

    protected DomainException(String code, String message) {
        super(message);
        this.code = code;
    }

    protected DomainException(String code, String message, Throwable cause) {
        super(message, cause);
        this.code = code;
    }

    public String code() {
        return code;
    }
}
