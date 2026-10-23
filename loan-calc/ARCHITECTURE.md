# Loan Calculator Architecture

This repository implements a small loan/EMI calculation library plus (optionally) a CLI layer. The core logic lives in:

- `loan_calc/calculator.py` — pure functions for EMI, interest, amortization schedules, prepayment/tenure effects, eligibility, and offer comparison.

All functions are deterministic and side-effect free **except** CSV generation (`schedule_to_csv`).

---

## Module: `loan_calc.calculator`

### Constants
- `DEFAULT_CURRENCY = "INR"`
  - Used by `summary()` to label currency.

---

## Helper functions

### `_monthly_rate(annual_rate)`
**Signature:** `def _monthly_rate(annual_rate) -> float`

**Purpose:** Convert an annual nominal interest rate (percent per year) into a monthly periodic rate.

**Logic:**
- `r = round(annual_rate / 1200, 4)`

**Inputs:**
- `annual_rate` (number): e.g., `10.5` meaning 10.5% p.a.

**Outputs:**
- Monthly rate `r` rounded to 4 decimals.

**Notes / edge cases:**
- If `annual_rate` is `0`, this returns `0.0` (exactly, given the arithmetic and rounding).

---

## EMI and aggregate cost functions

### `emi(principal, annual_rate, tenure_months)`
**Signature:** `def emi(principal, annual_rate, tenure_months) -> float`

**Purpose:** Compute the fixed monthly payment (EMI) for a fully amortizing loan.

**Validation:**
- Raises `ValueError("tenure must be positive")` if `tenure_months <= 0`
- Raises `ValueError("principal must be positive")` if `principal <= 0`

**Logic:**
1. `r = _monthly_rate(annual_rate)`
2. If `r == 0`, EMI is straight-line: `principal / tenure_months`
3. Else use standard amortization formula:
   - `f = (1 + r) ** tenure_months`
   - `emi = principal * r * f / (f - 1)`

**Rounding:**
- Result rounded to 2 decimals.

**Inputs:**
- `principal` (number): loan amount
- `annual_rate` (number): percent per year
- `tenure_months` (int): number of monthly payments

**Outputs:**
- EMI amount rounded to 2 decimals.

---

### `total_payment(principal, annual_rate, tenure_months)`
**Signature:** `def total_payment(principal, annual_rate, tenure_months) -> float`

**Purpose:** Total paid over the entire tenure (sum of EMI payments).

**Logic:**
- `round(emi(...) * tenure_months, 2)`

**Inputs/Outputs:**
- Same domain as `emi`
- Returns total amount rounded to 2 decimals.

---

### `total_interest(principal, annual_rate, tenure_months)`
**Signature:** `def total_interest(principal, annual_rate, tenure_months) -> float`

**Purpose:** Total interest paid over the life of the loan.

**Logic:**
- `total_interest = total_payment(...) - principal`
- rounded to 2 decimals

---

## Amortization schedule

### `amortisation_schedule(principal, annual_rate, tenure_months)`
**Signature:** `def amortisation_schedule(principal, annual_rate, tenure_months) -> list[dict]`

**Purpose:** Produce a per-month amortization breakdown: EMI, interest portion, principal portion, and remaining balance.

**Inputs:**
- `principal` (number)
- `annual_rate` (number)
- `tenure_months` (int)

**Outputs:**
- A list of dictionaries with length **`tenure_months - 1`** (see note below), each row containing:
  - `"month"`: 1-based month index
  - `"emi"`: instalment amount used for that month
  - `"interest"`: interest portion for that month
  - `"principal"`: principal portion for that month
  - `"balance"`: remaining balance after the principal portion, clamped to at least `0.0`

**Logic (important details / potential pitfalls):**
- Computes:
  - `r = _monthly_rate(annual_rate)`
  - `instalment = emi(principal, annual_rate, tenure_months)`
  - `balance = principal`
- Iterates `for month in range(1, tenure_months):`
  - This iterates **months 1..tenure_months-1**, not including the final month.
- Each iteration computes:
  - `interest = round(balance * r, 2)`
  - `principal_part = round(instalment - interest, 2)`
- There is a branch intended to adjust the last payment:
  ```python
  if month == tenure_months:
      principal_part = round(balance, 2)
      instalment_amt = round(principal_part + interest, 2)
  else:
      instalment_amt = instalment
  ```
  However, since the loop never reaches `month == tenure_months`, that “last month adjustment” branch is effectively unreachable.
- Updates:
  - `balance = round(balance - principal_part, 2)`
  - rows.append(... "balance": max(balance, 0.0))

**Net effect:**
- The schedule’s length is `tenure_months - 1`, and it likely omits the true final payment month. This is inconsistent with the typical “tenure months” expectation.

**Consumers:**
- Used by `outstanding_after()` and `prepayment_savings()`.

---

### `outstanding_after(principal, annual_rate, tenure_months, months_paid)`
**Signature:** `def outstanding_after(principal, annual_rate, tenure_months, months_paid) -> float`

**Purpose:** Return remaining outstanding balance after a given number of months paid.

**Logic:**
- If `months_paid <= 0`: return `round(principal, 2)`
- Compute `sched = amortisation_schedule(...)`
- If `months_paid > len(sched)`: return `0.0`
- Else return `sched[months_paid - 1]["balance"]`

**Note (depends on schedule length):**
- Because `amortisation_schedule()` returns `tenure_months - 1` rows, requesting outstanding after exactly the full tenure may behave like “months_paid > len(sched)” → `0.0`.

---

## Tenure recomputation

### `remaining_tenure(balance, annual_rate, instalment)`
**Signature:** `def remaining_tenure(balance, annual_rate, instalment) -> int`

**Purpose:** Given a remaining principal balance, interest rate, and a fixed monthly instalment (EMI), compute how many months are needed to fully repay.

**Inputs:**
- `balance` (number): remaining principal outstanding
- `annual_rate` (number): percent per year
- `instalment` (number): monthly payment to use

**Validation & edge handling:**
- If `balance <= 0`: return `0`
- `r = annual_rate / 100` (NOTE: this treats rate as “%/100”, not “/1200”)
- If `r == 0`: return `ceil(balance / instalment)` (simple division)
- If `instalment <= balance * r`: raise `ValueError("instalment too small to repay the loan")`

**Logic (logarithmic amortization inversion):**
- `n = -log(1 - balance * r / instalment) / log(1 + r)`
- return `ceil(n)`

**Potential inconsistency:**
- `remaining_tenure()` uses `r = annual_rate / 100`, while the rest of the module uses `_monthly_rate(annual_rate) = annual_rate / 1200`.
- This means `remaining_tenure()` is likely using an **incorrect interest rate basis** (monthly vs annual), causing incorrect tenure calculations unless the caller passes values differently than intended.

**Consumers:**
- Used by `prepayment_savings()`.

---

## Prepayment and eligibility logic

### `prepayment_savings(principal, annual_rate, tenure_months, prepay_month, prepay_amount)`
**Signature:** `def prepayment_savings(...) -> dict`

**Purpose:** Model a **lump-sum prepayment** occurring at `prepay_month`, while keeping EMI constant and shortening tenure.

**Docstring:**
- “Keep the same EMI after a lump-sum prepayment and shorten the tenure.”

**Outputs:**
Returns a dict containing:
- `"emi"`: original EMI value (fixed)
- `"months_saved"`: how many months of tenure are removed vs original schedule
- `"new_tenure"`: `prepay_month + months_left`
- `"interest_saved"` (rounded): difference between original total interest and new computed total interest
- `"interest_paid_before_prepayment"` (rounded): sum of interest components up to (but excluding) the prepayment month, based on current schedule slicing

**Logic details:**
1. `instalment = emi(...)`
2. `sched = amortisation_schedule(...)`
3. `balance = sched[prepay_month - 1]["balance"]`
   - Assumes `prepay_month - 1` is within schedule bounds.
4. `new_balance = balance - prepay_amount`
5. If `new_balance <= 0`: `months_left = 0`
   - else: `months_left = remaining_tenure(new_balance, annual_rate, instalment)`
6. `original_left = tenure_months - prepay_month`
7. Compute interest:
   - `interest_paid_so_far = sum(row["interest"] for row in sched[:prepay_month])`
   - `original_interest = total_interest(...)`
8. Compute a new “total interest” approximation:
   - `new_total = instalment * prepay_month + prepay_amount + instalment * months_left`
   - `new_interest = new_total - principal`
9. Return the dict with `round(...)` on money fields.

**Important quirks / correctness risks:**
- Relies on `amortisation_schedule()` which (as written) omits the final month and has an unreachable “last month adjustment” branch.
- Relies on `remaining_tenure()` which likely uses the wrong rate basis (`annual_rate/100` vs monthly rate).
- Mixes schedule-derived interest paid so far with a closed-form recomputation for later cost that may not match the schedule’s amortization conventions.

---

### `compare_offers(principal, offers)`
**Signature:** `def compare_offers(principal, offers) -> list[dict]`

**Purpose:** Given multiple loan offers, compute and rank them by total cost = total interest + processing fee.

**Inputs:**
- `principal` (number)
- `offers`: iterable of dict-like objects, each containing:
  - `"bank"` (string)
  - `"rate"` (number): annual interest %
  - `"tenure"` (int): months
  - Optional `"processing_fee_pct"` (number): percent of principal

**Logic:**
For each offer:
1. `e = emi(principal, o["rate"], o["tenure"])`
2. `ti = total_interest(principal, o["rate"], o["tenure"])`
3. `fee = o.get("processing_fee_pct", 0) * principal / 100`
4. Append:
   - `"bank"`, `"emi"`, `"total_interest"`, `"processing_fee"`, `"total_cost" = ti + fee`

Finally:
- sort by `"total_cost"` ascending
- return list.

**Outputs:**
- list of offers ranked cheapest first.

---

### `eligible_amount(monthly_income, existing_emis, annual_rate, tenure_months, foir=0.5)`
**Signature:** `def eligible_amount(monthly_income, existing_emis, annual_rate, tenure_months, foir=0.5) -> float`

**Purpose:** Estimate maximum principal a borrower can take given:
- monthly income,
- existing monthly EMIs,
- FOIR (fixed obligation to income ratio),
- interest and tenure.

**Inputs:**
- `monthly_income` (number)
- `existing_emis` (number): sum of existing EMI commitments
- `annual_rate` (number): percent per year
- `tenure_months` (int)
- `foir` (number, default `0.5`): maximum allowable fraction of income for EMI payments

**Outputs:**
- Eligible principal (rounded to 2 decimals).

**Logic:**
1. `available = monthly_income * foir - existing_emis`
2. If `available <= 0`: return `0.0`
3. Convert annual rate to monthly:
   - `r = _monthly_rate(annual_rate)`
4. If `r == 0`: return `available * tenure_months`
5. Else use EMI inversion formula (solving principal from EMI):
   - `f = (1 + r) ** tenure_months`
   - `eligible = available * (f - 1) / (r * f)`
6. Return rounded.

---

## Formatting & export

### `format_inr(amount)`
**Signature:** `def format_inr(amount) -> str`

**Purpose:** Format a numeric value into Indian INR style with comma grouping and 2 decimal places.

**Logic:**
- Tracks negativity; uses absolute value.
- Rounds to 2 decimals.
- Splits whole/frac from formatted `f"{amount:.2f}"`.
- For Indian grouping:
  - if more than 3 digits in whole part:
    - split into head and tail
    - then repeatedly take 2-digit groups for the head
    - join with commas and append tail
- Return `(" - " if neg) + "₹" + whole + "." + frac`

---

### `schedule_to_csv(rows, path)`
**Signature:** `def schedule_to_csv(rows, path) -> None`

**Purpose:** Write amortization schedule rows to a CSV file.

**Inputs:**
- `rows`: list of dicts with keys `month, emi, interest, principal, balance`
- `path`: file path to write

**Side effects:**
- Creates/overwrites the file at `path`.

**CSV schema:**
- Header: `month,emi,interest,principal,balance`
- Each row written as:
  - `f'{r["month"]},{r["emi"]},{r["interest"]},{r["principal"]},{r["balance"]}\n'`

---

## Human-readable summary

### `summary(principal, annual_rate, tenure_months, start=None)`
**Signature:** `def summary(principal, annual_rate, tenure_months, start=None) -> dict`

**Purpose:** Return a compact human-readable summary of the loan, including EMI and estimated end month/year.

**Inputs:**
- `principal` (number)
- `annual_rate` (number)
- `tenure_months` (int)
- `start` (date, optional): defaults to `date.today()`.

**Outputs:**
Dict with:
- `"principal"`: formatted INR
- `"rate"`: string like `"{annual_rate}% p.a."`
- `"tenure"`: string like `"{tenure_months} months"`
- `"emi"`: formatted INR
- `"total_interest"`: formatted INR
- `"total_payment"`: formatted INR
- `"last_emi"`: `YYYY-MM` string
- `"currency"`: `"INR"`

**Logic:**
- Compute `e = emi(...)`
- Compute calendar end date:
  - `end_year = start.year + (start.month - 1 + tenure_months) // 12`
  - `end_month = (start.month - 1 + tenure_months) % 12 + 1`
- Note: This assumes each tenure month maps cleanly to calendar months and reports the month the last EMI is due.

---

## Function call graph (high level)

- `_monthly_rate()` is used by:
  - `emi()` and `eligible_amount()` and `amortisation_schedule()`
- `emi()` is used by:
  - `total_payment()`, `compare_offers()`, `amortisation_schedule()`, `prepayment_savings()`, `summary()`
- `total_interest()` is used by:
  - `prepayment_savings()`, `compare_offers()`, `summary()`
- `amortisation_schedule()` is used by:
  - `outstanding_after()`, `prepayment_savings()`
- `remaining_tenure()` is used by:
  - `prepayment_savings()`

---

## Correctness notes (based on the current code)
Two areas may produce incorrect results relative to standard loan math:

1. **`amortisation_schedule()` loop bounds**
   - It loops `range(1, tenure_months)` (excludes the month `tenure_months`), so it omits the final month.
   - The “if month == tenure_months” adjustment is unreachable.

2. **`remaining_tenure()` rate basis**
   - Uses `r = annual_rate / 100` but should likely use monthly rate (consistent with `_monthly_rate` which divides by 1200).
   - This mismatch likely affects computed `months_left` in `prepayment_savings()`.

These issues don’t affect the documentation mechanically, but they are important for anyone interpreting the outputs.
