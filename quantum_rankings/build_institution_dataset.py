#!/usr/bin/env python3
"""
build_institution_dataset.py
============================

This script constructs a quantum research dataset organised by institution rather
than by individual faculty members.  Instead of starting from a list of
faculty (as in CSRankings), it queries the OpenAlex API for all works
associated with each institution in a given list, filters those works to
quantum venues and keywords, and then aggregates publication counts by author.

The resulting dataset can be consumed by the Quantum Research Rankings
frontend to rank institutions by the total number of quantum publications or by
publications per researcher.  Authors are included simply because they have
published at the institution in the selected venues, not because they are
tenure‑track faculty.  This makes the ranking more inclusive of physicists,
engineers and mathematicians working on quantum information science.

Usage example:

  python build_institution_dataset.py \
      --institutions-file institutions.txt \
      --min-year 2005 --max-year 2025 \
      --min-papers 3 \
      --output data.json \
      --output-js data.js

Dependencies: requires the `requests` library (install with `pip install
requests`).

Note: Querying OpenAlex can involve many requests.  Use the `--max-institutions` and
`--min-papers` flags to limit the workload.  Consider caching responses or
running the script in batches if you plan to harvest data for many
institutions.
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
# Configuration (copied from build_quantum_dataset.py)
###############################################################################

# Patterns for fuzzy matching of OpenAlex venue display names to short codes.
# Each tuple consists of a substring pattern (lower‑case) and the corresponding
# venue code.  Patterns are checked in order; the first match wins.
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

# Mapping from ISO country codes (uppercase) to broad regions.  This helps
# populate the `region` field for institutions.  The mapping is deliberately
# coarse and can be refined as needed.
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


def find_institution_id(name: str) -> Optional[str]:
    """Look up an institution in OpenAlex and return its ID (without the prefix)."""
    query = urllib.parse.quote(name)
    url = f"https://api.openalex.org/institutions?search={query}&per-page=1"
    try:
        data = fetch_json(url)
    except Exception:
        return None
    results = data.get('results', [])
    if not results:
        return None
    inst = results[0]
    inst_id = inst['id'].split('/')[-1]
    return inst_id


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


def iterate_institution_works(inst_id: str, min_year: int, max_year: int, max_works: Optional[int] = None) -> List[dict]:
    """Fetch works associated with a given institution ID from OpenAlex.  Handles
    pagination and returns a list of work dictionaries.  If max_works is
    provided, stops after collecting at least that many works."""
    works: List[dict] = []
    cursor: str = '*'
    base = f"https://api.openalex.org/works?filter=institutions.id:{inst_id}&per-page=200"
    while True:
        url = f"{base}&cursor={cursor}"
        data = fetch_json(url, sleep=0.1)
        page_results = data.get('results', [])
        for work in page_results:
            year = work.get('publication_year')
            if year is None or year < min_year or year > max_year:
                continue
            works.append(work)
            if max_works and len(works) >= max_works:
                return works
        meta = data.get('meta', {})
        next_cursor = meta.get('next_cursor')
        if not next_cursor:
            break
        cursor = next_cursor
    return works


def get_venue_code(display_name: str) -> Optional[str]:
    """
    Return a venue code for a given OpenAlex host_venue display_name using
    fuzzy substring matching.  The display_name is lower‑cased and the
    first matching pattern in ``VENUE_PATTERNS`` determines the code.  If
    no pattern matches, returns None.
    """
    if not display_name:
        return None
    venue_lower = display_name.lower()
    for pattern, code in VENUE_PATTERNS:
        if pattern in venue_lower:
            return code
    return None


def build_dataset(
    institutions_list: List[str],
    min_year: int,
    max_year: int,
    min_papers: int = 1,
    max_institutions: Optional[int] = None,
    max_works_per_inst: Optional[int] = None,
) -> dict:
    """
    Construct the dataset by processing institutions and their works.  Returns
    a dictionary ready to be dumped to JSON.

    This implementation uses fuzzy venue matching via ``VENUE_PATTERNS`` to
    account for edition‑specific names (e.g. FOCS/STOC/SODA).  It also
    constructs human‑friendly venue names from ``VENUE_NAMES``.
    """
    # Build unique list of venue codes and names
    venues: List[dict] = []
    for code in sorted(VENUE_NAMES.keys()):
        venues.append({'code': code, 'name': VENUE_NAMES[code]})

    institutions: Dict[str, dict] = {}
    authors_entries: List[dict] = []
    inst_key_map: Dict[str, str] = {}
    inst_count = 0

    for inst_name in institutions_list:
        if max_institutions is not None and inst_count >= max_institutions:
            break
        inst_name = inst_name.strip()
        if not inst_name:
            continue
        log(f"Processing institution: {inst_name}")
        inst_id = find_institution_id(inst_name)
        if not inst_id:
            log(f"  Warning: could not find OpenAlex ID for {inst_name}")
            continue
        works = iterate_institution_works(inst_id, min_year, max_year, max_works_per_inst)
        if not works:
            log(f"  No works found for {inst_name} in the given range.")
            continue
        # Aggregate works by author
        author_stats: Dict[str, dict] = defaultdict(lambda: {'name': None, 'count': 0, 'pubs': []})
        for work in works:
            host_venue = work.get('host_venue', {}) or {}
            display_name = host_venue.get('display_name', '') or ''
            code = get_venue_code(display_name)
            if not code:
                continue
            # For FOCS/STOC/SODA, check quantum keywords
            if code in ('FOCS', 'STOC', 'SODA'):
                title = work.get('title', '') or ''
                title_lower = title.lower()
                if title_lower:
                    has_keyword = any(kw in title_lower for kw in QUANTUM_KEYWORDS)
                    if not has_keyword:
                        continue
                else:
                    continue
            year = work.get('publication_year')
            # For each authorship, check if the author is affiliated with this institution
            for authorship in work.get('authorships', []):
                author = authorship.get('author')
                if not author:
                    continue
                insts = authorship.get('institutions', [])
                # Determine if this author is associated with the target institution
                belongs = False
                for inst in insts:
                    # Each inst has id e.g. https://openalex.org/I123...
                    inst_uri = inst.get('id')
                    if inst_uri and inst_uri.split('/')[-1] == inst_id:
                        belongs = True
                        break
                if not belongs:
                    continue
                aid = author.get('id')
                if not aid:
                    continue
                aid_short = aid.split('/')[-1]
                name = author.get('display_name') or author.get('name')
                if not name:
                    continue
                stats = author_stats[aid_short]
                stats['name'] = name
                stats['count'] += 1
                stats['pubs'].append({'year': year, 'venue': code, 'title': work.get('title', '')})
        # Filter authors by min_papers
        filtered_authors = {aid: info for aid, info in author_stats.items() if info['count'] >= min_papers}
        if not filtered_authors:
            log(f"  No authors with at least {min_papers} quantum publications found for {inst_name}.")
            continue
        # Create institution entry
        key = f"inst{len(inst_key_map)}"
        inst_key_map[inst_name] = key
        region = get_institution_region(inst_name)
        institutions[key] = {'name': inst_name, 'region': region}
        inst_count += 1
        # Create author entries
        for aid, info in filtered_authors.items():
            authors_entries.append({
                'name': info['name'],
                'institution': key,
                'publications': info['pubs']
            })
    dataset = {
        'venues': venues,
        'institutions': institutions,
        'authors': authors_entries
    }
    return dataset


def main() -> None:
    parser = argparse.ArgumentParser(description='Build quantum dataset by institution using OpenAlex.')
    parser.add_argument('--institutions-file', type=str, required=True,
                        help='Path to a text file containing one institution name per line.')
    parser.add_argument('--min-year', type=int, default=2005, help='Minimum publication year (inclusive)')
    parser.add_argument('--max-year', type=int, default=2025, help='Maximum publication year (inclusive)')
    parser.add_argument('--min-papers', type=int, default=1,
                        help='Minimum number of quantum publications required for an author to be included')
    parser.add_argument('--max-institutions', type=int, default=None,
                        help='Maximum number of institutions to process (for testing)')
    parser.add_argument('--max-works', type=int, default=None,
                        help='Maximum number of works to fetch per institution (for testing)')
    parser.add_argument('--output', type=str, default='data.json', help='Output JSON file')
    parser.add_argument('--output-js', type=str, default=None,
                        help='Optional: also write a JavaScript file with window.dataset assignment')
    args = parser.parse_args()

    # Read institution names
    with open(args.institutions_file, 'r', encoding='utf-8') as f:
        institutions_list = [line.strip() for line in f if line.strip()]

    dataset = build_dataset(institutions_list, args.min_year, args.max_year,
                            min_papers=args.min_papers,
                            max_institutions=args.max_institutions,
                            max_works_per_inst=args.max_works)

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