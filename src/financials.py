"""Financial calculation utilities for mortgage estimates."""

# Assumptions
DOWN_PAYMENT_PERCENT = 0.20  # 20%
INTEREST_RATE = 0.07  # 7% annual
LOAN_TERM_YEARS = 30
PROPERTY_TAX_RATE = 0.022  # 2.2% annually (Travis County avg)
ANNUAL_INSURANCE = 2000  # $2,000/year estimate


def calculate_down_payment(price: int | float) -> float:
    """Calculate 20% down payment."""
    return price * DOWN_PAYMENT_PERCENT


def calculate_loan_amount(price: int | float) -> float:
    """Calculate loan amount after down payment."""
    return price * (1 - DOWN_PAYMENT_PERCENT)


def calculate_monthly_pi(price: int | float) -> float:
    """
    Calculate monthly Principal & Interest payment.

    Uses standard amortization formula:
    M = P * [r(1+r)^n] / [(1+r)^n - 1]

    Where:
    - M = monthly payment
    - P = principal (loan amount)
    - r = monthly interest rate
    - n = number of payments
    """
    principal = calculate_loan_amount(price)
    monthly_rate = INTEREST_RATE / 12
    num_payments = LOAN_TERM_YEARS * 12

    if monthly_rate == 0:
        return principal / num_payments

    payment = principal * (
        (monthly_rate * (1 + monthly_rate) ** num_payments)
        / ((1 + monthly_rate) ** num_payments - 1)
    )
    return payment


def calculate_monthly_tax(price: int | float) -> float:
    """Calculate monthly property tax."""
    annual_tax = price * PROPERTY_TAX_RATE
    return annual_tax / 12


def calculate_monthly_insurance() -> float:
    """Calculate monthly insurance."""
    return ANNUAL_INSURANCE / 12


def calculate_total_monthly(price: int | float) -> float:
    """
    Calculate total estimated monthly payment.

    Includes: Principal, Interest, Property Tax, Insurance (PITI)
    No PMI since we assume 20% down.
    """
    pi = calculate_monthly_pi(price)
    tax = calculate_monthly_tax(price)
    insurance = calculate_monthly_insurance()
    return pi + tax + insurance


def get_assumptions_text() -> str:
    """Return formatted assumptions text for email footer."""
    return f"""• Down payment: {int(DOWN_PAYMENT_PERCENT * 100)}%
• Interest rate: {INTEREST_RATE * 100:.1f}% (30-year fixed)
• Property tax: {PROPERTY_TAX_RATE * 100:.1f}%/year (Travis County avg)
• Insurance: ${ANNUAL_INSURANCE:,}/year
• Monthly = P&I + Tax + Insurance (no PMI with 20% down)"""
