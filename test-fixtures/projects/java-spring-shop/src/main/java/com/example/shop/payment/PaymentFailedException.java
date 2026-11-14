package com.example.shop.payment;

import com.example.shop.common.error.BusinessRuleException;

public class PaymentFailedException extends BusinessRuleException {

    public static final String REJECTED = "PAYMENT_REJECTED";
    public static final String GATEWAY_UNAVAILABLE = "PAYMENT_GATEWAY_UNAVAILABLE";

    public PaymentFailedException(String code, String message) {
        super(code, message);
    }
}
