# loan-calc — Architecture

## 1. Purpose

This module computes EMI, amortisation schedules and prepayment savings for retail loans. It can also compare loan offers from different banks by total cost, and estimate the maximum loan a borrower is eligible for based on their income. It would be used behind a loan calculator app, a bank's loan comparison page, or by anyone planning a home or personal loan.

## 2. Conventions

- **Interest rate:** `annual_rate` is passed as a percentage, so `9` means 9% per year. `_monthly_rate()` converts it to a monthly decimal rate by dividing by 1200: ÷100 turns the percentage into a decimal, and ÷12 turns the yearly rate into a monthly one. So 9% p.a. becomes 0.0075 per month. The rate is **not** rounded; only final money amounts are.
- **Tenure:** always in months (`240` = 20 years).
- **Money and rounding:** all amounts are in INR and rounded to 2 decimal places (paise). Because each month's interest and principal are rounded, tiny differences build up over the loan. The last instalment absorbs them, so it can differ by a few paise from the regular EMI.

## 3. How the functions fit together

```
summary ──────────► emi, total_interest, total_payment, format_inr
total_interest ───► total_payment ──► amortisation_schedule ──► emi ──► _monthly_rate
outstanding_after ► amortisation_schedule
prepayment_savings ► emi, amortisation_schedule, remaining_tenure, total_interest
compare_offers ───► emi, total_interest
eligible_amount ──► _monthly_rate
remaining_tenure ─► _monthly_rate
cli.py ───────────► summary, amortisation_schedule, prepayment_savings
```

`emi()` and `amortisation_schedule()` are the foundation. Almost every other function either calls them directly or builds on their results, so a bug in either one spreads to the totals, the prepayment figures and the offer comparison.

## 4. Functions

### Core calculations

#### `emi(principal, annual_rate, tenure_months)`
Calculates the equated monthly instalment, the fixed amount paid every month, using the standard EMI formula `P × r × (1+r)^n / ((1+r)^n − 1)`. Here P is the principal (the amount borrowed), r is the monthly interest rate and n is the number of months. It first checks that principal and tenure_months are positive and raises `ValueError` if not. If the rate is 0% (an interest-free loan), it simply divides the principal evenly across the tenure. The result is rounded to 2 decimal places.

#### `amortisation_schedule(principal, annual_rate, tenure_months)`
Builds a month-by-month repayment table: a list with one dict per month containing `month`, `emi`, `interest`, `principal` and `balance`. Each month, the interest is the remaining balance × the monthly rate, and the rest of the EMI goes towards the principal, which reduces the balance. In the final month it pays off exactly whatever balance is left, so the last EMI absorbs any rounding difference and the balance ends at 0.

#### `total_payment(...)` and `total_interest(...)`
`total_payment()` adds up the EMI column of the schedule to get the total amount repaid over the loan. It sums the schedule rather than multiplying EMI × months, so the slightly different last instalment is counted correctly. `total_interest()` is the total payment minus the principal, i.e. the cost of borrowing.

#### `outstanding_after(principal, annual_rate, tenure_months, months_paid)`
Returns how much is still owed after a given number of EMIs have been paid, by reading the balance from the schedule. If `months_paid` is 0 or negative, it returns the full principal. If it is more than the tenure, it returns 0.

### Prepayment

#### `remaining_tenure(balance, annual_rate, instalment)`
Works out how many more months it takes to pay off a balance at a fixed instalment. It solves the EMI formula backwards for n using logarithms, then rounds up to a whole month. Before rounding up, it rounds n to 4 decimal places, so tiny floating-point noise (e.g. 19.000012) doesn't add an extra month. For 0% interest it is simply balance ÷ instalment, rounded up. If the instalment doesn't even cover one month's interest, the loan can never be repaid, so it raises `ValueError`.

#### `prepayment_savings(principal, annual_rate, tenure_months, prepay_month, prepay_amount)`
Shows what happens if the borrower pays an extra lump sum after a given month. It assumes the borrower **keeps paying the same EMI**, so the prepayment shortens the tenure rather than lowering the EMI. It looks up the balance at `prepay_month`, subtracts the prepayment, and uses `remaining_tenure()` to find how many months are left. It returns the EMI, months saved, new tenure, interest saved, and interest already paid before the prepayment. If the prepayment clears the whole balance, the remaining months are 0.

### Comparison and eligibility

#### `compare_offers(principal, offers)`
Takes a list of loan offers, each with a bank name, rate, tenure and optional processing fee %, and works out the EMI, total interest, processing fee and total cost of each one for the same principal. Total cost = total interest + processing fee. The results are sorted cheapest first, so the best offer is at the top. A lower rate doesn't always win: a higher processing fee can outweigh it.

#### `eligible_amount(monthly_income, existing_emis, annual_rate, tenure_months, foir=0.5)`
Estimates the largest loan a borrower can take. FOIR (Fixed Obligation to Income Ratio) is the share of monthly income a lender allows to go towards EMIs, 50% by default. The spare EMI the borrower can afford is `income × FOIR − existing EMIs`. The EMI formula is then run in reverse to find the principal that this EMI would repay. If there is no spare income, it returns 0.

### Output helpers

#### `format_inr(amount)`
Formats a number as rupees using Indian digit grouping: the last three digits, then groups of two, e.g. `₹12,34,567.89` instead of `₹1,234,567.89`. Negative amounts get a leading minus sign.

#### `schedule_to_csv(rows, path)`
Writes an amortisation schedule to a CSV file with the header `month,emi,interest,principal,balance` and one line per month.

#### `summary(principal, annual_rate, tenure_months, start=None)`
Gives a readable overview of a loan as formatted strings: principal, rate, tenure, EMI, total interest, total payment, currency, and the month of the last EMI (`YYYY-MM`). The last EMI month is the start month plus the tenure. If no start date is given, it uses today's date.

### Entry point

#### `cli.py`
A command-line wrapper. It takes principal, annual rate and tenure as arguments and prints the `summary()` as JSON. `--schedule` also prints every row of the amortisation schedule. `--prepay-month` and `--prepay-amount` together also print the `prepayment_savings()` result.

## 5. Worked example

₹10,00,000 (10 lakh) at 9% p.a. for 240 months, starting November 2026:

| Item | Value |
|---|---|
| Monthly rate | 9 / 1200 = 0.0075 |
| EMI | ₹8,997.26 |
| Month 1 split | ₹7,500.00 interest + ₹1,497.26 principal |
| Last EMI (month 240) | ₹8,996.96, slightly lower because it absorbs rounding |
| Total interest | ₹11,59,342.10 |
| Total payment | ₹21,59,342.10 |
| Last EMI month | 2046-11 |

Early on, most of the EMI goes to interest (₹7,500 of ₹8,997 in month 1). By the end, almost all of it goes to principal (only ₹66.97 interest in month 240).

Prepaying ₹2,00,000 after month 24 while keeping the same EMI shortens the loan from 240 to **159 months** (81 months saved) and saves **₹5,28,777.76** in interest.

## 6. Bugs found and fixed

| # | Function | Symptom | Cause | Fix |
|---|---|---|---|---|
| 1 | `amortisation_schedule()` | Schedule was one month short; a 1-month loan returned an empty schedule; the final balance never reached 0 | The loop used `range(1, tenure_months)`, which stops one month early | Changed to `range(1, tenure_months + 1)` |
| 2 | `remaining_tenure()` | `prepayment_savings()` raised "instalment too small" or gave wrong months for normal loans | It calculated the monthly rate as `annual_rate / 100`, making it 12× too high | Use the shared `_monthly_rate()`, which divides by 1200 |
| 3 | `_monthly_rate()` | Wrong EMIs, e.g. ₹10L at 10% for 120 months gave ₹13,192.93 instead of ₹13,215.07 | The monthly rate was rounded to 4 decimal places before compounding (0.008333… → 0.0083) | Removed the early rounding; only final money amounts are rounded |
