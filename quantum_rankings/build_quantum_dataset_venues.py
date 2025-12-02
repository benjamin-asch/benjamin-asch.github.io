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

import argparse
import json
import time
from collections import defaultdict
from typing import Dict, List, Any, Tuple

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
    {
        # There is no unified OpenAlex source for the QIP conference series.  We
        # use the journal "Quantum Information Processing" (Springer) as a proxy
        # because OpenAlex indexes the journal but not the conference.
        "code": "QIP",
        "name": "Quantum Information Processing (journal)",
        "source_ids": ["https://openalex.org/S92819544"],
        "require_keywords": False,
    },
    {
        # TQC has minimal coverage in OpenAlex; we explicitly list the known
        # conference series ID.  Users can add more IDs here when new
        # editions appear.
        "code": "TQC",
        "name": "Theory of Quantum Computation, Communication and Cryptography (TQC)",
        "source_ids": ["https://openalex.org/S4306418103"],
        "require_keywords": False,
    },
    {
        # QCrypt is sparsely indexed and currently omitted.  Provide an empty
        # ``source_ids`` list so the builder will skip this venue unless
        # populated later.
        "code": "QCRYPT",
        "name": "Conference on Quantum Cryptography (QCrypt)",
        "source_ids": [],
        "require_keywords": False,
    },
    {
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
    # Generic TCS venues – we require quantum keywords to avoid non‑quantum theory.
    {
        "code": "FOCS",
        "name": "IEEE Symposium on Foundations of Computer Science (FOCS)",
        "search": "Symposium on Foundations of Computer Science",
        "require_keywords": True,
    },
    {
        "code": "STOC",
        "name": "ACM Symposium on Theory of Computing (STOC)",
        "search": "Symposium on Theory of Computing",
        "require_keywords": True,
    },
    {
        "code": "SODA",
        "name": "ACM‑SIAM Symposium on Discrete Algorithms (SODA)",
        "search": "Symposium on Discrete Algorithms",
        "require_keywords": True,
    },
]


# A small set of keywords to treat a generic‑venue paper as quantum‑related.
QUANTUM_KEYWORDS = [
    "quantum",
    "qubit",
    "qudit",
    "qaoa",
    "vqe",
    "boson sampling",
    "hamiltonian",
    "qkd",
    "quantum key distribution",
    "entanglement",
    "bell inequality",
    "quantum advantage",
    "quantum supremacy",
]


# Map OpenAlex country codes (2‑letter) to coarse regions.
COUNTRY_TO_REGION = {
    # North America
    "US": "North America",
    "CA": "North America",
    "MX": "North America",

    # Europe (non‑exhaustive)
    "CH": "Europe",
    "DE": "Europe",
    "FR": "Europe",
    "UK": "Europe",
    "GB": "Europe",
    "NL": "Europe",
    "BE": "Europe",
    "IT": "Europe",
    "ES": "Europe",
    "PT": "Europe",
    "SE": "Europe",
    "NO": "Europe",
    "DK": "Europe",
    "FI": "Europe",
    "PL": "Europe",
    "CZ": "Europe",
    "AT": "Europe",
    "HU": "Europe",
    "IE": "Europe",
    "GR": "Europe",

    # Asia (non‑exhaustive)
    "CN": "Asia",
    "JP": "Asia",
    "KR": "Asia",
    "SG": "Asia",
    "IL": "Asia",
    "IN": "Asia",
    "TW": "Asia",

    # Oceania
    "AU": "Oceania",
    "NZ": "Oceania",

    # South America
    "BR": "South America",
    "AR": "South America",
    "CL": "South America",

    # Africa
    "ZA": "Africa",
}


def region_from_country_code(code: str) -> str:
    if not code:
        return "Other"
    return COUNTRY_TO_REGION.get(code.upper(), "Other")


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


def iter_works_for_source(source_id: str, start_year: int, end_year: int, mailto: str = None,
                          per_page: int = 200, max_pages: int = None, sleep: float = 0.2):
    """
    Iterate through all works for a given source over [start_year, end_year]
    using the OpenAlex /works endpoint with primary_location.source.id filter.

    Yields each work JSON object.
    """
    # We can filter by from_publication_date / to_publication_date; year‑only
    # filters are also supported.  We'll use dates for safety.
    from_date = f"{start_year}-01-01"
    to_date = f"{end_year}-12-31"

    page = 1
    while True:
        params = {
            "filter": f"primary_location.source.id:{source_id},"
                      f"from_publication_date:{from_date},"
                      f"to_publication_date:{to_date}",
            "page": page,
            "per-page": per_page,
        }
        data = openalex_get("/works", params, mailto=mailto, sleep=sleep)
        results = data.get("results", [])
        if not results:
            break
        for w in results:
            yield w
        page += 1
        if max_pages is not None and page > max_pages:
            break


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
        # Determine source IDs for this venue
        explicit_ids: List[str] = list(vcfg.get("source_ids", []) or [])
        source_ids: List[str] = []
        if explicit_ids:
            source_ids = explicit_ids
            print(f"[venue] {code}: using {len(source_ids)} explicit source id(s)")
        else:
            search = vcfg.get("search")
            if not search:
                print(f"[venue] {code}: no source_ids or search term provided; skipping")
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
        for source_id in source_ids:
            print(f"[venue] {code}: harvesting works from source {source_id}")
            for work in iter_works_for_source(
                source_id,
                start_year,
                end_year,
                mailto=mailto,
                max_pages=max_pages_per_source,
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
        "--max-pages-per-source",
        type=int,
        default=None,
        help="Optional cap on number of pages per venue (for testing).",
    )
    p.add_argument(
        "--min-papers-per-author",
        type=int,
        default=1,
        help="Minimum number of quantum papers required for an author+institution pair to be included.",
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

    dataset = build_dataset_from_venues(
        venues_cfg=DEFAULT_VENUES,
        start_year=args.min_year,
        end_year=args.max_year,
        mailto=args.mailto,
        max_pages_per_source=args.max_pages_per_source,
        min_papers_per_author=args.min_papers_per_author,
    )

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
