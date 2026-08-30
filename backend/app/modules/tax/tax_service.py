# backend/app/modules/tax/tax_service.py
from typing import Literal, Optional, Any
from pydantic import BaseModel, Field
from .tax_rules import TAX_RULES_METADATA, SECTION_80C_MAX_LIMIT, TAXATION_EXPLANATIONS

class TaxProfile(BaseModel):
    tax_regime: Literal["old", "new", "unknown"] = "unknown"
    annual_income_range: Literal["< 5L", "5L - 10L", "10L - 15L", "> 15L", "unknown"] = "unknown"
    existing_tax_saving_investments_range: float = Field(default=0.0, ge=0)
    existing_elss_investment_range: float = Field(default=0.0, ge=0)
    wants_tax_optimization: Optional[bool] = None
    financial_year: str = "2026-2027"

class TaxOpportunityService:
    @staticmethod
    def analyze_profile(profile: Optional[TaxProfile] = None) -> dict[str, Any]:
        """Analyzes user tax profile and returns educational opportunities and insights.
        
        This service DOES NOT file taxes or provide personal tax/legal advice.
        """
        # Default empty profile if none is provided
        p = profile or TaxProfile()

        opportunities = []
        warnings = []
        
        # Determine status/confidence
        if p.tax_regime == "unknown" or p.annual_income_range == "unknown":
            status = "INFORMATIONAL"
        elif p.annual_income_range == "> 15L":
            status = "REQUIRES_PROFESSIONAL_REVIEW"
        else:
            status = "ESTIMATED"

        # General educational notes about taxation differences
        opportunities.append({
            "title": "Mutual Fund Taxation",
            "description": TAXATION_EXPLANATIONS["equity"] + " " + TAXATION_EXPLANATIONS["debt"],
            "type": "educational"
        })

        # Section 80C & ELSS analysis (Only applicable if Old Regime is used or unknown)
        if p.tax_regime == "new":
            warnings.append({
                "title": "New Tax Regime Selected",
                "description": "Under the New Tax Regime (Section 115BAC), Section 80C deductions (including ELSS) are not applicable. ELSS can still be chosen for its investment merits, but it will not reduce tax liability."
            })
        else:
            # Old or Unknown regime
            regime_note = " (Assuming Old Tax Regime)" if p.tax_regime == "unknown" else ""
            remaining_80c = max(0.0, SECTION_80C_MAX_LIMIT - p.existing_tax_saving_investments_range)
            
            if remaining_80c > 0:
                opportunities.append({
                    "title": f"Potential Section 80C Tax Savings{regime_note}",
                    "description": (
                        f"You have an estimated remaining Section 80C limit of ₹{remaining_80c:,.2f} "
                        "which can be filled with tax-saving instruments. ELSS mutual funds qualify for this deduction."
                    ),
                    "type": "elss_opportunity",
                    "remaining_limit": remaining_80c
                })
                opportunities.append({
                    "title": "ELSS Tax Savings features",
                    "description": TAXATION_EXPLANATIONS["elss"],
                    "type": "educational"
                })
            else:
                opportunities.append({
                    "title": "Section 80C Limit Fully Utilized",
                    "description": "Your Section 80C tax-saving limit of 1.5 Lakhs appears to be fully utilized. Additional ELSS investments will not yield further tax deductions.",
                    "type": "educational"
                })

        # Warnings on lock-in and liquidity
        if p.wants_tax_optimization:
            warnings.append({
                "title": "Tax Optimization Considerations",
                "description": "Tax optimization strategies should always align with your investment horizon and liquidity needs. For example, ELSS has a mandatory 3-year lock-in period."
            })

        # Include metadata for rule transparency
        rule_meta = {
            "financial_year": p.financial_year,
            "rule_identifier": TAX_RULES_METADATA["rule_identifier"],
            "rule_source": TAX_RULES_METADATA["rule_source"],
            "last_reviewed_date": TAX_RULES_METADATA["last_reviewed_date"]
        }

        return {
            "status": status,
            "opportunities": opportunities,
            "warnings": warnings,
            "rules_applied": rule_meta
        }
