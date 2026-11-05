# Assignment P1 — Understand, Test and Fix Legacy Code (`loan-calc`)

`loan-calc` is a small Python module for retail loan maths: EMI, amortisation
schedules, prepayment savings, offer comparison and loan eligibility. It was
handed over with no tests and no documentation, and users reported wrong
numbers for some loans.

This repo contains my work for Assignment P1: understanding the code with the
aXet Plugin chat, documenting it, writing a pytest suite, and fixing the bugs
that suite exposed.

## Results at a glance

| Acceptance criterion | Status | Evidence |
|---|---|---|
| All three seeded bugs found and fixed | ✅ | [Bugs fixed](#bugs-fixed) |
| Test suite passes with coverage ≥ 85% | ✅ 54 passed, 100% line coverage | [Run the tests](#run-the-tests) |
| EMI for ₹10,00,000 at 9% p.a. over 240 months = ₹8,997 (± 1) | ✅ ₹8,997.26 | `test_assignment_acceptance_emi` |
| ARCHITECTURE.md accurate and in my own words | ✅ | [ARCHITECTURE.md](loan-calc/loan-calc/loan_calc/ARCHITECTURE.md) |
| Prompt log records where the AI was wrong | ✅ | [PROMPT_LOG.md](PROMPT_LOG.md) |

## Repository layout

```
.
├── README.md                         ← you are here
├── PROMPT_LOG.md                     ← prompts used with aXet
└── loan-calc/loan-calc/
    ├── cli.py                        ← command-line entry point
    ├── requirements.txt
    ├── loan_calc/
    │   ├── __init__.py
    │   ├── calculator.py             ← all the loan maths
    │   └── ARCHITECTURE.md           ← what each function does and how they connect
    └── tests/
        └── test_calculator.py        ← pytest suite (54 tests)
```

## Setup

```bash
cd loan-calc/loan-calc
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## Run the tests

From `loan-calc/loan-calc`:

```bash
pytest --cov=loan_calc --cov-report=term-missing
```

Result: **54 passed, 100% line coverage** of `loan_calc`.

## Try the CLI

From `loan-calc/loan-calc`:

```bash
python cli.py 1000000 9 240                                           # summary
python cli.py 1000000 9 240 --schedule                                # + month-by-month schedule
python cli.py 1000000 9 240 --prepay-month 24 --prepay-amount 200000  # + prepayment savings
```

The first command prints an EMI of `₹8,997.26`.

## Bugs fixed

| # | Function | Symptom | Root cause | Fix | Commit |
|---|---|---|---|---|---|
| 1 | `amortisation_schedule()` | Schedule one row short; empty for a 1-month loan; final balance never reaches 0 | Loop used `range(1, tenure_months)` | `range(1, tenure_months + 1)` | `5669b5c` |
| 2 | `remaining_tenure()` | `prepayment_savings()` raised "instalment too small" for normal loans | Monthly rate computed as `annual_rate / 100` instead of `/ 1200` | Use the shared `_monthly_rate()` helper | `3c02578` |
| 3 | `_monthly_rate()` | Wrong EMIs for most rates, e.g. ₹10L @ 10% / 120 months gave ₹13,192.93 instead of ₹13,215.07 | Monthly rate rounded to 4 d.p. before compounding | Remove the early `round()`; round only final money values | `5d83f0b`* |

\* Commit `5d83f0b` also contains two smaller fixes found by the tests (not seeded bugs):

- `total_payment()` now sums the amortisation schedule instead of `EMI × months`, so a 0% loan no longer shows `-₹0.04` total interest.
- `remaining_tenure()` rounds `n` to 4 d.p. before `ceil()`, so floating-point noise (e.g. `19.000012`) no longer adds an extra month.

The 9% acceptance case passed even before bug 3 was fixed, because 9 / 1200 = 0.0075 is already exact at 4 decimal places. Bug 3 only shows up at other rates.

## How AI was used

Exploring the code, docstrings and test drafting were done with aXet Plugin chat.
Every suggestion was reviewed before accepting it, and the places where the AI
was wrong are recorded in [PROMPT_LOG.md](PROMPT_LOG.md).
