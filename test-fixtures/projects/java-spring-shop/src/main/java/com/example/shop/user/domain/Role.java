package com.example.shop.user.domain;

public enum Role {
    /** Customer. */
    USER,
    /** Customer-support staff: can view and cancel any order. */
    SUPPORT,
    /** Back-office administrator: catalogue and configuration. */
    ADMIN
}
