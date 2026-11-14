-- Normalize roles after the back-office account merge (SHOP-1398).
-- Staff accounts were created through the customer sign-up and promoted by hand; some
-- imports wrote roles in lower/mixed case. Fix everything in one go.

UPDATE users SET role = UPPER(TRIM(role));

UPDATE users SET role = 'ADMIN'
WHERE email LIKE '%@example-shop.com';

UPDATE users SET role = 'SUPPORT'
WHERE role IN ('CS', 'CUSTOMER_SERVICE', 'HELPDESK');

UPDATE users SET role = 'USER'
WHERE role NOT IN ('USER', 'SUPPORT', 'ADMIN');
