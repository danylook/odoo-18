# Part of Odoo. See LICENSE file for full copyright and licensing details.


# Currency codes of the currencies supported by Mercado Pago in ISO 4217 format.
# See https://api.mercadopago.com/currencies. Last seen online: 2024-10-29.
SUPPORTED_CURRENCIES = [
    'USD',  # US Dollars
    'UYU',  # Uruguayan Peso
]

# Set of currencies where Mercado Pago's minor units deviates from the ISO 4217 standard.
# See https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/lists/list-one.xls
# vs. https://api.mercadopago.com/currencies. Last seen online: 2024-10-29.
CURRENCY_DECIMALS = {
    'COP': 0,
    'HNL': 0,
    'NIO': 0,
}

# The codes of the payment methods to activate when Mercado Pago is activated.
DEFAULT_PAYMENT_METHODS_CODES = [
    # Primary payment methods.
    'card', 'bank_transfer', 
    # Brand payment methods.
    'visa',
    'mastercard',
    'oca',
    'tarjeta_mercadopago',
    ]

# Mapping of payment method codes to Mercado Pago codes.
PAYMENT_METHODS_MAPPING = {
    'card': 'debit_card,credit_card,prepaid_card',
    'paypal': 'digital_wallet',
}

# Mapping of transaction states to Mercado Pago payment statuses.
# See https://www.mercadopago.com.mx/developers/en/reference/payments/_payments_id/get.
TRANSACTION_STATUS_MAPPING = {
    'pending': ('pending', 'in_process', 'in_mediation', 'authorized'),
    'done': ('approved', 'refunded'),
    'canceled': ('cancelled', 'null'),
    'error': ('rejected',),
}

# Mapping of error states to Mercado Pago error messages (lazy strings, translated at render time).
# See https://www.mercadopago.com.ar/developers/en/docs/checkout-api/response-handling/collection-results
ERROR_MESSAGE_MAPPING = {
    'accredited': (
        "Your payment has been credited. In your summary you will see the charge as a statement "
        "descriptor."
    ),
    'pending_contingency': (
        "We are processing your payment. Don't worry, in less than 2 business days, we will notify "
        "you by e-mail if your payment has been credited."
    ),
    'pending_review_manual': (
        "We are processing your payment. Don't worry, less than 2 business days we will notify you "
        "by e-mail if your payment has been credited or if we need more information."
    ),
    'cc_rejected_bad_filled_card_number': "Check the card number.",
    'cc_rejected_bad_filled_date': "Check expiration date.",
    'cc_rejected_bad_filled_other': "Check the data.",
    'cc_rejected_bad_filled_security_code': "Check the card security code.",
    'cc_rejected_blacklist': "We were unable to process your payment, please use another card.",
    'cc_rejected_call_for_authorize': "You must authorize the payment with this card.",
    'cc_rejected_card_disabled': (
        "Call your card issuer to activate your card or use another payment method. The phone "
        "number is on the back of your card."
    ),
    'cc_rejected_card_error': (
        "We were unable to process your payment, please check your card information."
    ),
    'cc_rejected_duplicated_payment': (
        "You have already made a payment for that value. If you need to pay again, use another card"
        " or another payment method."
    ),
    'cc_rejected_high_risk': (
        "We were unable to process your payment, please use another card."
    ),
    'cc_rejected_insufficient_amount': "Your card has not enough funds.",
    'cc_rejected_invalid_installments': (
        "This payment method does not process payments in installments."
    ),
    'cc_rejected_max_attempts': (
        "You have reached the limit of allowed attempts. Choose another card or other means of "
        "payment."
    ),
    'cc_rejected_other_reason': "Payment was not processed, use another card or contact issuer.",
}

