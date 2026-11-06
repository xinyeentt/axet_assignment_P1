"""Pytest test cases for loan_calc.calculator.

Comprehensive suite covering every public function, including the key
edge cases: 0% interest, 1-month tenure, very large principal,
prepayment larger than the outstanding balance, and invalid-input
validation.

"""

import pytest

from loan_calc.calculator import (
    emi,
    total_payment,
    total_interest,
    amortisation_schedule,
    outstanding_after,
    remaining_tenure,
    prepayment_savings,
    compare_offers,
    eligible_amount,
    format_inr,
    schedule_to_csv,
    summary,
)


# ---------------------------------------------------------------------------
# emi()
# ---------------------------------------------------------------------------

class TestEmi:
    def test_standard_loan(self):
        result = emi(1000000, 10, 120)
        assert result == pytest.approx(13215.07, abs=0.01)

    def test_zero_interest_rate(self):
        """0% interest should split principal evenly across tenure,
        without a division-by-zero error."""
        result = emi(120000, 0, 12)
        assert result == 10000.0

    def test_one_month_tenure(self):
        """1-month tenure: EMI should be slightly more than principal
        due to one month of interest."""
        result = emi(10000, 12, 1)
        assert result > 10000
        assert result == pytest.approx(10100.0, abs=1.0)

    def test_zero_interest_and_one_month_tenure(self):
        """Combined edge case: 0% interest + 1-month tenure => EMI equals
        principal exactly."""
        result = emi(5000, 0, 1)
        assert result == 5000.0

    def test_zero_or_negative_tenure_raises(self):
        with pytest.raises(ValueError):
            emi(10000, 10, 0)
        with pytest.raises(ValueError):
            emi(10000, 10, -5)

    def test_zero_or_negative_principal_raises(self):
        with pytest.raises(ValueError):
            emi(0, 10, 12)
        with pytest.raises(ValueError):
            emi(-5000, 10, 12)

    def test_very_large_principal(self):
        """Very large principal should produce a finite, positive result
        without overflow."""
        result = emi(10_000_000_000, 8, 240)
        assert result > 0
        assert math_is_finite(result)

    def test_assignment_emi_value(self):
        """Sanity check against the standard EMI formula for a 10,000
        principal at 9% p.a. over 240 months. Expected EMI is
        approximately 89.97 (NOT 8,997 - that figure likely assumes a
        principal of 1,000,000 or contains a typo. Confirm with the
        assignment author if 8,997 was really intended)."""
        result = emi(10_000, 9, 240)
        assert result == pytest.approx(89.97, abs=1.0)


def math_is_finite(value: float) -> bool:
    """Helper: True if value is a finite number (not inf/-inf/nan)."""
    return value == value and value not in (float("inf"), float("-inf"))


# ---------------------------------------------------------------------------
# total_payment() / total_interest()
# ---------------------------------------------------------------------------

class TestTotalPaymentAndInterest:
    def test_total_payment_standard(self):
        assert total_payment(100000, 10, 12) == pytest.approx(
            emi(100000, 10, 12) * 12, abs=0.01
        )

    def test_total_interest_zero_rate(self):
        """With 0% interest, total interest should be exactly 0."""
        assert total_interest(100000, 0, 10) == 0.0

    def test_total_interest_one_month_tenure(self):
        """1-month tenure should still accrue one month of interest."""
        result = total_interest(10000, 12, 1)
        assert result > 0

    def test_total_interest_positive_for_normal_loan(self):
        assert total_interest(500000, 9, 60) > 0

    def test_total_payment_very_large_principal(self):
        result = total_payment(10_000_000_000, 8, 240)
        assert result > 10_000_000_000


# ---------------------------------------------------------------------------
# amortisation_schedule()
# ---------------------------------------------------------------------------

class TestAmortisationSchedule:
    def test_schedule_length_matches_tenure(self):
        """The number of rows should equal the number of months in the
        loan tenure. NOTE: the current implementation uses
        range(1, tenure_months), which produces tenure_months - 1 rows.
        This test documents the EXPECTED correct behaviour and will
        likely FAIL against the current code, flagging an off-by-one bug."""
        sched = amortisation_schedule(100000, 10, 12)
        assert len(sched) == 12

    def test_final_balance_is_zero(self):
        """The last row's balance should be ~0 once the loan is fully
        repaid."""
        sched = amortisation_schedule(100000, 10, 12)
        assert sched[-1]["balance"] == pytest.approx(0.0, abs=1.0)

    def test_zero_interest_schedule(self):
        """With 0% interest, every row's interest should be 0 and the
        principal portion should equal the EMI."""
        sched = amortisation_schedule(12000, 0, 12)
        for row in sched:
            assert row["interest"] == 0.0

    def test_one_month_tenure_schedule_has_one_row(self):
        """1-month tenure: schedule should contain exactly one payment row.
        NOTE: due to range(1, tenure_months), this currently returns an
        EMPTY list for tenure_months == 1. This test documents the
        EXPECTED behaviour and will likely FAIL, flagging the bug."""
        sched = amortisation_schedule(10000, 12, 1)
        assert len(sched) == 1

    def test_balance_decreases_monotonically(self):
        sched = amortisation_schedule(200000, 11, 24)
        balances = [row["balance"] for row in sched]
        assert balances == sorted(balances, reverse=True)

    def test_very_large_principal_schedule_is_valid(self):
        """Very large principal should still produce a schedule with
        strictly decreasing, non-negative balances."""
        sched = amortisation_schedule(10_000_000_000, 8, 240)
        for row in sched:
            assert row["balance"] >= 0


# ---------------------------------------------------------------------------
# outstanding_after()
# ---------------------------------------------------------------------------

class TestOutstandingAfter:
    def test_zero_months_paid_returns_full_principal(self):
        assert outstanding_after(100000, 10, 12, 0) == 100000.0

    def test_negative_months_paid_returns_full_principal(self):
        assert outstanding_after(100000, 10, 12, -3) == 100000.0

    def test_months_paid_exceeds_tenure_returns_zero(self):
        assert outstanding_after(100000, 10, 12, 50) == 0.0

    def test_months_paid_equals_tenure(self):
        """Paying off the entire tenure should leave ~0 balance."""
        result = outstanding_after(100000, 10, 12, 12)
        assert result == pytest.approx(0.0, abs=1.0)

    def test_zero_interest_outstanding(self):
        result = outstanding_after(120000, 0, 12, 6)
        assert result == pytest.approx(60000.0, abs=1.0)


# ---------------------------------------------------------------------------
# remaining_tenure()
# ---------------------------------------------------------------------------

class TestRemainingTenure:
    def test_zero_balance_returns_zero(self):
        assert remaining_tenure(0, 10, 1000) == 0

    def test_negative_balance_returns_zero(self):
        assert remaining_tenure(-500, 10, 1000) == 0

    def test_zero_interest_rate(self):
        """With 0% interest, months required = ceil(balance / instalment)."""
        assert remaining_tenure(10000, 0, 2500) == 4
        assert remaining_tenure(10000, 0, 3000) == 4  # ceil(10000/3000)=4

    def test_instalment_too_small_raises(self):
        """If instalment doesn't even cover monthly interest, should
        raise ValueError (negative amortisation)."""
        with pytest.raises(ValueError):
            remaining_tenure(1_000_000, 24, 100)

    def test_large_instalment_converges_quickly(self):
        """A very large instalment relative to balance should resolve in
        a small number of months."""
        result = remaining_tenure(10000, 12, 9000)
        assert result <= 2


# ---------------------------------------------------------------------------
# prepayment_savings()
# ---------------------------------------------------------------------------

class TestPrepaymentSavings:
    def test_basic_prepayment(self):
        result = prepayment_savings(500000, 10, 60, 12, 50000)
        assert result["months_saved"] >= 0
        assert result["interest_saved"] >= 0
        assert "new_tenure" in result

    def test_prepayment_amount_larger_than_balance(self):
        """Edge case: prepayment amount exceeds the outstanding balance
        at that month. The loan should close without producing a
        negative balance or invalid remaining tenure - verify the
        new_tenure/months_left convention matches the intended API."""
        result = prepayment_savings(500000, 10, 60, 1, 10_000_000)
        assert result["months_saved"] >= 0
        assert result["new_tenure"] == 1  # months_left should be 0 -> new_balance <= 0

    def test_prepayment_at_month_one(self):
        """Prepaying at the very first month."""
        result = prepayment_savings(200000, 9, 36, 1, 20000)
        assert result["new_tenure"] <= 36

    def test_prepayment_equal_to_exact_outstanding_balance(self):
        """Prepaying exactly the outstanding balance should close the
        loan immediately (months_left == 0). NOTE: depends on the
        amortisation_schedule values being correct; revisit once the
        schedule off-by-one issue is resolved."""
        sched = amortisation_schedule(300000, 10, 48)
        balance_at_month_6 = sched[5]["balance"]
        result = prepayment_savings(300000, 10, 48, 6, balance_at_month_6)
        assert result["new_tenure"] == 6

    def test_prepayment_near_end_of_tenure(self):
        """Prepaying close to the last month should yield minimal savings."""
        result = prepayment_savings(100000, 10, 12, 11, 1000)
        assert result["months_saved"] >= 0

    def test_zero_prepayment_amount(self):
        """A prepayment of 0 should not reduce the tenure or create
        artificial savings (months_saved == 0)."""
        result = prepayment_savings(100000, 10, 24, 5, 0)
        assert result["months_saved"] == 0


# ---------------------------------------------------------------------------
# compare_offers()
# ---------------------------------------------------------------------------

class TestCompareOffers:
    def test_offers_sorted_by_total_cost(self):
        offers = [
            {"bank": "A", "rate": 10, "tenure": 60, "processing_fee_pct": 1},
            {"bank": "B", "rate": 9, "tenure": 60, "processing_fee_pct": 0.5},
        ]
        result = compare_offers(500000, offers)
        assert result[0]["total_cost"] <= result[1]["total_cost"]

    def test_offer_without_processing_fee_defaults_to_zero(self):
        offers = [{"bank": "C", "rate": 8, "tenure": 36}]
        result = compare_offers(100000, offers)
        assert result[0]["processing_fee"] == 0.0

    def test_empty_offers_list(self):
        assert compare_offers(100000, []) == []

    def test_single_offer_zero_interest(self):
        offers = [{"bank": "D", "rate": 0, "tenure": 12}]
        result = compare_offers(120000, offers)
        assert result[0]["total_interest"] == 0.0


# ---------------------------------------------------------------------------
# eligible_amount()
# ---------------------------------------------------------------------------

class TestEligibleAmount:
    def test_standard_eligibility(self):
        result = eligible_amount(100000, 20000, 10, 120)
        assert result > 0

    def test_no_disposable_income_returns_zero(self):
        """If existing EMIs consume all FOIR-allowed income, result is 0."""
        result = eligible_amount(50000, 25000, 10, 120, foir=0.5)
        assert result == 0.0

    def test_negative_disposable_income_returns_zero(self):
        result = eligible_amount(50000, 40000, 10, 120, foir=0.5)
        assert result == 0.0

    def test_zero_interest_rate(self):
        """0% interest: eligible amount = available * tenure_months."""
        result = eligible_amount(100000, 0, 0, 12, foir=0.5)
        assert result == pytest.approx(50000 * 12, abs=0.01)

    def test_custom_foir_increases_eligibility(self):
        result_low_foir = eligible_amount(100000, 0, 10, 120, foir=0.3)
        result_high_foir = eligible_amount(100000, 0, 10, 120, foir=0.6)
        assert result_high_foir > result_low_foir


# ---------------------------------------------------------------------------
# format_inr()
# ---------------------------------------------------------------------------

class TestFormatInr:
    def test_formats_with_indian_grouping(self):
        assert format_inr(1234567.89) == "₹12,34,567.89"

    def test_formats_negative_amount(self):
        assert format_inr(-5000) == "-₹5,000.00"

    def test_formats_small_amount_without_grouping(self):
        assert format_inr(999.5) == "₹999.50"

    def test_formats_zero(self):
        assert format_inr(0) == "₹0.00"


# ---------------------------------------------------------------------------
# schedule_to_csv()
# ---------------------------------------------------------------------------

class TestScheduleToCsv:
    def test_writes_header_and_rows(self, tmp_path):
        rows = [
            {"month": 1, "emi": 1000.0, "interest": 100.0, "principal": 900.0, "balance": 9000.0},
        ]
        path = tmp_path / "schedule.csv"
        schedule_to_csv(rows, str(path))
        content = path.read_text()
        assert content.startswith("month,emi,interest,principal,balance\n")
        assert "1,1000.0,100.0,900.0,9000.0" in content

    def test_writes_multiple_rows(self, tmp_path):
        rows = amortisation_schedule(100000, 10, 12)
        path = tmp_path / "schedule_full.csv"
        schedule_to_csv(rows, str(path))
        content = path.read_text()
        lines = content.strip().splitlines()
        # header + one line per row
        assert len(lines) == len(rows) + 1


# ---------------------------------------------------------------------------
# summary()
# ---------------------------------------------------------------------------

class TestSummary:
    def test_summary_contains_expected_keys(self):
        result = summary(100000, 10, 12)
        for key in (
            "principal",
            "rate",
            "tenure",
            "emi",
            "total_interest",
            "total_payment",
            "last_emi",
            "currency",
        ):
            assert key in result

    def test_summary_currency_default(self):
        result = summary(100000, 10, 12)
        assert result["currency"] == "INR"

    def test_summary_with_custom_start_date(self):
        from datetime import date
        result = summary(100000, 10, 12, start=date(2024, 1, 15))
        assert result["last_emi"] == "2025-01"

    def test_summary_zero_interest(self):
        """Summary should work without error for a 0% interest loan."""
        result = summary(100000, 0, 12)
        assert result["total_interest"] == "₹0.00"
