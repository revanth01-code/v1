# backend/app/modules/tax/tax_rules.py

# 중앙 집중식 세금 규칙 설정 (Centralized Tax Rules Configuration)
TAX_RULES_METADATA = {
    "financial_year": "2026-2027",
    "rule_identifier": "in_tax_rules_v1",
    "rule_source": "Income Tax Act, 1961 (India)",
    "last_reviewed_date": "2026-08-30",
}

# Indian Tax Limits
SECTION_80C_MAX_LIMIT = 150000.0

TAXATION_EXPLANATIONS = {
    "equity": (
        "Equity Mutual Funds: Short-term gains (holding period <= 12 months) are taxed at 20%. "
        "Long-term gains (holding period > 12 months) are taxed at 12.5% for gains exceeding 1.25 Lakhs in a financial year."
    ),
    "debt": (
        "Debt Mutual Funds: Gains are added directly to the user's taxable income and taxed according to "
        "their personal income tax slab rate, regardless of the holding period (Finance Act 2023 rule)."
    ),
    "elss": (
        "Equity Linked Savings Scheme (ELSS): Offers tax deductions under Section 80C up to 1.5 Lakhs per year. "
        "ELSS investments are subject to a mandatory lock-in period of 3 years, which is the shortest among tax-saving options."
    )
}
