import httpx
from app.core.constants import AMFI_NAV_URL

# AMFI's raw category text -> our simplified 4-bucket system. Match order
# matters: check more specific terms (e.g. "flexi cap") before generic ones.
CATEGORY_KEYWORD_MAP = [
    (["large cap"], "largecap"),
    (["flexi cap", "multi cap"], "flexicap"),
    (["mid cap", "small cap"], "midcap"),
    (
        ["debt", "liquid", "overnight", "gilt", "money market", "ultra short",
         "short duration", "corporate bond", "banking and psu"],
        "debt",
    ),
]


def normalize_category(category_raw: str) -> str | None:
    """Maps AMFI's raw section-header text to one of our 4 fund categories.
    Returns None for categories we don't support in v1 (sectoral, hybrid,
    ELSS, index funds, etc.) — those are simply excluded from the cache."""
    text = category_raw.lower()
    for keywords, bucket in CATEGORY_KEYWORD_MAP:
        if any(kw in text for kw in keywords):
            return bucket
    return None


def _is_direct_growth_plan(scheme_name: str) -> bool:
    """Filters to Direct-Growth plans only — lower expense ratio, the
    standard recommendation for self-directed investors, and avoids
    showing 3-4 near-duplicate entries (Regular/Direct x Growth/IDCW) per
    underlying fund."""
    name = scheme_name.lower()
    return "direct" in name and "growth" in name and "idcw" not in name and "dividend" not in name


def fetch_navall_raw() -> str:
    resp = httpx.get(AMFI_NAV_URL, timeout=30.0, follow_redirects=True)
    resp.raise_for_status()
    return resp.text


def parse_navall(raw_text: str) -> list[dict]:
    """Parses AMFI's NAVAll.txt format. Structure is:
    Category header -> AMC (fund house) name -> scheme rows -> next AMC name
    -> more scheme rows -> next category header -> ...

    Both category headers AND AMC names are semicolon-free lines, so we
    can't treat every semicolon-free line as a category change — only
    lines that actually look like a scheme-type header count. AMFI's
    real category headers always start with one of a small set of
    scheme-type prefixes; AMC names never do.
    """
    results = []
    current_category_raw = ""
    header_prefixes = ("open ended", "close ended", "closed ended", "interval")

    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("Scheme Code"):
            continue  # the column-header row, not data

        if ";" not in line:
            if line.lower().startswith(header_prefixes):
                current_category_raw = line
            # else: an AMC name line (or other noise) — ignore it,
            # keep whatever category we're currently inside
            continue

        parts = line.split(";")
        if len(parts) < 6:
            continue

        scheme_code, _isin_growth, _isin_div, scheme_name, nav_str, date_str = parts[:6]

        if not _is_direct_growth_plan(scheme_name):
            continue

        category = normalize_category(current_category_raw)
        if category is None:
            continue

        try:
            nav = float(nav_str.strip())
        except ValueError:
            continue

        results.append({
            "scheme_code": scheme_code.strip(),
            "scheme_name": scheme_name.strip(),
            "category": category,
            "category_raw": current_category_raw,
            "latest_nav": nav,
            "nav_date": date_str.strip(),
        })

    return results


def fetch_and_parse_funds() -> list[dict]:
    return parse_navall(fetch_navall_raw())