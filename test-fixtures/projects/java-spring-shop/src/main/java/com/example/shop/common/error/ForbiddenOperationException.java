package com.example.shop.common.error;

public class ForbiddenOperationException extends DomainException {

    public ForbiddenOperationException(String message) {
        super("FORBIDDEN", message);
    }
}
