# Prompt Log — loan_calc.calculator Review & Fix Session

This log documents the sequence of user prompts and the corresponding
actions taken during this session, covering documentation, test
authoring, defect discovery, and fixes applied to
`loan_calc/calculator.py`.

---

## 1. Prompt: "explain each function"
**Action:** Read `loan_calc/calculator.py` and produced a plain-language
explanation of every function's purpose, parameters, and return values,
including a note flagging a suspected off-by-one issue in
`amortisation_schedule()`.

---

## 2. Prompt: "without changing the code for calculator.py, generate
docstrings and type hints for every public function. let me review each
suggestion before accepting it"
**Action:** Drafted Google-style docstrings (Args/Returns/Raises) and
type hints for all 12 public functions and presented them for review
before applying.

## 3. Prompt: "Apply all suggestions"
**Action:** Applied docstrings and type hints to `calculator.py` via
`replace_in_file`. A stray `with` token was accidentally introduced
during the edit, causing a syntax error; it was immediately detected
(Pylance error) and fixed in a follow-up `replace_in_file`. Verified the
file compiled cleanly with `python -m py_compile`.

---

## 4. Prompt: "using pytest, propose test cases, including edge cases:
0% interest, 1-month tenure, very large principal prepayment larger than
the balance, don't need to run them yet"
**Action:** Began drafting a pytest suite covering all public functions
and the requested edge cases. The first draft was not saved by the user
(write declined).

## 5. Prompt: "how many test cases are there?"
**Action:** Provided a breakdown table of the drafted test counts per
function/class.

## 6. Prompt (via ask_followup_question choice): "Show the full draft
content first for review before writing the file"
**Action:** Presented the complete draft test suite content for review,
with reasoning/comments on which assertions might reveal real bugs vs.
test-authoring mistakes.

## 7. Feedback: Recommendation to trim the suite to ~20-25 focused tests
covering normal cases, edge cases, validation, and major features; cut
or combine redundant cases per function.
**Action:** Rewrote a smaller, trimmed test file.

## 8. Feedback: "sorry keep your comprehensive test suite rather than
cut it down too aggressively... Keep the important edge cases... I would
also keep tests for every public function... Verify the required EMI
result [10,000 @ 9% / 240 months ≈ 89.97, flag the 8,997 assignment value
as a likely typo]... Do not modify the test merely to match the current
implementation."
**Action:** Restored and expanded the test suite back to a comprehensive
~54-test version covering all 12 public functions, including the
specifically requested edge cases (0% interest, 1-month tenure, very
large principal, prepayment larger than balance, invalid inputs), plus
an explicit sanity-check test (`test_assignment_emi_value`) verifying the
correct EMI formula result against the user-supplied figures. Saved to
`loan-calc/tests/test_calculator.py`.

---

## 9. Prompt: "run tests, . Save the initial failures so you can explain
which tests revealed which defects, don't change the code yet until i
review the failures."
**Action:** Ran `pytest -v`, saved output to
`loan-calc/test_results_initial.txt`. Result: 46 passed, 8 failed.
Analyzed each failure and reported:
- `test_standard_loan` — test's own expected value was wrong (likely a
  manual calc error) — flagged as a test defect, not a code bug (at the
  time; later re-investigated, see below).
- 3x `TestAmortisationSchedule` failures — confirmed the
  `range(1, tenure_months)` off-by-one bug (schedule always one row
  short; broke the 1-month case entirely).
- 3x `TestPrepaymentSavings` failures — confirmed `remaining_tenure()`
  used `annual_rate / 100` instead of the `annual_rate / 1200` monthly
  rate convention used elsewhere, causing false `ValueError`s.
- `test_summary_zero_interest` — minor floating-point rounding residual
  (`-₹0.04` instead of `₹0.00`) for a 0%-interest loan.
No code changes made at this stage, per instruction.

---

## 10. Prompt: "ok first fix the amortisation schedule: change the loop
so it generates one row for every month, including the final payment.
Verify the final balance and one-month case."
**Action:** Changed `range(1, tenure_months)` → `range(1, tenure_months +
1)` in `amortisation_schedule()`. Verified via targeted test run
(`-k AmortisationSchedule`): all 6 related tests now pass, including the
previously-failing final-balance and one-month cases. Re-ran the full
suite to confirm no regressions (49 passed, 5 failed — remaining
failures unrelated to this fix). Saved to
`loan-calc/test_results_after_fix.txt` /
`loan-calc/test_results_full_after_fix.txt`.

---

## 11. Prompt: "ok next fix remaining_tenure() and find where the
annual interest rate is converted into a monthly rate. Fix the
implementation, not the tests. If it currently uses annual_rate / 100,
change it to the consistent monthly-rate conversion, annual_rate / 1200,
assuming the function accepts an annual percentage rate like emi() does."
**Action:** Changed `r = annual_rate / 100` → `r = _monthly_rate
(annual_rate)` in `remaining_tenure()`. Re-ran full suite: 52 passed, 2
failed (all 6 `TestPrepaymentSavings` cases now pass; no regressions).
Saved to `loan-calc/test_results_after_remaining_tenure_fix.txt`.

---

## 12. Prompt: "Please investigate the two remaining failures
carefully... Do not assume either value is correct without independently
calculating the expected EMI... If the test expectation is incorrect,
explain why before changing it. If the implementation is incorrect, fix
the code. Do not modify the test merely to match the current
implementation... Trace how summary() calculates total interest...
Fix the underlying cause while preserving correct behavior for non-zero
interest loans."
**Action (after a brief tool-use hiccup and resumption):**
- Independently recomputed the EMI for principal=1,000,000, rate=10%,
  tenure=120 using both the *precise* monthly rate (0.008333...) and the
  *code's rounded* rate (0.0083, from `round(annual_rate/1200, 4)`).
  Precise rate → 13215.07 (matches the test's expectation exactly).
  Rounded rate → 13192.93 (matches the buggy implementation's output).
  Conclusion: the **test was correct**; the bug is `_monthly_rate()`
  prematurely rounding the rate before compounding.
- Traced `summary()` → `total_interest()` → `total_payment()` →
  `emi()` for a 0%-interest loan and found that rounding the EMI to
  cents *before* multiplying by `tenure_months` produces a small
  residual (100000/12 rounds to 8333.33, ×12 = 99999.96, a 4-cent
  shortfall) instead of the exact principal.
- Presented both findings and proposed fixes via
  `ask_followup_question` before making any changes.

---

## 13. User instruction (new task continuation): "ok please fix
monthly_rate() precision loss: round(annual_rate / 1200, 4) prematurely
rounds the monthly rate, causing incorrect EMI calculations."
**Action:** Changed `_monthly_rate()` from `round(annual_rate / 1200, 4)`
→ `annual_rate / 1200` (no rounding). Re-ran full suite: `test_standard_
loan` now passes. This surfaced one *new* failure
(`test_zero_prepayment_amount`, `months_saved` off by one) and left
`test_summary_zero_interest` unchanged. Reported both via
`ask_followup_question`.

## 14. Prompt (via ask_followup_question choice): "Fix both now"
**Action:**
- Diagnosed the `months_saved` discrepancy: feeding a cents-rounded
  instalment back into the closed-form logarithmic month formula
  produces tiny floating-point noise (e.g. `19.000012` instead of
  exactly `19`), which `math.ceil()` then incorrectly rounds up by a
  whole extra month. Fixed by rounding `n` to 4 decimal places before
  `math.ceil()` in `remaining_tenure()`.
- Fixed `total_payment()` to sum the amortisation schedule's per-month
  EMI column (which already correctly absorbs rounding into the final
  instalment) instead of naively multiplying the rounded EMI by
  `tenure_months`. Verified via a 0%-interest 12-month example: the
  schedule sums to exactly 100000.00, resolving the 4-cent residual.
- Re-ran the full suite: one test (`test_total_payment_standard`) failed
  because it still asserted the old, now-outdated relationship
  `total_payment == emi * tenure_months`. Corrected the test's
  expectation to compare against the schedule-derived sum instead
  (a test-authoring fix, not a behavior compromise, since the
  implementation change was intentional and verified correct).
- Final full suite run: **54 passed, 0 failed**. Saved to
  `loan-calc/test_results_final.txt`.

---

## 15. Prompt: "ok what is the line coverage (pytest --cov)"
**Action:** Ran `pytest --cov=loan_calc --cov-report=term-missing`.
Result: **100% line coverage** (111/111 statements, 0 missed) across
`loan_calc/calculator.py` and `loan_calc/__init__.py`, with all 54 tests
passing. Saved to `loan-calc/test_coverage.txt`.

---

## 16. Prompt: "generate a prompt log"
**Action:** Created this file, `loan-calc/PROMPT_LOG.md`.

---

## Summary of Defects Found & Fixed

| # | Function | Defect | Fix |
|---|----------|--------|-----|
| 1 | `amortisation_schedule()` | Off-by-one loop (`range(1, tenure_months)`) produced one fewer row than the tenure, breaking the final payment and the 1-month case entirely | Changed to `range(1, tenure_months + 1)` |
| 2 | `remaining_tenure()` | Used `annual_rate / 100` as the monthly rate instead of the `/ 1200` convention used elsewhere, massively overstating interest and causing false `ValueError`s in `prepayment_savings()` | Changed to use `_monthly_rate(annual_rate)` |
| 3 | `_monthly_rate()` | Rounded the monthly rate to 4 decimal places *before* compounding, introducing a multi-rupee EMI error over long tenures | Removed the premature rounding; only final monetary outputs are rounded |
| 4 | `total_payment()` | Multiplied the cents-rounded EMI by `tenure_months`, producing a rounding-residual error (e.g. -4 cents for a 0%-interest loan) | Changed to sum the amortisation schedule's EMI column, which correctly absorbs rounding into the final instalment |
| 5 | `remaining_tenure()` (secondary) | `math
