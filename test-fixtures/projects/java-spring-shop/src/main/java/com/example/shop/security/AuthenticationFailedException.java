package com.example.shop.security;

import com.example.shop.common.error.DomainException;

/** Invalid credentials or refresh token. Mapped to 401; message is safe to return to clients. */
public class AuthenticationFailedException extends DomainException {

    public AuthenticationFailedException(String message) {
        super("AUTHENTICATION_FAILED", message);
    }
}
