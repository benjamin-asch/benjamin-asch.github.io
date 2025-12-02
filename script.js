// Quantum research rankings script

let data = null;

// List of keywords that indicate a quantum‐related publication.  When
// counting FOCS, STOC, and SODA papers, only publications whose title
// contains at least one of these keywords (case‐insensitive) will be
// considered.  This helps filter out general theory papers that are
// unrelated to quantum information science.
const quantumKeywords = [
  'quantum',
  'qubit',
  'qutrit',
  'entanglement',
  'quantum computing',
  'quantum information',
  'quantum algorithm',
  'quantum error correction',
  'quantum cryptography',
  'quantum complexity'
];
let selectedVenues = new Set();
let selectedRegions = new Set();

// Load dataset from the embedded JSON script element and initialise UI
async function loadData() {
  // First check if a global dataset has been loaded via data.js.  This allows
  // loading much larger datasets without embedding them directly in the HTML.
  if (window.dataset) {
    data = window.dataset;
  } else {
    // Fallback: try to read the embedded JSON dataset (for backwards
    // compatibility).  The script tag with id="dataset" contains either
    // plain JSON or a base64 encoded JSON object.
    const datasetScript = document.getElementById('dataset');
    if (datasetScript) {
      try {
        const rawContent = datasetScript.textContent.trim();
        const parsed = JSON.parse(rawContent);
        if (parsed && parsed.base64) {
          try {
            const decoded = atob(parsed.base64);
            data = JSON.parse(decoded);
          } catch (err) {
            console.error('Failed to decode base64 dataset', err);
          }
        } else {
          data = parsed;
        }
      } catch (err) {
        console.error('Failed to parse embedded dataset', err);
      }
    }
  }
  // If data is still null after checking window.dataset and embedded script,
  // attempt to fetch a local JSON file called data.json.  This fetch
  // requires that the site be served over HTTP; it will not work if
  // index.html is opened directly from disk due to browser CORS
  // restrictions.  If you run a local server (e.g. `python -m http.server`)
  // in the directory containing index.html and data.json, this will load
  // the dataset automatically.
  if (!data) {
    try {
      const resp = await fetch('data.json');
      if (resp.ok) {
        data = await resp.json();
      }
    } catch (err) {
      // ignore errors
    }
  }
  if (!data) {
    console.error('Dataset not found.');
    return;
  }
  initialiseUI();
  updateRanking();
}

// Populate venue and region filters
function initialiseUI() {
  const venueContainer = document.getElementById('venueFilters');
  const regionContainer = document.getElementById('regionFilters');

  // Build venue checkboxes
  data.venues.forEach(venue => {
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.id = `venue-${venue.code}`;
    checkbox.value = venue.code;
    checkbox.checked = true;
    checkbox.addEventListener('change', () => {
      if (checkbox.checked) {
        selectedVenues.add(venue.code);
      } else {
        selectedVenues.delete(venue.code);
      }
    });
    selectedVenues.add(venue.code);
    const label = document.createElement('label');
    label.htmlFor = checkbox.id;
    label.textContent = venue.code;
    venueContainer.appendChild(checkbox);
    venueContainer.appendChild(label);
    venueContainer.appendChild(document.createTextNode(' '));
  });

  // Build region checkboxes
  const regions = new Set();
  Object.values(data.institutions).forEach(inst => regions.add(inst.region));
  regions.forEach(region => {
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.id = `region-${region}`;
    checkbox.value = region;
    checkbox.checked = true;
    checkbox.addEventListener('change', () => {
      if (checkbox.checked) {
        selectedRegions.add(region);
      } else {
        selectedRegions.delete(region);
      }
    });
    selectedRegions.add(region);
    const label = document.createElement('label');
    label.htmlFor = checkbox.id;
    label.textContent = region;
    regionContainer.appendChild(checkbox);
    regionContainer.appendChild(label);
    regionContainer.appendChild(document.createTextNode(' '));
  });

  // Update button
  document.getElementById('updateBtn').addEventListener('click', updateRanking);

  // Sort method change triggers update
  document.getElementById('sortMethod').addEventListener('change', updateRanking);

  // Add venue button
  document.getElementById('addVenueBtn').addEventListener('click', () => {
    const codeInput = document.getElementById('newVenueCode');
    const nameInput = document.getElementById('newVenueName');
    const code = codeInput.value.trim();
    const name = nameInput.value.trim();
    if (!code || !name) {
      alert('Both code and name are required to add a venue.');
      return;
    }
    // Prevent duplicates by code
    const exists = data.venues.find(v => v.code.toLowerCase() === code.toLowerCase());
    if (exists) {
      alert(`Venue code ${code} already exists.`);
      return;
    }
    data.venues.push({ code: code, name: name });
    // Add to UI
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.id = `venue-${code}`;
    checkbox.value = code;
    checkbox.checked = true;
    checkbox.addEventListener('change', () => {
      if (checkbox.checked) {
        selectedVenues.add(code);
      } else {
        selectedVenues.delete(code);
      }
    });
    selectedVenues.add(code);
    const label = document.createElement('label');
    label.htmlFor = checkbox.id;
    label.textContent = code;
    venueContainer.appendChild(checkbox);
    venueContainer.appendChild(label);
    venueContainer.appendChild(document.createTextNode(' '));
    // Clear inputs
    codeInput.value = '';
    nameInput.value = '';
    updateRanking();
  });

  // Scrape institution statistics button
  const scrapeBtn = document.getElementById('scrapeBtn');
  if (scrapeBtn) {
    scrapeBtn.addEventListener('click', scrapeInstitution);
  }
}

// Update ranking table based on current filters
function updateRanking() {
  const startYear = parseInt(document.getElementById('startYear').value, 10);
  const endYear = parseInt(document.getElementById('endYear').value, 10);
  const sortMethod = document.getElementById('sortMethod').value;

  const rankings = [];

  // Compute statistics for each institution
  Object.keys(data.institutions).forEach(instKey => {
    const instInfo = data.institutions[instKey];
    // Skip if region not selected
    if (!selectedRegions.has(instInfo.region)) return;
    let pubCount = 0;
    let authorsList = [];
    let researcherCount = 0;
    // Filter authors (researchers) of this institution
    data.authors.forEach(author => {
      if (author.institution === instKey) {
        researcherCount++;
        let authorPubCount = 0;
        const pubDetails = [];
        author.publications.forEach(pub => {
          // Only consider publications within the year range and selected venues
          if (pub.year < startYear || pub.year > endYear || !selectedVenues.has(pub.venue)) {
            return;
          }
          // For FOCS, STOC and SODA venues, include the publication only if its
          // title contains a quantum keyword.  Titles are stored on each
          // publication object; fallback to empty string if missing.
          const venue = pub.venue;
          const title = (pub.title || '').toLowerCase();
          if ((venue === 'FOCS' || venue === 'STOC' || venue === 'SODA')) {
            // Only apply keyword filtering when a title is provided.  Many
            // entries in the dataset omit titles; in those cases we assume
            // the paper is quantum‐related and include it in the count.  If
            // a title is present, require that it contain one of the
            // quantum keywords.
            if (title) {
              const hasKeyword = quantumKeywords.some(kw => title.includes(kw.toLowerCase()));
              if (!hasKeyword) {
                return; // skip non‑quantum theory paper
              }
            }
          }
          // Count publication
          pubCount++;
          authorPubCount++;
          pubDetails.push(`${pub.year} – ${pub.venue}`);
        });
        authorsList.push({
          name: author.name,
          count: authorPubCount,
          details: pubDetails
        });
      }
    });
    if (researcherCount === 0) return;
    const ratio = researcherCount > 0 ? pubCount / researcherCount : 0;
    rankings.push({
      institution: instKey,
      name: instInfo.name,
      region: instInfo.region,
      publications: pubCount,
      researcherCount: researcherCount,
      ratio: ratio,
      authors: authorsList
    });
  });

  // Sort according to selected method
  rankings.sort((a, b) => {
    if (sortMethod === 'total') {
      if (b.publications === a.publications) {
        return a.name.localeCompare(b.name);
      }
      return b.publications - a.publications;
    } else {
      if (b.ratio === a.ratio) {
        return a.name.localeCompare(b.name);
      }
      return b.ratio - a.ratio;
    }
  });

  // Populate ranking table
  const tbody = document.querySelector('#rankingTable tbody');
  tbody.innerHTML = '';
  rankings.forEach((entry, index) => {
    const tr = document.createElement('tr');
    tr.dataset.institution = entry.institution;
    tr.innerHTML = `
      <td>${index + 1}</td>
      <td>${entry.name}</td>
      <td>${entry.region}</td>
      <td>${entry.publications}</td>
      <td>${entry.researcherCount}</td>
      <td>${entry.ratio.toFixed(2)}</td>
    `;
    tr.addEventListener('click', () => showDetails(entry));
    tbody.appendChild(tr);
  });

  // Hide details section if no selection
  const detailsSection = document.getElementById('detailsSection');
  detailsSection.style.display = 'none';
}

// Show faculty details for selected institution
function showDetails(entry) {
  const detailsSection = document.getElementById('detailsSection');
  const detailsTitle = document.getElementById('detailsTitle');
  const detailsTableBody = document.querySelector('#detailsTable tbody');
  detailsTableBody.innerHTML = '';
  detailsTitle.textContent = `Faculty Details – ${entry.name}`;
  entry.authors.forEach(author => {
    const row = document.createElement('tr');
    const detailsString = author.details.join(', ');
    row.innerHTML = `
      <td>${author.name}</td>
      <td>${author.count}</td>
      <td>${detailsString}</td>
    `;
    detailsTableBody.appendChild(row);
  });
  detailsSection.style.display = 'block';
}

// Experimental scraping function.  Attempts to query a public search API via
// a CORS proxy to retrieve information about quantum research at a given
// institution.  Results are not automatically integrated into the dataset;
// instead, they are logged to the console for manual review.
function scrapeInstitution() {
  const input = document.getElementById('scrapeInput');
  if (!input) return;
  const name = input.value.trim();
  if (!name) {
    alert('Please enter an institution name before scraping.');
    return;
  }
  // Build a query that targets quantum information science at the institution.
  const query = encodeURIComponent(`${name} quantum information publications`);
  // Use DuckDuckGo Instant Answer API via a proxy to avoid CORS issues.  This
  // endpoint returns JSON with related topics; it is used here as a simple
  // demonstration.  Note that reliability may vary, and scraping may not
  // always succeed.
  const apiUrl = 'https://api.allorigins.win/raw?url=' + encodeURIComponent(`https://api.duckduckgo.com/?q=${query}&format=json`);
  fetch(apiUrl)
    .then(resp => resp.json())
    .then(data => {
      console.log('Scrape result for', name, data);
      alert(`Scraping complete. Check the browser console for details on ${name}.`);
    })
    .catch(err => {
      console.error('Scrape error:', err);
      alert('Failed to retrieve data from the web. This feature may be limited by network or CORS restrictions.');
    });
}

// Initialise after DOM content loaded
document.addEventListener('DOMContentLoaded', loadData);