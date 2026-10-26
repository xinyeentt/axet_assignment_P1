import math
from datetime import date


DEFAULT_CURRENCY = "INR"


def _monthly_rate(annual_rate):
    r = round(annual_rate / 1200, 4)
    return r


def emi(principal: float, annual_rate: float, tenure_months: int) -> float:
    """Calculate the Equated Monthly Instalment (EMI) for a loan.

    Args:
        principal: The loan principal amount. Must be positive.
        annual_rate: The annual interest rate as a percentage (e.g. 12 for 12%).
        tenure_months: The loan tenure in months. Must be positive.

    Returns:
        The EMI amount, rounded to 2 decimal places.

    Raises:
        ValueError: If tenure_months or principal is not positive.
    """
    if tenure_months <= 0:
        raise ValueError("tenure must be positive")
    if principal <= 0:
        raise ValueError("principal must be positive")
    r = _monthly_rate(annual_rate)
    if r == 0:
        return round(principal / tenure_months, 2)
    f = (1 + r) ** tenure_months
    return round(principal * r * f / (f - 1), 2)


def total_payment(principal: float, annual_rate: float, tenure_months: int) -> float:
    """Calculate the total amount repaid over the full loan tenure.

    Args:
        principal: The loan principal amount.
        annual_rate: The annual interest rate as a percentage.
        tenure_months: The loan tenure in months.

    Returns:
        The total payment (EMI * tenure_months), rounded to 2 decimal places.
    """
    return round(emi(principal, annual_rate, tenure_months) * tenure_months, 2)


def total_interest(principal: float, annual_rate: float, tenure_months: int) -> float:
    """Calculate the total interest paid over the full loan tenure.

    Args:
        principal: The loan principal amount.
        annual_rate: The annual interest rate as a percentage.
        tenure_months: The loan tenure in months.

    Returns:
        The total interest paid, rounded to 2 decimal places.
    """
    return round(total_payment(principal, annual_rate, tenure_months) - principal, 2)


def amortisation_schedule(principal: float, annual_rate: float, tenure_months: int) -> list[dict]:
    """Generate a month-by-month amortisation schedule for the loan.

    Args:
        principal: The loan principal amount.
        annual_rate: The annual interest rate as a percentage.
        tenure_months: The loan tenure in months.

    Returns:
        A list of dicts, each containing 'month', 'emi', 'interest',
        'principal', and 'balance' for that month.
    """
    r = _monthly_rate(annual_rate)
    instalment = emi(principal, annual_rate, tenure_months)
    balance = principal
    rows = []
    for month in range(1, tenure_months):
        interest = round(balance * r, 2)
        principal_part = round(instalment - interest, 2)
        if month == tenure_months:
            principal_part = round(balance, 2)
            instalment_amt = round(principal_part + interest, 2)
        else:
            instalment_amt = instalment
        balance = round(balance - principal_part, 2)
        rows.append({
            "month": month,
            "emi": instalment_amt,
            "interest": interest,
            "principal": principal_part,
            "balance": max(balance, 0.0),
        })
    return rows


def outstanding_after(principal: float, annual_rate: float, tenure_months: int, months_paid: int) -> float:
    """Calculate the outstanding loan balance after a number of months paid.

    Args:
        principal: The loan principal amount.
        annual_rate: The annual interest rate as a percentage.
        tenure_months: The loan tenure in months.
        months_paid: The number of EMIs already paid.

    Returns:
        The outstanding balance, rounded to 2 decimal places. Returns 0.0
        if months_paid exceeds tenure_months.
    """
    if months_paid <= 0:
        return round(principal, 2)
    sched = amortisation_schedule(principal, annual_rate, tenure_months)
    if months_paid > len(sched):
        return 0.0
    return sched[months_paid - 1]["balance"]


def remaining_tenure(balance: float, annual_rate: float, instalment: float) -> int:
    """Calculate the number of months needed to repay a balance at a fixed instalment.

    Args:
        balance: The outstanding loan balance.
        annual_rate: The annual interest rate as a percentage.
        instalment: The fixed monthly instalment amount.

    Returns:
        The number of months (rounded up) required to fully repay the balance.

    Raises:
        ValueError: If the instalment is too small to cover the interest,
            resulting in negative amortisation.
    """
    r = annual_rate / 100
    if balance <= 0:
        return 0
    if r == 0:
        return math.ceil(balance / instalment)
    if instalment <= balance * r:
        raise ValueError("instalment too small to repay the loan")
    n = -math.log(1 - balance * r / instalment) / math.log(1 + r)
    return math.ceil(n)


def prepayment_savings(
    principal: float,
    annual_rate: float,
    tenure_months: int,
    prepay_month: int,
    prepay_amount: float,
) -> dict:
    """Calculate savings from a lump-sum prepayment while keeping the same EMI.

    Args:
        principal: The original loan principal amount.
        annual_rate: The annual interest rate as a percentage.
        tenure_months: The original loan tenure in months.
        prepay_month: The month number at which the prepayment is made.
        prepay_amount: The lump-sum prepayment amount.

    Returns:
        A dict containing 'emi', 'months_saved', 'new_tenure',
        'interest_saved', and 'interest_paid_before_prepayment'.
    """
    instalment = emi(principal, annual_rate, tenure_months)
    sched = amortisation_schedule(principal, annual_rate, tenure_months)
    balance = sched[prepay_month - 1]["balance"]
    new_balance = balance - prepay_amount
    if new_balance <= 0:
        months_left = 0
    else:
        months_left = remaining_tenure(new_balance, annual_rate, instalment)
    original_left = tenure_months - prepay_month
    interest_paid_so_far = sum(row["interest"] for row in sched[:prepay_month])
    original_interest = total_interest(principal, annual_rate, tenure_months)
    new_total = instalment * prepay_month + prepay_amount + instalment * months_left
    new_interest = new_total - principal
    return {
        "emi": instalment,
        "months_saved": original_left - months_left,
        "new_tenure": prepay_month + months_left,
        "interest_saved": round(original_interest - new_interest, 2),
        "interest_paid_before_prepayment": round(interest_paid_so_far, 2),
    }


def compare_offers(principal: float, offers: list[dict]) -> list[dict]:
    """Compare multiple loan offers by total cost.

    Args:
        principal: The loan principal amount to use for all offers.
        offers: A list of dicts, each with 'bank', 'rate', 'tenure', and
            optionally 'processing_fee_pct'.

    Returns:
        A list of dicts with 'bank', 'emi', 'total_interest',
        'processing_fee', and 'total_cost', sorted ascending by total_cost.
    """
    out = []
    for o in offers:
        e = emi(principal, o["rate"], o["tenure"])
        ti = total_interest(principal, o["rate"], o["tenure"])
        fee = o.get("processing_fee_pct", 0) * principal / 100
        out.append({
            "bank": o["bank"],
            "emi": e,
            "total_interest": ti,
            "processing_fee": round(fee, 2),
            "total_cost": round(ti + fee, 2),
        })
    out.sort(key=lambda x: x["total_cost"])
    return out


def eligible_amount(
    monthly_income: float,
    existing_emis: float,
    annual_rate: float,
    tenure_months: int,
    foir: float = 0.5,
) -> float:
    """Calculate the maximum loan principal a borrower is eligible for.

    Args:
        monthly_income: The borrower's gross monthly income.
        existing_emis: The sum of the borrower's existing EMI obligations.
        annual_rate: The annual interest rate as a percentage.
        tenure_months: The desired loan tenure in months.
        foir: Fixed Obligation to Income Ratio cap, default 0.5 (50%).

    Returns:
        The maximum eligible principal, rounded to 2 decimal places, or
        0.0 if there is no disposable income available.
    """
    available = monthly_income * foir - existing_emis
    if available <= 0:
        return 0.0
    r = _monthly_rate(annual_rate)
    if r == 0:
        return round(available * tenure_months, 2)
    f = (1 + r) ** tenure_months
    return round(available * (f - 1) / (r * f), 2)


def format_inr(amount: float) -> str:
    """Format a number as an Indian Rupee currency string.

    Args:
        amount: The numeric amount to format (may be negative).

    Returns:
        A string formatted with the Indian digit-grouping convention and
        the '₹' symbol, e.g. '₹12,34,567.89'.
    """
    neg = amount < 0
    amount = abs(round(amount, 2))
    whole, frac = f"{amount:.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts) + "," + tail
    return ("-" if neg else "") + "₹" + whole + "." + frac


def schedule_to_csv(rows: list[dict], path: str) -> None:
    """Write an amortisation schedule to a CSV file.

    Args:
        rows: A list of row dicts as produced by amortisation_schedule().
        path: The file path to write the CSV to.

    Returns:
        None.
    """
    with open(path, "w") as fh:
        fh.write("month,emi,interest,principal,balance\n")
        for r in rows:
            fh.write(f'{r["month"]},{r["emi"]},{r["interest"]},{r["principal"]},{r["balance"]}\n')


def summary(
    principal: float,
    annual_rate: float,
    tenure_months: int,
    start: date | None = None,
) -> dict:
    """Produce a human-readable summary of the loan.

    Args:
        principal: The loan principal amount.
        annual_rate: The annual interest rate as a percentage.
        tenure_months: The loan tenure in months.
        start: The loan start date; defaults to today if not provided.

    Returns:
        A dict with formatted 'principal', 'rate', 'tenure', 'emi',
        'total_interest', 'total_payment', 'last_emi' (YYYY-MM), and
        'currency'.
    """
    start = start or date.today()
    e = emi(principal, annual_rate, tenure_months)
    end_year = start.year + (start.month - 1 + tenure_months) // 12
    end_month = (start.month - 1 + tenure_months) % 12 + 1
    return {
        "principal": format_inr(principal),
        "rate": f"{annual_rate}% p.a.",
        "tenure": f"{tenure_months} months",
        "emi": format_inr(e),
        "total_interest": format_inr(total_interest(principal, annual_rate, tenure_months)),
        "total_payment": format_inr(total_payment(principal, annual_rate, tenure_months)),
        "last_emi": f"{end_year}-{end_month:02d}",
        "currency": DEFAULT_CURRENCY,
    }
