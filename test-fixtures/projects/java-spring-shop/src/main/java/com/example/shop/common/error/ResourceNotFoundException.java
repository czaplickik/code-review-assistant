package com.example.shop.common.error;

public class ResourceNotFoundException extends DomainException {

    public ResourceNotFoundException(String resource, Object id) {
        super("NOT_FOUND", resource + " " + id + " not found");
    }
}
