import math
from datetime import date
from typing import Any, Dict, Iterable, List, Optional


DEFAULT_CURRENCY = "INR"


def _monthly_rate(annual_rate: float) -> float:
    """
    Convert an annual nominal interest rate (percent per year) into a monthly periodic rate.

    Args:
        annual_rate: Annual interest rate in percent per year (e.g. 10.5 for 10.5% p.a.).

    Returns:
        Monthly periodic interest rate, rounded to 4 decimals.
    """
    r = round(annual_rate / 1200, 4)
    return r


def emi(principal: float, annual_rate: float, tenure_months: int) -> float:
    """
    Compute the fixed monthly payment (EMI) for a fully amortizing loan.

    Args:
        principal: Loan amount (must be positive).
        annual_rate: Annual interest rate in percent per year.
        tenure_months: Total number of monthly payments (must be positive).

    Returns:
        EMI amount rounded to 2 decimals.

    Raises:
        ValueError: If tenure_months <= 0 or principal <= 0.
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
    """
    Compute the total amount paid over the entire tenure.

    Args:
        principal: Loan amount.
        annual_rate: Annual interest rate in percent per year.
        tenure_months: Total number of monthly payments.

    Returns:
        Total paid (EMI * tenure) rounded to 2 decimals.
    """
    return round(emi(principal, annual_rate, tenure_months) * tenure_months, 2)


def total_interest(principal: float, annual_rate: float, tenure_months: int) -> float:
    """
    Compute the total interest paid over the entire tenure.

    Args:
        principal: Loan amount.
        annual_rate: Annual interest rate in percent per year.
        tenure_months: Total number of monthly payments.

    Returns:
        Total interest rounded to 2 decimals.
    """
    return round(total_payment(principal, annual_rate, tenure_months) - principal, 2)


def amortisation_schedule(principal: float, annual_rate: float, tenure_months: int) -> List[Dict[str, float]]:
    """
    Generate a per-month amortization schedule.

    Each row contains:
        - month: 1-based month index
        - emi: instalment amount used for that month
        - interest: interest portion for that month
        - principal: principal portion for that month
        - balance: remaining balance after the principal portion (never below 0.0)

    Notes:
        The current implementation iterates `for month in range(1, tenure_months)`,
        producing `tenure_months - 1` rows. The branch `if month == tenure_months`
        is unreachable with the current loop bounds.

    Args:
        principal: Loan amount.
        annual_rate: Annual interest rate in percent per year.
        tenure_months: Total number of monthly payments.

    Returns:
        List of amortization rows.
    """
    r = _monthly_rate(annual_rate)
    instalment = emi(principal, annual_rate, tenure_months)
    balance = principal
    rows: List[Dict[str, float]] = []
    for month in range(1, tenure_months):
        interest = round(balance * r, 2)
        principal_part = round(instalment - interest, 2)
        if month == tenure_months:
            principal_part = round(balance, 2)
            instalment_amt = round(principal_part + interest, 2)
        else:
            instalment_amt = instalment
        balance = round(balance - principal_part, 2)
        rows.append(
            {
                "month": float(month),
                "emi": float(instalment_amt),
                "interest": float(interest),
                "principal": float(principal_part),
                "balance": max(balance, 0.0),
            }
        )
    return rows


def outstanding_after(
    principal: float, annual_rate: float, tenure_months: int, months_paid: int
) -> float:
    """
    Compute the outstanding loan balance after a given number of months have been paid.

    Args:
        principal: Loan amount.
        annual_rate: Annual interest rate in percent per year.
        tenure_months: Total number of monthly payments.
        months_paid: Number of months already paid.

    Returns:
        Remaining balance rounded to 2 decimals when months_paid <= 0,
        otherwise the scheduled balance. If months_paid exceeds the schedule length, returns 0.0.
    """
    if months_paid <= 0:
        return round(principal, 2)
    sched = amortisation_schedule(principal, annual_rate, tenure_months)
    if months_paid > len(sched):
        return 0.0
    return float(sched[months_paid - 1]["balance"])


def remaining_tenure(balance: float, annual_rate: float, instalment: float) -> int:
    """
    Compute the remaining number of months required to repay a loan balance
    given a fixed monthly instalment.

    Args:
        balance: Remaining principal balance.
        annual_rate: Annual interest rate in percent per year.
        instalment: Fixed monthly payment amount.

    Returns:
        Number of months (ceiling) required to fully repay.

    Raises:
        ValueError: If instalment is too small to repay the loan.
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
) -> Dict[str, float]:
    """
    Model a lump-sum prepayment occurring at `prepay_month`, keeping EMI constant
    and shortening the tenure.

    Args:
        principal: Original loan amount.
        annual_rate: Annual interest rate in percent per year.
        tenure_months: Original loan tenure in months.
        prepay_month: 1-based month when the lump-sum prepayment happens.
        prepay_amount: Lump-sum amount paid at prepay_month.

    Returns:
        Dict with keys:
            - emi: original EMI (float)
            - months_saved: months reduced compared to original schedule
            - new_tenure: prepay_month + months_left
            - interest_saved: interest saved vs original total interest
            - interest_paid_before_prepayment: interest accumulated before prepayment

    Notes:
        This function depends on both `amortisation_schedule()` and `remaining_tenure()`.
    """
    instalment = emi(principal, annual_rate, tenure_months)
    sched = amortisation_schedule(principal, annual_rate, tenure_months)
    balance = float(sched[prepay_month - 1]["balance"])
    new_balance = balance - prepay_amount
    if new_balance <= 0:
        months_left = 0
    else:
        months_left = remaining_tenure(new_balance, annual_rate, instalment)
    original_left = tenure_months - prepay_month
    interest_paid_so_far = sum(float(row["interest"]) for row in sched[:prepay_month])
    original_interest = total_interest(principal, annual_rate, tenure_months)
    new_total = instalment * prepay_month + prepay_amount + instalment * months_left
    new_interest = new_total - principal
    return {
        "emi": float(instalment),
        "months_saved": float(original_left - months_left),
        "new_tenure": float(prepay_month + months_left),
        "interest_saved": round(original_interest - new_interest, 2),
        "interest_paid_before_prepayment": round(interest_paid_so_far, 2),
    }


def compare_offers(principal: float, offers: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Compare multiple loan offers by computing EMI, total interest, processing fees,
    and ranking by total cost.

    Args:
        principal: Loan amount.
        offers: Iterable of offer dicts. Each offer should include:
            - bank (str)
            - rate (float): annual interest rate in percent p.a.
            - tenure (int): tenure in months
            - processing_fee_pct (optional float): processing fee percentage of principal

    Returns:
        List of dicts sorted by increasing total_cost (cheapest first). Each output dict contains:
            - bank
            - emi
            - total_interest
            - processing_fee
            - total_cost
    """
    out: List[Dict[str, Any]] = []
    for o in offers:
        e = emi(principal, float(o["rate"]), int(o["tenure"]))
        ti = total_interest(principal, float(o["rate"]), int(o["tenure"]))
        fee = float(o.get("processing_fee_pct", 0)) * principal / 100
        out.append(
            {
                "bank": o["bank"],
                "emi": e,
                "total_interest": ti,
                "processing_fee": round(fee, 2),
                "total_cost": round(ti + fee, 2),
            }
        )
    out.sort(key=lambda x: x["total_cost"])
    return out


def eligible_amount(
    monthly_income: float,
    existing_emis: float,
    annual_rate: float,
    tenure_months: int,
    foir: float = 0.5,
) -> float:
    """
    Estimate the maximum eligible loan principal given affordability constraints.

    Args:
        monthly_income: Borrower's monthly income.
        existing_emis: Sum of existing monthly loan EMIs.
        annual_rate: Annual interest rate in percent per year.
        tenure_months: Tenure in months.
        foir: Fixed obligation to income ratio (fraction of income allowed for EMI payments).

    Returns:
        Eligible principal rounded to 2 decimals. Returns 0.0 if affordability is not sufficient.
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
    """
    Format a numeric amount as Indian INR currency with comma grouping.

    Args:
        amount: Monetary amount (can be negative).

    Returns:
        String formatted like: '₹1,23,456.78' (with '-' prefix if negative).
    """
    neg = amount < 0
    amount = abs(round(amount, 2))
    whole, frac = f"{amount:.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts: List[str] = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts) + "," + tail
    return ("-" if neg else "") + "₹" + whole + "." + frac


def schedule_to_csv(rows: Iterable[Dict[str, float]], path: str) -> None:
    """
    Export amortization schedule rows to a CSV file.

    Args:
        rows: Iterable of dicts containing keys: month, emi, interest, principal, balance.
        path: Output file path (overwritten if exists).

    Side effects:
        Writes a file to disk.
    """
    with open(path, "w") as fh:
        fh.write("month,emi,interest,principal,balance\n")
        for r in rows:
            fh.write(f'{r["month"]},{r["emi"]},{r["interest"]},{r["principal"]},{r["balance"]}\n')


def summary(
    principal: float,
    annual_rate: float,
    tenure_months: int,
    start: Optional[date] = None,
) -> Dict[str, str]:
    """
    Produce a human-readable loan summary suitable for display.

    Args:
        principal: Loan amount.
        annual_rate: Annual interest rate in percent per year.
        tenure_months: Tenure in months.
        start: Start date used to compute the estimated last EMI month. Defaults to today.

    Returns:
        Dict containing:
            - principal (formatted INR)
            - rate (e.g. '10.5% p.a.')
            - tenure (e.g. '360 months')
            - emi (formatted INR)
            - total_interest (formatted INR)
            - total_payment (formatted INR)
            - last_emi (YYYY-MM)
            - currency ('INR')
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
