#!/usr/bin/env python3
"""
build_quantum_dataset.py
========================

This script builds a quantum research dataset for the Quantum Research Rankings
web application by harvesting data from the CSRankings faculty list and the
OpenAlex API.  It produces a JSON file in the format expected by the
frontend: a dictionary with keys `venues`, `institutions`, and `authors`.

The workflow is as follows:

1. Download the CSRankings faculty CSV from GitHub.  This file contains
   faculty names and their primary affiliations.  You can override the
   source of this CSV by passing the `--csrankings` flag.
2. Iterate over each faculty member, search for them in OpenAlex, and
   retrieve all of their works.  For each work, filter by year and by
   quantum‐relevant venues.  A small list of keywords is used to further
   filter FOCS/STOC/SODA papers to those relevant to quantum information
   science.
3. Group publications by institution, building up counts per faculty.
4. Write the resulting dataset to a JSON file and optionally generate a
   JavaScript file (`data.js`) for the web frontend.

Usage:

  python build_quantum_dataset.py \
      --output data.json \
      --min-year 2005 --max-year 2025 \
      --max-authors 1000

Note: Harvesting publications for all CSRankings authors can take a long
time.  Use the `--max-authors` option to limit the number of authors
processed (useful for debugging).  You can also provide a file with a
subset of institutions or authors via the `--institutions` or
`--authors-file` options.

Dependencies: This script requires the `requests` library.  Install
with `pip install requests` if necessary.

"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.parse
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

try:
    import requests
except ImportError:
    print("This script requires the 'requests' library. Install it with 'pip install requests'.")
    sys.exit(1)


###############################################################################
# Configuration
###############################################################################

# Patterns for fuzzy matching of OpenAlex venue display names to short codes.
# Each tuple consists of a substring pattern (lower‑case) and the
# corresponding venue code.  Patterns are checked in order; the first
# matching pattern determines the code.
VENUE_PATTERNS: List[Tuple[str, str]] = [
    ('quantum information processing conference', 'QIP'),
    ('quantum information processing', 'QIP'),
    ('qip', 'QIP'),
    ('theory of quantum computation, communication and cryptography', 'TQC'),
    ('tqc', 'TQC'),
    ('quantum cryptography', 'QCrypt'),
    ('qcrypt', 'QCrypt'),
    ('npj quantum information', 'NPJ_QI'),
    ('prx quantum', 'PRX_Q'),
    ('quantum journal', 'Quantum'),
    ('quantum (open journal)', 'Quantum'),
    ('quantum information & computation', 'QIC'),
    ('quantum information and computation', 'QIC'),
    ('acm transactions on quantum computing', 'ACM_TQC'),
    ('ieee symposium on foundations of computer science', 'FOCS'),
    ('foundations of computer science', 'FOCS'),
    ('acm symposium on theory of computing', 'STOC'),
    ('symposium on theory of computing', 'STOC'),
    ('acm-siam symposium on discrete algorithms', 'SODA'),
    ('symposium on discrete algorithms', 'SODA'),
]

# Human‑friendly names for venues keyed by code.  Used when building the
# ``venues`` list in the output.  Feel free to refine these names.
VENUE_NAMES: Dict[str, str] = {
    'QIP': 'Quantum Information Processing (journal/conference)',
    'TQC': 'Theory of Quantum Computation, Communication and Cryptography (TQC)',
    'QCrypt': 'Conference on Quantum Cryptography (QCrypt)',
    'NPJ_QI': 'npj Quantum Information',
    'PRX_Q': 'PRX Quantum',
    'Quantum': 'Quantum (open journal)',
    'QIC': 'Quantum Information and Computation',
    'ACM_TQC': 'ACM Transactions on Quantum Computing',
    'FOCS': 'IEEE Symposium on Foundations of Computer Science (FOCS)',
    'STOC': 'ACM Symposium on Theory of Computing (STOC)',
    'SODA': 'ACM-SIAM Symposium on Discrete Algorithms (SODA)',
}

# Keywords that indicate a quantum‐related publication when searching within
# FOCS, STOC, and SODA.  Only publications with titles containing at least
# one of these keywords are kept.  All keywords are compared
# case‐insensitively.
QUANTUM_KEYWORDS: List[str] = [
    'quantum', 'qubit', 'qutrit', 'entanglement', 'qkd',
    'quantum computing', 'quantum information', 'quantum algorithm',
    'quantum error correction', 'quantum cryptography', 'quantum complexity'
]

# Mapping from ISO country codes (uppercase) to broad regions.  This
# helps populate the `region` field for institutions.  The mapping is
# deliberately coarse and can be refined as needed.
COUNTRY_TO_REGION: Dict[str, str] = {
    # North America
    'US': 'North America', 'CA': 'North America', 'MX': 'North America',
    # Europe
    'GB': 'Europe', 'UK': 'Europe', 'DE': 'Europe', 'FR': 'Europe', 'CH': 'Europe', 'AT': 'Europe',
    'NL': 'Europe', 'BE': 'Europe', 'LU': 'Europe', 'IE': 'Europe', 'SE': 'Europe', 'FI': 'Europe',
    'NO': 'Europe', 'DK': 'Europe', 'ES': 'Europe', 'PT': 'Europe', 'IT': 'Europe', 'GR': 'Europe',
    'PL': 'Europe', 'CZ': 'Europe', 'SK': 'Europe', 'HU': 'Europe', 'RO': 'Europe', 'BG': 'Europe',
    'HR': 'Europe', 'SI': 'Europe', 'EE': 'Europe', 'LV': 'Europe', 'LT': 'Europe', 'CY': 'Europe',
    # Asia
    'CN': 'Asia', 'JP': 'Asia', 'KR': 'Asia', 'TW': 'Asia', 'HK': 'Asia', 'IN': 'Asia',
    'SG': 'Asia', 'IL': 'Asia', 'TR': 'Asia', 'SA': 'Asia',
    # Oceania
    'AU': 'Oceania', 'NZ': 'Oceania'
}


def log(msg: str) -> None:
    """Print a log message to stderr."""
    sys.stderr.write(msg + "\n")


def fetch_json(url: str, *, sleep: float = 0.0) -> dict:
    """Fetch a URL and return the parsed JSON.  Raises an exception on errors."""
    if sleep > 0:
        time.sleep(sleep)
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


def find_author_id(name: str) -> Optional[str]:
    """Look up an author in OpenAlex and return their author ID (without the prefix)."""
    query = urllib.parse.quote(name)
    url = f"https://api.openalex.org/authors?search={query}&per-page=1"
    try:
        data = fetch_json(url)
    except Exception:
        return None
    results = data.get('results', [])
    if not results:
        return None
    author = results[0]
    # The `id` looks like `https://openalex.org/A1234567890`; strip the prefix
    author_id = author['id'].split('/')[-1]
    return author_id


def get_institution_region(institution_name: str) -> str:
    """Look up an institution in OpenAlex and return a broad region string.  If
    the lookup fails, return 'Other'."""
    query = urllib.parse.quote(institution_name)
    url = f"https://api.openalex.org/institutions?search={query}&per-page=1"
    try:
        data = fetch_json(url)
    except Exception:
        return 'Other'
    results = data.get('results', [])
    if not results:
        return 'Other'
    institution = results[0]
    country_code = institution.get('country_code')
    if country_code:
        country_code = country_code.upper()
        return COUNTRY_TO_REGION.get(country_code, 'Other')
    return 'Other'


def iterate_author_works(author_id: str) -> List[dict]:
    """Yield all works for a given author ID from OpenAlex.  Handles pagination.
    Returns a list of work dictionaries."""
    works: List[dict] = []
    cursor: str = '*'
    base = f"https://api.openalex.org/works?filter=author.id:{author_id}&per-page=200"
    while True:
        url = f"{base}&cursor={cursor}"
        data = fetch_json(url, sleep=0.1)
        works.extend(data.get('results', []))
        meta = data.get('meta', {})
        next_cursor = meta.get('next_cursor')
        if not next_cursor:
            break
        cursor = next_cursor
    return works


def get_venue_code(display_name: str) -> Optional[str]:
    """
    Return a venue code for a given OpenAlex host_venue display_name using
    fuzzy substring matching.  The display_name is lower‑cased and the first
    matching pattern in ``VENUE_PATTERNS`` determines the code.  If no
    pattern matches, returns None.
    """
    if not display_name:
        return None
    venue_lower = display_name.lower()
    for pattern, code in VENUE_PATTERNS:
        if pattern in venue_lower:
            return code
    return None


def build_dataset(
    csrankings_csv: str,
    min_year: int,
    max_year: int,
    max_authors: Optional[int] = None,
) -> dict:
    """
    Construct the dataset by processing authors and their works.  Returns a
    dictionary ready to be dumped to JSON.

    This implementation uses fuzzy venue matching via ``VENUE_PATTERNS`` to
    account for edition‑specific names (e.g. FOCS/STOC/SODA).  It also
    constructs human‑friendly venue names from ``VENUE_NAMES`` instead of
    deriving names directly from OpenAlex.
    """
    # Build unique list of venue codes and names
    venues: List[dict] = []
    for code in sorted(VENUE_NAMES.keys()):
        venues.append({'code': code, 'name': VENUE_NAMES[code]})

    institutions: Dict[str, dict] = {}
    authors_entries: List[dict] = []
    inst_key_map: Dict[str, str] = {}  # map from institution name to key

    # Read CSRankings faculty file
    with open(csrankings_csv, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        count = 0
        for row in reader:
            if max_authors is not None and count >= max_authors:
                break
            if not row:
                continue
            # CSRankings CSV format: name, affiliation, homepage, scholarid
            # Some lines may have extra spaces; strip them
            name = row[0].strip()
            affiliation = row[1].strip()
            if not name or not affiliation:
                continue
            count += 1
            log(f"Processing author {count}: {name} ({affiliation})")
            # Look up author in OpenAlex
            author_id = find_author_id(name)
            if not author_id:
                log(f"  Warning: could not find OpenAlex ID for {name}")
                continue
            works = iterate_author_works(author_id)
            # Build publication list for this author
            pub_list = []
            for work in works:
                year = work.get('publication_year')
                if year is None:
                    # Skip works without a publication year
                    continue
                if not (min_year <= year <= max_year):
                    continue
                host_venue = work.get('host_venue', {}) or {}
                display_name = host_venue.get('display_name', '') or ''
                code = get_venue_code(display_name)
                if not code:
                    # Skip works whose venue does not match any pattern
                    continue
                # For generic TCS venues FOCS/STOC/SODA, require quantum keywords
                if code in ('FOCS', 'STOC', 'SODA'):
                    title = work.get('title', '') or ''
                    title_lower = title.lower()
                    if title_lower:
                        if not any(kw in title_lower for kw in QUANTUM_KEYWORDS):
                            continue
                    else:
                        continue
                pub_list.append({'year': year, 'venue': code, 'title': work.get('title', '')})
            if not pub_list:
                continue
            # Determine institution key; create entry if necessary
            if affiliation not in inst_key_map:
                key = f"inst{len(inst_key_map)}"
                inst_key_map[affiliation] = key
                # Determine region using OpenAlex (may be slow)
                region = get_institution_region(affiliation)
                institutions[key] = {'name': affiliation, 'region': region}
            inst_key = inst_key_map[affiliation]
            authors_entries.append({
                'name': name,
                'institution': inst_key,
                'publications': pub_list
            })

    dataset = {
        'venues': venues,
        'institutions': institutions,
        'authors': authors_entries
    }
    return dataset


def main() -> None:
    parser = argparse.ArgumentParser(description='Build quantum dataset from CSRankings and OpenAlex.')
    parser.add_argument('--csrankings', type=str, default='csrankings.csv',
                        help='Path to csrankings.csv or URL (default: csrankings.csv in current dir)')
    parser.add_argument('--min-year', type=int, default=2005, help='Minimum publication year (inclusive)')
    parser.add_argument('--max-year', type=int, default=2025, help='Maximum publication year (inclusive)')
    parser.add_argument('--max-authors', type=int, default=None,
                        help='Maximum number of authors to process (for testing)')
    parser.add_argument('--output', type=str, default='data.json', help='Output JSON file')
    parser.add_argument('--output-js', type=str, default=None,
                        help='Optional: also write a JavaScript file with window.dataset assignment')
    args = parser.parse_args()

    # If the csrankings source is a URL, download it
    cs_file = args.csrankings
    if cs_file.startswith('http://') or cs_file.startswith('https://'):
        log(f"Downloading CSRankings file from {cs_file}")
        resp = requests.get(cs_file)
        resp.raise_for_status()
        cs_file_local = 'csrankings_download.csv'
        with open(cs_file_local, 'w', encoding='utf-8') as f:
            f.write(resp.text)
        cs_file = cs_file_local

    dataset = build_dataset(cs_file, args.min_year, args.max_year, args.max_authors)
    # Write JSON output
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(dataset, f, indent=2)
    log(f"Wrote dataset to {args.output} with {len(dataset['authors'])} authors and {len(dataset['institutions'])} institutions.")
    if args.output_js:
        mini = json.dumps(dataset, separators=(',', ':'))
        with open(args.output_js, 'w', encoding='utf-8') as f:
            f.write('window.dataset = ' + mini + ';\n')
        log(f"Wrote dataset JS file to {args.output_js}.")


if __name__ == '__main__':
    main()