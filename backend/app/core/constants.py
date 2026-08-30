API_PREFIX = "/api/v1"

# Risk level -> assumed annual return %, used by the feasibility engine.
# These are estimates for planning purposes only, not guarantees.
RISK_RETURN_MAP = {
    "low": 7.0,
    "mid": 10.0,
    "high": 13.0,
}

# Risk level -> suggested fund category mix (percentages).
FUND_CATEGORY_MIX = {
    "low": {"debt": 60, "largecap": 40},
    "mid": {"largecap": 40, "flexicap": 40, "debt": 20},
    "high": {"largecap": 30, "flexicap": 40, "midcap": 30},
}

# Below this many months, a goal is "short_term" — and short-term goals
# should not be in Mid/High risk (equity volatility risk).
SHORT_TERM_MONTHS_THRESHOLD = 36

DEFAULT_INFLATION_PCT = 6.0
DEFAULT_LIFE_EXPECTANCY = 85
DEFAULT_PRE_RETIREMENT_RETURN_PCT = 11.0
DEFAULT_POST_RETIREMENT_RETURN_PCT = 7.0
# DEFAULT_INFLATION_PCT already exists from Module 4 — reused here too

AMFI_NAV_URL = "https://portal.amfiindia.com/spages/NAVAll.txt"
MFAPI_BASE_URL = "https://api.mfapi.in/mf"

FUND_CATEGORIES = ["largecap", "flexicap", "midcap", "debt"]
FUND_CACHE_TTL_HOURS = 0.01

# Category mapping from legacy/frontend categories to asset_universe subcategories
LEGACY_TO_UNIVERSE_SUBCAT_MAP = {
    "largecap": ["large_cap"],
    "flexicap": ["flexi_cap"],
    "midcap": ["mid_cap", "small_cap"],
    "debt": ["liquid", "overnight", "ultra_short", "money_market", "short_duration"]
}

# Inverse mapping from asset_universe subcategory back to legacy category
UNIVERSE_TO_LEGACY_CAT_MAP = {
    "large_cap": "largecap",
    "flexi_cap": "flexicap",
    "mid_cap": "midcap",
    "small_cap": "midcap",
    "liquid": "debt",
    "overnight": "debt",
    "ultra_short": "debt",
    "money_market": "debt",
    "short_duration": "debt"
}

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-120b"  # current recommended production model (llama-3.3-70b-versatile was deprecated)