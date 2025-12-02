# Quantum Research Rankings

This project implements a **quantum‑specific research ranking platform** inspired by CS theory rankings.  The site does **not reuse any of the CSRankings code or assets**, and it is intended for private use.  The goal is to provide a flexible tool for analysing the research productivity of universities in quantum information and computation.  It covers the period from **2005–2025** by default but allows the user to adjust the year range.

## Selection of venues

The platform focuses on major journals and conferences that are recognised as leading venues for quantum information science.  Journals such as *npj Quantum Information*, *PRX Quantum*, *Quantum*, *Quantum Information & Computation* and *ACM Transactions on Quantum Computing* are all explicitly listed on researcher Mark Wilde’s curated journal list【612732740359058†L34-L47】.  In addition to these, the platform includes the flagship theory conferences *Quantum Information Processing (QIP)*, *Theory of Quantum Computation, Communication and Cryptography (TQC)* and *QCrypt*, because they represent the best recent results in quantum computation and cryptography.  QIP is described as “the premier annual meeting for quantum information research”【792032660781572†L51-L60】.  TQC is recognised as a “leading annual international conference” in theoretical quantum information science【192540379572434†L58-L62】, and QCrypt explicitly aims to present the previous year’s best results in quantum cryptography【725400974355398†L27-L43】.

Although not exclusive to quantum research, the platform also allows filtering publications that appear in general theory venues such as **FOCS** and **STOC**.  FOCS is the flagship conference of the IEEE Computer Society’s Technical Committee on the Mathematical Foundations of Computing and is paired with its sister conference STOC【696845523441044†L8-L14】.  STOC, the flagship conference of ACM SIGACT, covers all areas of algorithms and computation theory, explicitly including quantum computing【235036322479565†L7-L19】.  By including these conferences, the tool can account for quantum results that appear in broader theoretical computer science venues.

## Features

The website is contained in this folder and functions entirely on the client side (no server is needed).  It includes the following features:

1. **Year range and venue selection.**  Users can choose a start and end year and select which journals and conferences to include when computing rankings.  Venues are listed with short codes (e.g., `QIP`, `TQC`, `NPJ_QI`, `PRX_Q`) but can be expanded by editing the `data.json` file or by adding new venues through the interface.

2. **Region filtering.**  Institutions are tagged with a geographic region (North America, Europe, Asia, Oceania, etc.), and users can exclude entire regions from the ranking.  This allows comparisons such as “North American universities only” or “Exclude Europe.”

3. **Sorting by productivity or efficiency.**  Rankings can be sorted either by the total number of publications or by the **publications‑per‑faculty ratio**, enabling users to consider the size of faculty when comparing productivity.

4. **Faculty details.**  Clicking on an institution in the ranking reveals a table listing individual faculty members from that university, along with their publication counts and the years/venues of each publication.

5. **Extendable venue list.**  A small form at the bottom of the page allows users to add new conference or journal codes for temporary experimentation without editing source files.  To make permanent changes, one can add entries to the `venues` array in `data.json`.

## Data and extensibility

The ranking is driven by a simple JSON file (`data.json`) that lists venues, institutions, and authors with their publication records.  The included data set is a **fictional example** intended to demonstrate the functionality of the ranking platform.  Each author entry contains an `institution` key, a list of `(year, venue)` pairs and is associated with one of the predefined institutions.  To adapt the tool for real data, you can:

* Add or remove **venues** in the `venues` array.  Each venue must have a unique short code and a descriptive name.
* Expand the **institutions** object with additional universities or research institutes and specify their geographic region.
* Populate the **authors** array with real faculty members and their publication records (including the year and venue code for each paper).  Publications outside the selected venues or year range are ignored.

Because everything is stored in a JSON file and processed on the client side, no server‑side code is required.  This design makes it straightforward to adapt the system to new venues or new datasets.

## Running locally

All files required for the website are contained in this folder.  To run the ranking platform locally:

1. Copy the `quantum_rankings` directory to a local machine.
2. Open `index.html` in a modern web browser.  No internet connection is required because the site operates entirely on local data.
3. Adjust the filters, click **Update Ranking**, and explore the faculty details by clicking on a school.

### Building a real dataset

The data included in this repository is a **small synthetic example** meant only to demonstrate the interface.  To generate a realistic dataset from publicly available sources, a Python script named `build_quantum_dataset.py` is provided.  It uses the [CSRankings faculty list](https://csrankings.org/) to identify researchers and the [OpenAlex](https://openalex.org/) API to harvest their publications.  Publications are filtered to include only those from the selected quantum venues (QIP, TQC, QCrypt, *npj QI*, *PRX Quantum*, *Quantum*, *QIC*, ACM TQC) and quantum‑relevant papers that appear in FOCS, STOC and SODA (determined by keywords).

To build a new dataset:

1. Install the `requests` library if you do not already have it:

   ```bash
   pip install requests
   ```

2. Download the CSRankings faculty CSV.  You can pass a URL directly to the script and it will download the file for you.  For example, to process the first 1,000 faculty in the list and collect publications from 2005–2025, run:

   ```bash
   cd quantum_rankings
   python build_quantum_dataset.py \
       --csrankings https://raw.githubusercontent.com/emeryberger/CSrankings/gh-pages/csrankings.csv \
       --min-year 2005 --max-year 2025 \
       --max-authors 1000 \
       --output data.json \
       --output-js data.js
   ```

   The `--max-authors` option is optional but recommended because downloading data for all authors can take hours.  Adjust this number as you see fit or omit it entirely to process the full list.

3. The script will create a JSON file (`data.json`) and, if you specify `--output-js`, a JavaScript file (`data.js`).  The JS file assigns the dataset to the global `window.dataset` variable.  Place `data.js` alongside `index.html` and the rankings page will automatically pick up the new data instead of the embedded synthetic example.  If you prefer to host `data.json` on a local web server, you can fetch it manually inside `script.js`—for example, by modifying the `loadData()` function to fetch `data.json`.

**Important:** The harvesting script relies on the OpenAlex API.  Although OpenAlex is free to use, you should avoid making thousands of requests in rapid succession.  The script includes a small delay between API calls, but you may still hit rate limits.  Feel free to adapt the script to cache intermediate results or restrict the number of authors processed.

### Alternative: build data by institution

The `build_quantum_dataset.py` workflow begins with the CSRankings faculty list, so it naturally focuses on faculty who can advise CS PhD students【717009529760304†L119-L124】.  If you want a more inclusive ranking that counts **any researcher who publishes quantum papers at a given institution**, regardless of department or faculty status, use the companion script `build_institution_dataset.py` in this directory.

To use it:

1. Create a plain text file (`institutions.txt`) containing one institution name per line.  For example:

   ```
   ETH Zürich
   University of Waterloo
   Perimeter Institute for Theoretical Physics
   MIT
   Caltech
   ```

2. Run the script with your desired year range and minimum paper count:

   ```bash
   python build_institution_dataset.py \
       --institutions-file institutions.txt \
       --min-year 2005 --max-year 2025 \
       --min-papers 3 \
       --output data.json \
       --output-js data.js
   ```

   This will look up each institution in OpenAlex, fetch all works in the given time window, filter them to quantum venues or titles containing quantum keywords, and aggregate publication counts by author.  Only authors with at least `--min-papers` qualifying publications are retained.  The resulting `data.json`/`data.js` files can be loaded by the website in the same way as above.

3. Place the generated `data.js` file next to `index.html` (or serve `data.json` via a local server) and reload the page.  The rankings will now reflect **researchers** instead of CS faculty and will include physicists, mathematicians, electrical engineers and others who publish quantum work at the institutions you specified.

Use the optional flags `--max-institutions` and `--max-works` to limit the number of institutions processed or the number of works fetched per institution, which can help when testing or avoiding excessive API usage.

## License

This tool is intended for private, educational use.  It does not reproduce any code from CSRankings (which is distributed under a no‑derivatives licence) and is provided as an independent demonstration of how one might rank universities based on quantum research publications.