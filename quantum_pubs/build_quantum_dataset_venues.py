#!/usr/bin/env python3
"""
build_quantum_dataset_venues.py
================================

Venue‑first dataset builder for the quantum rankings website.

Instead of starting from a list of faculty or institutions, this script:

  1. Takes a list of quantum venues (conferences / journals) and a year range.
  2. Uses the OpenAlex API to retrieve all works published in those venues.
  3. Optionally applies an extra keyword filter for "generic" theory venues
     like FOCS/STOC/SODA so that only quantum‑related papers are kept.
  4. Aggregates per‑author, per‑institution quantum publications.
  5. Emits a JSON file in the exact schema expected by the frontend:
       {
         "venues": [ { "code": ..., "name": ... }, ... ],
         "institutions": {
           "inst0": { "name": "...", "region": "Europe" },
           ...
         },
         "authors": [
           {
             "name": "...",
             "institution": "inst0",
             "publications": [
               { "year": 2021, "venue": "QIP", "title": "..." },
               ...
             ]
           },
           ...
         ]
       }

You can then either:
  - Serve `data.json` and let `script.js` fetch it, or
  - Use the companion `build_quantum_dataset.py` / a tiny helper to wrap
    the JSON into a `data.js` file that does:  window.dataset = {...};

This script does **not** call OpenAlex here in this environment; it is meant
to be run on your own machine with internet access.
"""

# Typical command: python build_quantum_dataset_venues.py   --min-year 2005   --max-year 2025   --mailto "basch.oakwood@gmail.com"   --min-papers-per-author 1   --min-papers-per-institution 5   --max-institutions 1000   --output-json data.json   --output-js data.js

import argparse
import json
import time
from collections import defaultdict
from typing import Dict, List, Any, Tuple
import pathlib
import requests


# ------------------------- Configuration ---------------------------------

# Default venue configuration.
#
# You can edit this list or override with a YAML/JSON later if you like.
# `search` is the string we pass to OpenAlex /sources?search=... to find
# the source; `require_keywords` means we additionally require the title/
# abstract to contain quantum‑related terms.
# Default venue configuration.  To accurately harvest data from OpenAlex, we
# specify explicit source identifiers for journals whenever possible and use
# search strings for conferences that vary by year.  See the README for
# details on how these IDs were determined.  For FOCS/STOC/SODA we leave
# ``source_ids`` empty and provide a search term; the builder will collect
# all matching sources (one per conference edition) to ensure full coverage.
DEFAULT_VENUES = [
    # TCS venues – harvest via DBLP and require quantum keywords
    {
        "code": "FOCS",
        "name": "IEEE Symposium on Foundations of Computer Science (FOCS)",
        # Appears as 'venue': "FOCS" in DBLP JSON
        "dblp_venue": "FOCS",
        "require_keywords": True,
    },
    {
        "code": "STOC",
        "name": "ACM Symposium on Theory of Computing (STOC)",
        # Appears as 'venue': "STOC" in DBLP JSON
        "dblp_venue": "STOC",
        "require_keywords": True,
    },
    {
        "code": "SODA",
        "name": "ACM-SIAM Symposium on Discrete Algorithms (SODA)",
        # Appears as 'venue': "SODA" in DBLP JSON
        "dblp_venue": "SODA",
        "require_keywords": True,
    },
    {
        "code": "CCC",
        "name": "IEEE Conference on Computational Complexity (CCC)",
        # DBLP uses 'CCC' as the venue acronym
        "dblp_venue": "CCC",
        "require_keywords": True,
    },
    {
        "code": "ITCS",
        "name": "Innovations in Theoretical Computer Science (ITCS)",
        # In DBLP, the venue acronym is "ITCS"
        "dblp_venue": "ITCS",
        "require_keywords": True,
    },
    {
        "code": "CRYPTO",
        "name": "International Cryptology Conference (CRYPTO)",
        "dblp_venue": "CRYPTO",
        "require_keywords": True,  # keep only quantum-adjacent crypto via keywords
    },
    {
        "code": "EUROCRYPT",
        "name": "European Cryptology Conference (EUROCRYPT)",
        "dblp_venue": "EUROCRYPT",
        "require_keywords": True,
    },
    {
        "code": "QCRYPT",
        "name": "Conference on Quantum Cryptography (QCrypt)",
        # QCrypt is quantum by design; no keyword filter needed.
        "dblp_venue": "QCRYPT",
        "require_keywords": False,
    },
    {
        "code": "TQC",
        "name": "Theory of Quantum Computation, Communication and Cryptography (TQC)",
        # TQC is quantum-specific, but DBLP coverage is extremely good
        "dblp_venue": "TQC",
        "require_keywords": False,
    },
    {
        # Journals and magazines: supply explicit source ids.  Codes have been
        # normalised to match the frontend (no underscores).
        "code": "NPJQI",
        "name": "npj Quantum Information",
        "source_ids": ["https://openalex.org/S2738600312"],
        "require_keywords": False,
    },
    {
        "code": "PRXQ",
        "name": "PRX Quantum",
        "source_ids": ["https://openalex.org/S4210195673"],
        "require_keywords": False,
    },
    {
        "code": "QUANTUM",
        "name": "Quantum (open journal)",
        "source_ids": ["https://openalex.org/S4210226432"],
        "require_keywords": False,
    },
    {
        "code": "QIC",
        "name": "Quantum Information and Computation",
        "source_ids": ["https://openalex.org/S41034432"],
        "require_keywords": False,
    },
    {
        "code": "ACMTQC",
        "name": "ACM Transactions on Quantum Computing",
        "source_ids": ["https://openalex.org/S4210170170"],
        "require_keywords": False,
    },
    {
        "code": "NATCOMM",
        "name": "Nature Communications",
        "source_ids": ["https://openalex.org/S64187185"],
        "require_keywords": True
    },
    {
        "code": "NATPHYS",
        "name": "Nature Physics",
        "source_ids": ["https://openalex.org/S156274416"],
        "require_keywords": True
    },
    {
        "code": "NATURE",
        "name": "Nature",
        "source_ids": ["https://openalex.org/S137773608"],
        "require_keywords": True
    },
    {
        "code": "SCIENCE",
        "name": "Science",
        "source_ids": ["https://openalex.org/S3880285"],
        "require_keywords": True
    },
    {
        "code": "PRL",
        "name": "Physical Review Letters",
        "source_ids": ["https://openalex.org/S24807848"],
        "require_keywords": True
    },
    {
        "code": "PRA",
        "name": "Physical Review A",
        "source_ids": ["https://openalex.org/S164566984"],
        "require_keywords": True
    },
    {
        "code": "PRX",
        "name": "Physical Review X",
        "source_ids": ["https://openalex.org/S137042341"],
        "require_keywords": True
    },
    {
        "code": "ISIT",
        "name": "IEEE Transactions on Information Theory",
        "source_ids": ["https://openalex.org/S4502562"],
        "require_keywords": True
    }
]


# A small set of keywords to treat a generic‑venue paper as quantum‑related.
QUANTUM_KEYWORDS = [
    # Core identifiers
    "quantum",
    "qubit",
    "qudit",
    "qutrit",

    # Algorithms & protocols
    "quantum algorithm",
    "quantum circuit",
    "quantum optimization",
    "variational quantum",
    "vqa",
    "vqe",
    "qaoa",
    "quantum walk",
    "boson sampling",
    "hamiltonian simulation",
    "quantum simulation",

    # Information theory & cryptography
    "entanglement",
    "bell inequality",
    "nonlocality",
    "quantum key distribution",
    "qkd",
    "device-independent",
    "measurement-based quantum",
    "mbqc",

    # Complexity theory
    "quantum advantage",
    "quantum supremacy",
    "bqp",
    "qma",
    "qmma",
    "qcma",
    "qszk",
    "boson-sampling",
    "classical simulation of quantum",

    # Error correction & noise
    "quantum error correction",
    "qec",
    "surface code",
    "stabilizer code",
    "fault tolerant",
    "fault-tolerant",

    # Quantum channels / info theory
    "quantum channel",
    "quantum capacity",
    "quantum information",
    "quantum entropy",
    "coherent information",
    "quantum mutual information",

    # Quantum cryptography & randomness
    "quantum cryptography",
    "post-quantum",
    "quantum randomness",
    "randomness amplification",
    "quantum de finetti",

    # ➤ Interactive proofs / entangled provers / nonlocal games
    "mip",
    "mip*",
    "nonlocal game",
    "nonlocal games",
    "entangled game",
    "entangled games",
    "entangled prover",
    "entangled provers",
    "xor game",
    "xor games",
    "interactive proof",
    "interactive proofs",
    "multiprover",
    "multi-prover",
    "rigidity",
    "rigidity theorem",
    "self-testing",
    "self testing",
    "quantum pcp",
    "pcp for entangled",
    "quantum low-degree test",
    "classical verification of quantum",
    "verifiable quantum",
]



# Map OpenAlex country codes (2‑letter) to coarse regions.
COUNTRY_TO_REGION = {
    # -----------------------
    # North America
    # -----------------------
    "US": "North America",
    "CA": "North America",
    "MX": "North America",
    "GL": "North America",  # Greenland (geographically North America)

    # -----------------------
    # Europe
    # -----------------------
    "AL": "Europe",
    "AD": "Europe",
    "AM": "Europe",  # Caucasus treated as Europe in scientometrics
    "AT": "Europe",
    "AZ": "Europe",  # same rationale as AM/GE
    "BA": "Europe",
    "BE": "Europe",
    "BG": "Europe",
    "BY": "Europe",
    "CH": "Europe",
    "CY": "Europe",  # EU member, treated as Europe
    "CZ": "Europe",
    "DE": "Europe",
    "DK": "Europe",
    "EE": "Europe",
    "ES": "Europe",
    "FI": "Europe",
    "FR": "Europe",
    "GB": "Europe",
    "GE": "Europe",
    "GR": "Europe",
    "HR": "Europe",
    "HU": "Europe",
    "IE": "Europe",
    "IS": "Europe",
    "IT": "Europe",
    "KZ": "Asia",  # classified as Asia in scientometrics despite Ural region
    "LI": "Europe",
    "LT": "Europe",
    "LU": "Europe",
    "LV": "Europe",
    "MC": "Europe",
    "MD": "Europe",
    "ME": "Europe",
    "MK": "Europe",
    "MT": "Europe",
    "NL": "Europe",
    "NO": "Europe",
    "PL": "Europe",
    "PT": "Europe",
    "RO": "Europe",
    "RS": "Europe",
    "RU": "Europe",  # scientifically treated as Europe
    "SE": "Europe",
    "SI": "Europe",
    "SK": "Europe",
    "SM": "Europe",
    "UA": "Europe",
    "VA": "Europe",  # Vatican
    "UK": "Europe",  # alias

    # -----------------------
    # Asia
    # -----------------------
    "AE": "Asia",
    "AF": "Asia",
    "AZ": "Asia",  # some datasets place AZ in both; we treat as Europe above
    "BH": "Asia",
    "BD": "Asia",
    "BN": "Asia",
    "BT": "Asia",
    "CN": "Asia",
    "EG": "Africa",  # correct classification
    "HK": "Asia",
    "ID": "Asia",
    "IL": "Asia",
    "IN": "Asia",
    "IQ": "Asia",
    "IR": "Asia",
    "JO": "Asia",
    "JP": "Asia",
    "KG": "Asia",
    "KH": "Asia",
    "KP": "Asia",
    "KR": "Asia",
    "KW": "Asia",
    "KZ": "Asia",
    "LA": "Asia",
    "LB": "Asia",
    "LK": "Asia",
    "MM": "Asia",
    "MN": "Asia",
    "MO": "Asia",
    "MY": "Asia",
    "NP": "Asia",
    "OM": "Asia",
    "PH": "Asia",
    "PK": "Asia",
    "PS": "Asia",
    "QA": "Asia",
    "SA": "Asia",
    "SG": "Asia",
    "SY": "Asia",
    "TH": "Asia",
    "TJ": "Asia",
    "TL": "Asia",
    "TM": "Asia",
    "TR": "Europe",  # scientometrics + CSRankings treat it as Europe
    "TW": "Asia",
    "UZ": "Asia",
    "VN": "Asia",
    "YE": "Asia",

    # -----------------------
    # Oceania
    # -----------------------
    "AU": "Oceania",
    "NZ": "Oceania",
    "FJ": "Oceania",
    "PG": "Oceania",
    "SB": "Oceania",
    "TO": "Oceania",
    "VU": "Oceania",
    "WS": "Oceania",
    "NR": "Oceania",
    "KI": "Oceania",
    "TV": "Oceania",
    "FM": "Oceania",
    "MH": "Oceania",
    "PW": "Oceania",

    # -----------------------
    # South America
    # -----------------------
    "AR": "South America",
    "BO": "South America",
    "BR": "South America",
    "CL": "South America",
    "CO": "South America",
    "EC": "South America",
    "GY": "South America",
    "PE": "South America",
    "PY": "South America",
    "SR": "South America",
    "UY": "South America",
    "VE": "South America",

    # -----------------------
    # Central America & Caribbean
    # -----------------------
    "BZ": "North America",
    "CR": "North America",
    "GT": "North America",
    "HN": "North America",
    "NI": "North America",
    "PA": "North America",
    "SV": "North America",
    "CU": "North America",
    "DO": "North America",
    "HT": "North America",
    "JM": "North America",
    "TT": "North America",
    "BB": "North America",
    "BS": "North America",

    # -----------------------
    # Middle East (subset of Asia, but useful if you ever add subregions)
    # -----------------------
    # Already included via Asia classification above.

    # -----------------------
    # Africa
    # -----------------------
    "DZ": "Africa",
    "AO": "Africa",
    "BF": "Africa",
    "BI": "Africa",
    "BJ": "Africa",
    "BW": "Africa",
    "CD": "Africa",
    "CF": "Africa",
    "CG": "Africa",
    "CI": "Africa",
    "CM": "Africa",
    "CV": "Africa",
    "DJ": "Africa",
    "DZ": "Africa",
    "EG": "Africa",
    "ER": "Africa",
    "ET": "Africa",
    "GA": "Africa",
    "GH": "Africa",
    "GM": "Africa",
    "GN": "Africa",
    "GQ": "Africa",
    "KE": "Africa",
    "KM": "Africa",
    "LR": "Africa",
    "LS": "Africa",
    "LY": "Africa",
    "MA": "Africa",
    "MG": "Africa",
    "ML": "Africa",
    "MR": "Africa",
    "MU": "Africa",
    "MW": "Africa",
    "MZ": "Africa",
    "NA": "Africa",
    "NE": "Africa",
    "NG": "Africa",
    "RW": "Africa",
    "SC": "Africa",
    "SD": "Africa",
    "SL": "Africa",
    "SN": "Africa",
    "SO": "Africa",
    "SS": "Africa",
    "ST": "Africa",
    "SZ": "Africa",
    "TD": "Africa",
    "TG": "Africa",
    "TN": "Africa",
    "TZ": "Africa",
    "UG": "Africa",
    "ZA": "Africa",
    "ZM": "Africa",
    "ZW": "Africa",
}



def region_from_country_code(code: str) -> str:
    if not code:
        return "Other"
    return COUNTRY_TO_REGION.get(code.upper(), "Other")

# ------------------------- OpenAlex caching ------------------------------

OPENALEX_CACHE_PATH = pathlib.Path(__file__).with_name("openalex_cache.json")

# Structure: {"doi": {doi -> slim_work}, "title": {key -> slim_work}}
_openalex_cache = {"doi": {}, "title": {}}


def load_openalex_cache():
    global _openalex_cache
    if OPENALEX_CACHE_PATH.is_file():
        try:
            with OPENALEX_CACHE_PATH.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                _openalex_cache["doi"] = dict(data.get("doi", {}))
                _openalex_cache["title"] = dict(data.get("title", {}))
            print(f"[cache] Loaded OpenAlex cache from {OPENALEX_CACHE_PATH}")
        except Exception as e:
            print(f"[cache] Failed to load cache ({e}); starting fresh")


def save_openalex_cache():
    tmp_path = OPENALEX_CACHE_PATH.with_suffix(".tmp")
    try:
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(_openalex_cache, f, ensure_ascii=False)
        tmp_path.replace(OPENALEX_CACHE_PATH)
        print(f"[cache] Saved OpenAlex cache to {OPENALEX_CACHE_PATH}")
    except Exception as e:
        print(f"[cache] Failed to save cache ({e})")


# ------------------------- OpenAlex helpers -------------------------------

BASE_URL = "https://api.openalex.org"


def openalex_get(path: str, params: Dict[str, Any], mailto: str = None, sleep: float = 0.2) -> Dict[str, Any]:
    """Make a polite GET request to OpenAlex and return JSON."""
    url = f"{BASE_URL}{path}"
    params = dict(params)
    if mailto:
        params["mailto"] = mailto
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if sleep:
        time.sleep(sleep)
    return data


def find_source_id_for_venue(search: str, mailto: str = None, max_candidates: int = 5) -> str:
    """
    Backwards‑compatible helper that returns a single OpenAlex source ID for a
    given search term.  It delegates to ``find_source_ids_for_venue`` and
    returns the first ID if present.  If no matching sources are found,
    raises a RuntimeError.
    """
    ids = find_source_ids_for_venue(search, mailto=mailto, max_candidates=max_candidates)
    if not ids:
        raise RuntimeError(f"No OpenAlex sources found for search='{search}'")
    return ids[0]


# New helper to return all plausible OpenAlex source IDs for a search term.
def find_source_ids_for_venue(search: str, mailto: str = None, max_candidates: int = 25) -> List[str]:
    """
    Use /sources?search=... to find all matching source identifiers for a
    venue.  OpenAlex assigns each conference edition its own source ID, so
    multiple results may be returned.  We include only those results whose
    display_name contains all tokens in the search string (case‑insensitive).
    The number of candidates can be limited via ``max_candidates``.
    """
    try:
        data = openalex_get(
            "/sources", {"search": search, "per-page": max_candidates}, mailto=mailto
        )
    except Exception:
        return []
    results = data.get("results", [])
    ids: List[str] = []
    for src in results:
        name = (src.get("display_name") or "").lower()
        tokens = [t.lower() for t in search.split() if t]
        if all(tok in name for tok in tokens):
            ids.append(src["id"])
    return ids


# (Definition removed; a unified implementation of find_source_id_for_venue appears earlier.)

def iter_works_for_source(
    source_id: str,
    start_year: int,
    end_year: int,
    mailto: str = None,
    per_page: int = 200,
    max_pages: int = None,
    sleep: float = 0.2,
    require_keywords: bool = False,
):
    """
    Iterate through works for a given source over [start_year, end_year]
    using the OpenAlex /works endpoint.

    If require_keywords is True, we:
      - push a title.search OR-filter built from QUANTUM_KEYWORDS into the API
      - and, if the result set is still too large (>10k), recursively split the
        year range into smaller intervals until each query falls below the
        OpenAlex 10k limit.

    This avoids 400 errors from requesting page > 50 while keeping coverage
    essentially complete for large venues like PRL / Nature Communications.
    """

    # Build the OR-list for title.search once
    title_filter_val = None
    if require_keywords:
        # Clean / deduplicate keywords for title.search.
        title_terms = {
            kw.replace(",", " ").strip()
            for kw in QUANTUM_KEYWORDS
            if kw and len(kw.strip()) >= 3
        }
        if title_terms:
            # Example: "quantum|qubit|entanglement|qkd|..."
            title_filter_val = "|".join(sorted(title_terms))

    # Effective page limit imposed by OpenAlex (10k results cap).
    # For per_page=200 this is 50 pages.
    max_pages_by_api = 10000 // per_page if per_page > 0 else 50
    if max_pages is not None:
        max_pages_by_api = min(max_pages_by_api, max_pages)

    def make_filter_str(y0: int, y1: int) -> str:
        from_date = f"{y0}-01-01"
        to_date = f"{y1}-12-31"
        base = (
            f"primary_location.source.id:{source_id},"
            f"from_publication_date:{from_date},"
            f"to_publication_date:{to_date}"
        )
        if title_filter_val:
            return base + f",title.search:{title_filter_val}"
        return base

    def _iter_year_range(y0: int, y1: int):
        # First, probe page 1 to see how big the result set is.
        filter_str = make_filter_str(y0, y1)
        params = {
            "filter": filter_str,
            "page": 1,
            "per-page": per_page,
        }

        data = openalex_get("/works", params, mailto=mailto, sleep=sleep)
        meta = data.get("meta", {}) or {}
        total = meta.get("count")
        results = data.get("results", [])

        # Compute how many pages actually exist for this query
        effective_page_limit = max_pages_by_api
        if isinstance(total, int) and per_page > 0:
            pages_from_count = (total + per_page - 1) // per_page  # ceil(total / per_page)
            if effective_page_limit is None:
                effective_page_limit = pages_from_count
            else:
                effective_page_limit = min(effective_page_limit, pages_from_count)

        # If the range is too large (>10k) and spans more than one year,
        # split it into two subranges and recurse.
        if isinstance(total, int) and total > 10000 and y0 < y1:
            mid = (y0 + y1) // 2
            # Left half [y0, mid]
            yield from _iter_year_range(y0, mid)
            # Right half [mid+1, y1]
            yield from _iter_year_range(mid + 1, y1)
            return

        # Otherwise, page through this range normally (respecting the 10k cap).
        page = 1
        while True:
            if page == 1:
                current_results = results
            else:
                # Don't request pages beyond what meta["count"] says is possible
                if effective_page_limit is not None and page > effective_page_limit:
                    break

                params = {
                    "filter": filter_str,
                    "page": page,
                    "per-page": per_page,
                }

                try:
                    data = openalex_get("/works", params, mailto=mailto, sleep=sleep)
                except requests.HTTPError as e:
                    # OpenAlex can return 409 if page is out of range or query too broad.
                    # Treat that as "no more pages" for this range.
                    if e.response is not None and e.response.status_code == 409:
                        print(
                            f"[warning] OpenAlex 409 for source {source_id}, "
                            f"years [{y0},{y1}], page {page}; stopping pagination."
                        )
                        break
                    raise

                current_results = data.get("results", [])

            if not current_results:
                break

            for w in current_results:
                yield w

            page += 1
            if effective_page_limit is not None and page > effective_page_limit:
                # Optional: keep your 10k-warning logic here if you like
                break

    # Kick off recursion on the full year range.
    yield from _iter_year_range(start_year, end_year)

def _slim_openalex_work(work: Dict[str, Any]) -> Dict[str, Any]:
    """
    Keep only fields we actually use to keep the cache small:
      - id, title/display_name, publication_year
      - authorships: author(id, display_name), institutions(id, display_name, country_code)
    """
    if not work:
        return {}
    out: Dict[str, Any] = {
        "id": work.get("id"),
        "title": work.get("title") or work.get("display_name"),
        "display_name": work.get("display_name"),
        "publication_year": work.get("publication_year"),
    }
    slim_authorships = []
    for auth in work.get("authorships", []):
        a = auth.get("author") or {}
        insts = auth.get("institutions") or []
        slim_insts = []
        for inst in insts:
            slim_insts.append({
                "id": inst.get("id"),
                "display_name": inst.get("display_name"),
                "country_code": inst.get("country_code"),
            })
        slim_authorships.append({
            "author": {
                "id": a.get("id"),
                "display_name": a.get("display_name"),
            },
            "institutions": slim_insts,
        })
    out["authorships"] = slim_authorships
    return out


# ------------------------- DBLP + OpenAlex bridging -------------------------------

DBLP_SEARCH_URL = "https://dblp.org/search/publ/api"


def _title_looks_quantum(title: str) -> bool:
    """
    Cheap prefilter using only the title and QUANTUM_KEYWORDS.

    This is used *before* we call OpenAlex for generic TCS/crypto venues
    (require_keywords=True) so we don't resolve obviously classical papers.
    """
    t = (title or "").lower()
    if not t:
        return False
    return any(kw.lower() in t for kw in QUANTUM_KEYWORDS)


def dblp_search_conference_papers(
    venue_acronym: str,
    start_year: int,
    end_year: int,
    max_hits: int = 1000,
) -> List[Dict[str, Any]]:
    """
    Query the DBLP publication API for a given conference acronym over
    [start_year, end_year].

    Strategy:
      * For each year, search for "<VENUE> <YEAR>".
      * Filter hits so that info["venue"] contains the exact acronym.
      * Drop obvious non-paper types.
    """
    results: List[Dict[str, Any]] = []

    for year in range(start_year, end_year + 1):
        params = {
            "q": f"{venue_acronym} {year}",
            "h": str(max_hits),
            "format": "json",
        }
        try:
            resp = requests.get(DBLP_SEARCH_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json().get("result", {})
        except Exception as e:
            print(f"[dblp] {venue_acronym} {year}: request failed: {e}")
            continue

        hits = (data.get("hits") or {}).get("hit") or []
        if isinstance(hits, dict):
            hits = [hits]

        for hit in hits:
            info = hit.get("info", {}) or {}
            v = info.get("venue")

            if isinstance(v, list):
                has_venue = venue_acronym in v
            else:
                has_venue = (v == venue_acronym)

            if not has_venue:
                continue

            typ = (info.get("type") or "").lower()
            if typ.startswith("editorship"):
                continue

            year_str = info.get("year")
            try:
                y_int = int(year_str)
            except (TypeError, ValueError):
                continue
            if y_int < start_year or y_int > end_year:
                continue

            info = dict(info)
            info["year_int"] = y_int
            results.append(info)

    print(f"[dblp] {venue_acronym}: collected {len(results)} candidate papers from DBLP")
    return results


def _extract_doi_from_dblp_info(info: Dict[str, Any]) -> str:
    """
    Try to extract a clean DOI string from a DBLP 'info' dict.
    """
    doi = info.get("doi")
    ee = info.get("ee")
    if not doi and isinstance(ee, str) and "doi.org/" in ee:
        doi = ee.split("doi.org/", 1)[-1]
    if not doi:
        return None
    doi = doi.strip()
    if doi.lower().startswith("https://doi.org/"):
        doi = doi[len("https://doi.org/") :]
    elif doi.lower().startswith("http://doi.org/"):
        doi = doi[len("http://doi.org/") :]
    return doi or None


def fetch_openalex_work_by_doi(doi: str, mailto: str = None) -> Dict[str, Any]:
    """
    Resolve a DOI to an OpenAlex work via /works/doi:<doi>, with cache.
    """
    if not doi:
        return {}

    # Cache lookup
    if doi in _openalex_cache["doi"]:
        return _openalex_cache["doi"][doi]

    try:
        # For DOI lookups we can set sleep=0 and rely on overall rate being modest.
        data = openalex_get(f"/works/doi:{doi}", params={}, mailto=mailto, sleep=0.0)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return {}
        print(f"[openalex] DOI {doi}: HTTP error {e}")
        return {}
    except Exception as e:
        print(f"[openalex] DOI {doi}: generic error {e}")
        return {}

    if not data:
        return {}

    slim = _slim_openalex_work(data)
    _openalex_cache["doi"][doi] = slim
    return slim


def search_openalex_work_by_title(
    title: str,
    year_hint: int = None,
    mailto: str = None,
    max_results: int = 5,
) -> Dict[str, Any]:
    """
    Fallback: search OpenAlex by title and optional year window, with cache.
    """
    title = (title or "").strip()
    if not title:
        return {}

    key_parts = [title.lower()]
    if year_hint is not None:
        key_parts.append(str(year_hint))
    cache_key = "|".join(key_parts)

    if cache_key in _openalex_cache["title"]:
        return _openalex_cache["title"][cache_key]

    filters = []
    if year_hint is not None:
        lo = year_hint - 1
        hi = year_hint + 1
        filters.append(f"from_publication_date:{lo}-01-01")
        filters.append(f"to_publication_date:{hi}-12-31")
    filter_str = ",".join(filters) if filters else None

    params: Dict[str, Any] = {
        "search": title,
        "per_page": max_results,
    }
    if filter_str:
        params["filter"] = filter_str

    try:
        data = openalex_get("/works", params=params, mailto=mailto, sleep=0.0)
    except Exception as e:
        print(f"[openalex] title search failed for '{title[:80]}...': {e}")
        return {}

    results = (data or {}).get("results") or []
    if not results:
        return {}

    chosen = None
    for w in results:
        y = w.get("publication_year")
        try:
            y = int(y)
        except (TypeError, ValueError):
            y = None
        if year_hint is not None and y is not None and abs(y - year_hint) <= 1:
            chosen = w
            break
    if chosen is None:
        chosen = results[0]

    slim = _slim_openalex_work(chosen)
    _openalex_cache["title"][cache_key] = slim
    return slim


def harvest_dblp_venue(
    vcfg: Dict[str, Any],
    start_year: int,
    end_year: int,
    institutions: Dict[str, Dict[str, Any]],
    author_inst: Dict[Tuple[str, str], Dict[str, Any]],
    venues_out: List[Dict[str, str]],
    seen_work_ids: set,
    mailto: str = None,
):
    """
    Bridge DBLP -> OpenAlex -> our aggregation.

    vcfg must contain:
      * code
      * name
      * dblp_venue: the acronym as it appears in DBLP's 'venue' field
      * require_keywords: whether to apply quantum keyword filtering
    """
    code = vcfg.get("code")
    name = vcfg.get("name")
    dblp_venue = vcfg.get("dblp_venue")
    require_keywords = vcfg.get("require_keywords", False)

    if not dblp_venue:
        print(f"[dblp] {code}: no dblp_venue configured; skipping")
        return

    venues_out.append({"code": code, "name": name})

    dblp_infos = dblp_search_conference_papers(
        dblp_venue,
        start_year=start_year,
        end_year=end_year,
    )

    total = len(dblp_infos)
    filtered_out_by_title = 0
    resolved = 0

    for info in dblp_infos:
        title = info.get("title") or ""
        year_int = info.get("year_int")

        # Cheap prefilter for generic venues: skip obviously classical papers
        if require_keywords and not _title_looks_quantum(title):
            filtered_out_by_title += 1
            continue

        # Resolve to OpenAlex via DOI if possible, otherwise via title search
        doi = _extract_doi_from_dblp_info(info)
        work: Dict[str, Any] = {}
        if doi:
            work = fetch_openalex_work_by_doi(doi, mailto=mailto)
        if not work:
            work = search_openalex_work_by_title(title, year_hint=year_int, mailto=mailto)
        if not work:
            print(f"[dblp] {code}: could not resolve OpenAlex work for '{title[:80]}...' ({year_int})")
            continue

        resolved += 1

        work_id = work.get("id")
        if work_id and work_id in seen_work_ids:
            continue
        if work_id:
            seen_work_ids.add(work_id)

        year = work.get("publication_year") or year_int
        try:
            year = int(year)
        except (TypeError, ValueError):
            continue
        if year < start_year or year > end_year:
            continue

        # Apply main quantum filter (title+abstract) if requested
        if not is_quantum_paper(work, require_keywords=require_keywords):
            continue

        final_title = (work.get("title") or work.get("display_name") or title).strip() or "(untitled)"
        pub_entry = {"year": int(year), "venue": code, "title": final_title}

        for auth in work.get("authorships", []):
            author = auth.get("author") or {}
            author_id = author.get("id")
            author_name = author.get("display_name") or "Unknown"
            insts = auth.get("institutions") or []
            if not insts or not author_id:
                continue
            for inst in insts:
                inst_id = inst.get("id")
                if not inst_id:
                    continue
                inst_name = inst.get("display_name") or "Unknown institution"
                country_code = inst.get("country_code")
                if inst_id not in institutions:
                    institutions[inst_id] = {
                        "name": inst_name,
                        "region": region_from_country_code(country_code),
                    }
                key = (author_id, inst_id)
                if key not in author_inst:
                    author_inst[key] = {
                        "name": author_name,
                        "institution_id": inst_id,
                        "publications": [],
                    }
                author_inst[key]["publications"].append(pub_entry)

    print(
        f"[dblp] {code}: {total} candidates, {filtered_out_by_title} "
        f"filtered by title, {resolved} resolved via OpenAlex"
    )


# ------------------------- Core logic -------------------------------------

def is_quantum_paper(work: Dict[str, Any], require_keywords: bool) -> bool:
    """
    Decide whether a work should be treated as quantum‑related.

    For pure quantum venues, require_keywords=False and we accept everything.
    For generic TCS venues (FOCS/STOC/SODA), require_keywords=True and we only
    keep works whose title or abstract contains one of the QUANTUM_KEYWORDS.
    """
    if not require_keywords:
        return True

    title = (work.get("title") or work.get("display_name") or "").lower()
    abstract = (work.get("abstract") or work.get("abstract_inverted_index") or "")

    # abstract_inverted_index is a dict; we flatten its keys if present.
    if isinstance(abstract, dict):
        # keys are tokens; join them into a pseudo‑abstract string
        abstract_text = " ".join(abstract.keys()).lower()
    else:
        abstract_text = str(abstract).lower()

    text = title + " " + abstract_text
    return any(kw in text for kw in QUANTUM_KEYWORDS)


def build_dataset_from_venues(
    venues_cfg: List[Dict[str, Any]],
    start_year: int,
    end_year: int,
    mailto: str = None,
    max_pages_per_source: int = None,
    min_papers_per_author: int = 1,
    min_papers_per_institution: int = 0,
    max_institutions: int = None,
) -> Dict[str, Any]:

    """
    Main driver: for each venue configuration, resolve its source IDs, iterate
    through works, filter to quantum papers, and aggregate authors + institutions.

    Each entry in ``venues_cfg`` may specify either ``source_ids`` (a list of
    explicit OpenAlex source identifiers) or a ``search`` string.  If
    ``source_ids`` is provided and non‑empty, the script will harvest
    publications from each listed source.  Otherwise it falls back to using
    ``search`` and resolves all matching sources via ``find_source_ids_for_venue``.
    ``require_keywords`` controls whether the title/abstract must contain
    quantum keywords (used for generic theory conferences like FOCS/STOC/SODA).
    """

    # institution_id -> { "name": ..., "region": ... }
    institutions: Dict[str, Dict[str, Any]] = {}
    # (author_id, institution_id) -> {"name": ..., "institution_id": ..., "publications": [...]}
    author_inst: Dict[Tuple[str, str], Dict[str, Any]] = {}
    # List of venue descriptors for output
    venues_out: List[Dict[str, str]] = []
    # Track processed work IDs to avoid duplicate counting across multiple sources
    seen_work_ids: set = set()

    for vcfg in venues_cfg:
        code = vcfg.get("code")
        name = vcfg.get("name")
        require_keywords = vcfg.get("require_keywords", False)

        dblp_venue = vcfg.get("dblp_venue")
        if dblp_venue:
            print(f"[venue] {code}: harvesting via DBLP venue '{dblp_venue}'")
            harvest_dblp_venue(
                vcfg,
                start_year=start_year,
                end_year=end_year,
                institutions=institutions,
                author_inst=author_inst,
                venues_out=venues_out,
                seen_work_ids=seen_work_ids,
                mailto=mailto,
            )
            continue

        # Determine source IDs for this venue (OpenAlex path)
        explicit_ids: List[str] = list(vcfg.get("source_ids", []) or [])
        source_ids: List[str] = []
        if explicit_ids:
            source_ids = explicit_ids
        else:
            search = vcfg.get("search")
            if not search:
                print(f"[venue] {code}: neither 'source_ids' nor 'search' provided; skipping")
                continue
            # Resolve all plausible source IDs for this search term
            source_ids = find_source_ids_for_venue(search, mailto=mailto, max_candidates=25)
            if not source_ids:
                print(f"[venue] {code}: no sources found for search='{search}'; skipping")
                continue
            print(f"[venue] {code}: resolved {len(source_ids)} source id(s) for '{search}'")

        # Record venue descriptor for output
        venues_out.append({"code": code, "name": name})

        # Harvest works from each source id
                # Harvest works from each source id
        for source_id in source_ids:
            print(f"[venue] {code}: harvesting works from source {source_id}")
            for work in iter_works_for_source(
                source_id,
                start_year,
                end_year,
                mailto=mailto,
                max_pages=max_pages_per_source,
                require_keywords=require_keywords,
            ):

                work_id = work.get("id")
                # Deduplicate across sources by work id
                if work_id and work_id in seen_work_ids:
                    continue
                if work_id:
                    seen_work_ids.add(work_id)
                year = work.get("publication_year")
                if year is None:
                    continue
                # Keyword filtering for generic venues
                if not is_quantum_paper(work, require_keywords=require_keywords):
                    continue
                # Extract title
                title = (work.get("title") or work.get("display_name") or "").strip() or "(untitled)"
                
                pub_entry = {"year": int(year), "venue": code, "title": title}
                # Attach publication to each institution listed in this authorship
                for auth in work.get("authorships", []):
                    author = auth.get("author") or {}
                    author_id = author.get("id")
                    author_name = author.get("display_name") or "Unknown"
                    insts = auth.get("institutions") or []
                    if not insts or not author_id:
                        continue
                    for inst in insts:
                        inst_id = inst.get("id")
                        if not inst_id:
                            continue
                        inst_name = inst.get("display_name") or "Unknown institution"
                        country_code = inst.get("country_code")
                        # Register institution if unseen
                        if inst_id not in institutions:
                            institutions[inst_id] = {
                                "name": inst_name,
                                "region": region_from_country_code(country_code),
                            }
                        key = (author_id, inst_id)
                        if key not in author_inst:
                            author_inst[key] = {
                                "name": author_name,
                                "institution_id": inst_id,
                                "publications": [],
                            }
                        # Avoid exact duplicate publications for this author+inst
                        pubs = author_inst[key]["publications"]
                        if not any(
                            p["year"] == pub_entry["year"]
                            and p["venue"] == pub_entry["venue"]
                            and p["title"] == pub_entry["title"]
                            for p in pubs
                        ):
                            pubs.append(pub_entry)

    # Filter out authors with fewer than min_papers_per_author publications
    author_inst = {
        key: val
        for key, val in author_inst.items()
        if len(val["publications"]) >= min_papers_per_author
    }
    print(f"[summary] Institutions found: {len(institutions)}")
    print(f"[summary] Author+institution pairs (after min_papers filter): {len(author_inst)}")

        # Aggregate total publications per institution
    from collections import defaultdict
    inst_total_pubs: Dict[str, int] = defaultdict(int)
    for (author_id, inst_id), info in author_inst.items():
        inst_total_pubs[inst_id] += len(info["publications"])

    # Apply minimum total pubs per institution if requested
    keep_insts = set(inst_total_pubs.keys())
    if min_papers_per_institution > 0:
        keep_insts = {
            inst_id
            for inst_id, count in inst_total_pubs.items()
            if count >= min_papers_per_institution
        }

    # Optionally cap to top-K institutions by total pubs
    if max_institutions is not None and len(keep_insts) > max_institutions:
        # sort institutions by total pubs (descending) and keep the top-K
        sorted_insts = sorted(
            keep_insts,
            key=lambda inst_id: inst_total_pubs.get(inst_id, 0),
            reverse=True,
        )
        keep_insts = set(sorted_insts[:max_institutions])

    # Now drop authors and institutions that are not in keep_insts
    author_inst = {
        key: val
        for key, val in author_inst.items()
        if key[1] in keep_insts
    }
    institutions = {
        inst_id: info
        for inst_id, info in institutions.items()
        if inst_id in keep_insts
    }

    print(f"[summary] Institutions after institution-level filters: {len(institutions)}")
    print(f"[summary] Author+institution pairs after institution-level filters: {len(author_inst)}")


    # Convert raw institution ids to sequential inst0, inst1, ... keys
    inst_id_to_key: Dict[str, str] = {}
    institutions_out: Dict[str, Dict[str, Any]] = {}
    for idx, (inst_id, inst_info) in enumerate(sorted(institutions.items(), key=lambda kv: kv[1]["name"])):
        key = f"inst{idx}"
        inst_id_to_key[inst_id] = key
        institutions_out[key] = {
            "name": inst_info["name"],
            "region": inst_info["region"],
        }
    # Build authors array using new keys
    authors_out: List[Dict[str, Any]] = []
    for (author_id, inst_id), info in author_inst.items():
        inst_key = inst_id_to_key.get(inst_id)
        if not inst_key:
            continue
        authors_out.append({
            "name": info["name"],
            "institution": inst_key,
            "publications": sorted(
                info["publications"], key=lambda p: (p["year"], p["venue"], p["title"])
            ),
        })
    return {
        "venues": venues_out,
        "institutions": institutions_out,
        "authors": authors_out,
    }


# ------------------------- CLI --------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build quantum dataset by venue using OpenAlex.")
    p.add_argument(
        "--min-year",
        type=int,
        default=2005,
        help="Minimum publication year (inclusive).",
    )
    p.add_argument(
        "--max-year",
        type=int,
        default=2025,
        help="Maximum publication year (inclusive).",
    )
    p.add_argument(
        "--mailto",
        type=str,
        default=None,
        help="Contact email to pass to OpenAlex (recommended for heavy use).",
    )
    p.add_argument(
        "--min-papers-per-author",
        type=int,
        default=1,
        help="Minimum number of quantum papers required for an author+institution pair to be included.",
    )
    p.add_argument(
        "--min-papers-per-institution",
        type=int,
        default=3,
        help="Minimum total quantum papers required for an institution to be included.",
    )
    p.add_argument(
        "--max-institutions",
        type=int,
        default=1000,
        help="Optional cap on the number of institutions to keep (keeps the most prolific ones).",
    )
    p.add_argument(
        "--max-pages-per-source",
        type=int,
        default=None,
        help="Optional cap on number of pages per venue (for testing).",
    )
    p.add_argument(
        "--output-json",
        type=str,
        default="data.json",
        help="Path to write JSON dataset.",
    )
    p.add_argument(
        "--output-js",
        type=str,
        default=None,
        help="Optional path to write dataset as a JS file assigning window.dataset.",
    )
    return p.parse_args()


def main():
    args = parse_args()

    load_openalex_cache()

    dataset = build_dataset_from_venues(
        venues_cfg=DEFAULT_VENUES,
        start_year=args.min_year,
        end_year=args.max_year,
        mailto=args.mailto,
        max_pages_per_source=args.max_pages_per_source,
        min_papers_per_author=args.min_papers_per_author,
        min_papers_per_institution=args.min_papers_per_institution,
        max_institutions=args.max_institutions,
    )

    save_openalex_cache()

    # Write JSON
    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False)

    print(f"[output] Wrote JSON dataset to {args.output_json}")

    if args.output_js:
        with open(args.output_js, "w", encoding="utf-8") as f:
            f.write("window.dataset = ")
            json.dump(dataset, f, ensure_ascii=False)
            f.write(";\n")
        print(f"[output] Wrote JS dataset to {args.output_js}")


if __name__ == "__main__":
    main()
