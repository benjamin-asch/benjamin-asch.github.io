// Quantum research rankings script

let data = null;

// Subfield configuration: each subfield is a label plus a list of
// title keywords (all matched case-insensitively).  If one or more
// subfields are selected, a paper is counted only if its *title*
// contains at least one keyword from at least one selected subfield.
const subfieldConfig = {
  qcrypto: {
    label: 'Quantum cryptography / DI',
    keywords: [
      'quantum key distribution',
      'qkd',
      'device-independent',
      'device independent',
      'diqkd',
      'di-qkd',
      'semi-device-independent',
      'bb84',
      'ekert',
      'ekert91',
      'entanglement-based qkd',
      'entanglement based qkd',
      'prepare-and-measure',
      'prepare and measure',
      'randomness amplification',
      'randomness expansion',
      'entropy accumulation',
      'privacy amplification',
      'min-entropy',
      'smooth min-entropy',
      'composable security',
      'universally composable',
      'uc security',
      'quantum authentication',
      'authenticating quantum',
      'quantum oblivious transfer',
      'quantum bit commitment',
      'quantum coin flipping',
      'quantum coin-flipping'
    ]
  },

  qcomplexity: {
    label: 'Quantum complexity / verification',
    keywords: [
      // Classes
      'qma',
      'qma(2)',
      'qma( k )',
      'bqp',
      'qszk',
      'qcma',
      'qip',
      'qip(2)',
      'xmip*',
      'mip*',
      'mip* = re',

      // Proof systems / games / verification
      'interactive proof',
      'interactive proofs',
      'quantum interactive proof',
      'nonlocal game',
      'non-local game',
      'nonlocal games',
      'non-local games',
      'projection game',
      'entangled game',
      'entangled games',
      'xor game',
      'xor games',
      'self-testing',
      'self testing',
      'rigidity theorem',
      'rigidity theorems',
      'hamiltonian complexity',
      'local hamiltonian problem',
      'quantum pcp',
      'pcp for entangled',
      'quantum low-degree test',
      'low-degree test for entangled',
      'classical verification of quantum',
      'verifiable quantum computing',
      'blind quantum computing',
      'ma-protocol with quantum',
      'sum-check with quantum',
      'quantum prover interactive proof'
    ]
  },

  qinfo: {
    label: 'Quantum information theory',
    keywords: [
      'quantum channel',
      'quantum capacity',
      'entanglement-assisted capacity',
      'entanglement assisted capacity',
      'channel capacity',
      'coherent information',
      'private capacity',
      'squashed entanglement',
      'entanglement entropy',
      'von neumann entropy',
      'relative entropy of entanglement',
      'relative entropy',
      'entanglement of formation',
      'entanglement cost',
      'distillable entanglement',
      'entanglement distillation',
      'data hiding',
      'data-hiding',
      'lockable entanglement',
      'locking classical information',
      'holevo information',
      'holevo bound',
      'no-cloning',
      'no cloning',
      'no-broadcasting',
      'no broadcasting',
      'no-signalling',
      'no signalling',
      'one-shot coding',
      'one shot coding',
      'one-shot capacity',
      'information spectrum',
      'asymptotic equipartition property',
      'aep',
      'typical subspace',
      'decoupling theorem',
      'decoupling approach',
      'entropic uncertainty',
      'sandwiched rényi',
      'sandwiched renyi',
      'quantum mutual information',
      'symmetric extendibility',
      'loqc',
      'locc',
      'separable states',
      'separable state'
    ]
  },

  qec: {
    label: 'Quantum error correction / fault tolerance',
    keywords: [
      'quantum error correction',
      'quantum error-correcting code',
      'quantum error-correcting codes',
      'error-correcting code',
      'error-correcting codes',
      'stabilizer code',
      'stabilizer codes',
      'stabilizer formalism',
      'css code',
      'css codes',
      'surface code',
      'toric code',
      'color code',
      'color codes',
      'subsystem code',
      'subsystem codes',
      'gauge code',
      'topological code',
      'topological codes',
      'quantum ldpc',
      'ldpc code',
      'ldpc codes',
      'fault-tolerant',
      'fault tolerant',
      'fault-tolerance',
      'logical qubit',
      'logical qubits',
      'logical gate',
      'logical gates',
      'transversal gate',
      'transversal gates',
      'magic state distillation',
      'threshold theorem',
      'error threshold',
      'decoding algorithm',
      'decoder',
      'syndrome extraction',
      'syndrome measurement',
      'stabilizer measurement',
      'stabilizer decoding'
    ]
  },

  vqa: {
    label: 'VQAs / quantum optimization',
    keywords: [
      'variational quantum eigensolver',
      'vqe',
      'vqe-like',
      'variational quantum algorithm',
      'variational algorithm',
      'variational ansatz',
      'parameterized quantum circuit',
      'parameterised quantum circuit',
      'pqc',
      'ansatz circuit',
      'hardware-efficient ansatz',
      'hardware efficient ansatz',
      'quantum approximate optimization algorithm',
      'qaoa',
      'barren plateau',
      'barren plateaus',
      'energy landscape',
      'loss landscape',
      'quantum natural gradient',
      'quantum optimization',
      'quantum optimiser',
      'quantum optimizer',
      'variational simulator',
      'variational quantum simulation',
      'variational quantum linear solver'
    ]
  },

  qalgo: {
    label: 'Quantum algorithms',
    keywords: [
      'quantum algorithm',
      'quantum algorithms',
      'search algorithm',
      'grover',
      'grover\'s algorithm',
      'shor\'s algorithm',
      'shor',
      'phase estimation',
      'quantum fourier transform',
      'qft',
      'amplitude amplification',
      'amplitude estimation',
      'hamiltonian simulation',
      'linear systems algorithm',
      'quantum linear systems',
      'hhl',
      'quantum walk',
      'quantum walks',
      'continuous-time quantum walk',
      'discrete-time quantum walk',
      'boson sampling',
      'boson-sampling',
      'quantum metrology',
      'quantum sensing',
      'quantum search',
      'quantum speedup',
      'oracle separation'
    ]
  },

  qfoundations: {
    label: 'Foundations / nonlocality / contextuality',
    keywords: [
      'bell inequality',
      'bell inequalities',
      'chsh',
      'tsirelson bound',
      'tsirelson\'s bound',
      'contextuality',
      'noncontextuality',
      'non-contextuality',
      'kochen-specker',
      'kochen specker',
      'leggett-garg',
      'leggett garg',
      'macrorealism',
      'macro-realism',
      'hidden variable',
      'hidden variables',
      'ontological model',
      'ontological models',
      'psi-epistemic',
      'psi epistemic',
      'psi-ontic',
      'psi ontic',
      'measurement problem',
      'decoherence',
      'einstein-podolsky-rosen',
      'epr paradox',
      'wigner\'s friend',
      'frauchiger-renner'
    ]
  },

  hardware_supercond: {
    label: 'Superconducting qubits',
    keywords: [
      'superconducting qubit',
      'superconducting qubits',
      'transmon',
      'transmon qubit',
      'flux qubit',
      'fluxonium',
      'josephson junction',
      'josephson qubit',
      'gmon',
      'xmon',
      'coplanar waveguide',
      'microwave resonator',
      '3d cavity',
      '3d resonator',
      'cavity qed',
      'circuit qed',
      'circuit-qed'
    ]
  },

  hardware_trapped_ion: {
    label: 'Trapped-ion qubits',
    keywords: [
      'trapped ion',
      'trapped-ion',
      'paul trap',
      'penning trap',
      'ion chain',
      'ion trap quantum',
      'calcium ion',
      'ytterbium ion',
      '171yb',
      '40ca+',
      '40 ca+'
    ]
  },

  hardware_neutral_atom: {
    label: 'Neutral-atom qubits',
    keywords: [
      'neutral atom',
      'neutral-atom',
      'rydberg atom',
      'rydberg blockade',
      'rydberg array',
      'optical tweezer',
      'optical tweezers',
      'optical lattice clock',
      'optical lattice',
      'atomic array'
    ]
  },

  hardware_photonic: {
    label: 'Photonic qubits',
    keywords: [
      'photonic qubit',
      'photonic quantum',
      'integrated photonics',
      'waveguide array',
      'waveguide chip',
      'linear optical',
      'linear-optical',
      'spdc',
      'spontaneous parametric down-conversion',
      'single-photon source',
      'single photon source',
      'single-photon detector',
      'single photon detector',
      'homodyne detection',
      'heterodyne detection'
    ]
  }
};


let selectedVenues = new Set();
let selectedRegions = new Set();
// If this set is empty, no subfield filter is applied.
let selectedSubfields = new Set();

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
  const subfieldContainer = document.getElementById('subfieldFilters');


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
    venueContainer.appendChild(label);
    venueContainer.appendChild(checkbox);
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

  // Build subfield checkboxes (all start unchecked = no subfield filter)
  if (subfieldContainer) {
    Object.entries(subfieldConfig).forEach(([code, cfg]) => {
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.id = `subfield-${code}`;
      checkbox.value = code;
      checkbox.checked = false;
      checkbox.addEventListener('change', () => {
        if (checkbox.checked) {
          selectedSubfields.add(code);
        } else {
          selectedSubfields.delete(code);
        }
        // Live update when subfield filters change
        updateRanking();
      });

      const label = document.createElement('label');
      label.htmlFor = checkbox.id;
      label.textContent = cfg.label;
      label.title = `Matches title keywords like: ${cfg.keywords.slice(0, 4).join(', ')}…`;

      subfieldContainer.appendChild(label);
      subfieldContainer.appendChild(checkbox);
      subfieldContainer.appendChild(document.createTextNode(' '));
    });
  }  

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

  // Build the lower-cased list of active subfield keywords. If none are
  // selected, this array stays empty and no subfield filter is applied.
  const activeSubfieldKeywords = [];
  selectedSubfields.forEach(code => {
    const cfg = subfieldConfig[code];
    if (!cfg || !Array.isArray(cfg.keywords)) return;
    cfg.keywords.forEach(kw => {
      const trimmed = (kw || '').toLowerCase().trim();
      if (trimmed) {
        activeSubfieldKeywords.push(trimmed);
      }
    });
  });

  const rankings = [];

  // Compute statistics for each institution
  Object.keys(data.institutions).forEach(instKey => {
    const instInfo = data.institutions[instKey];
    // Skip if region not selected
    if (!selectedRegions.has(instInfo.region)) return;
    let pubCount = 0;
    let authorsList = [];
    let activeResearchers = 0;
    // Iterate through authors belonging to this institution
    data.authors.forEach(author => {
      if (author.institution !== instKey) return;
      let authorPubCount = 0;
      const pubDetails = [];
      // Count the author's publications that match the current filters
      author.publications.forEach(pub => {
        // Only consider publications within the year range and selected venues
        if (pub.year < startYear || pub.year > endYear || !selectedVenues.has(pub.venue)) {
          return;
        }

        const venue = pub.venue;
        const title = (pub.title || '').toLowerCase();

        // Optional subfield filter: if one or more subfields are selected,
        // require that the title contain at least one of the corresponding
        // keywords. If no subfields are selected, we keep everything.
        if (activeSubfieldKeywords.length > 0) {
          // If there's no title, we can't confidently assign a subfield; drop it.
          if (!title) {
            return;
          }
          const matchesSubfield = activeSubfieldKeywords.some(kw => title.includes(kw));
          if (!matchesSubfield) {
            return;
          }
        }

        // Count publication
        pubCount++;
        authorPubCount++;
        pubDetails.push(`${pub.year} – ${pub.venue}`);
      });

      // Only include authors with at least one relevant publication in this list
      if (authorPubCount > 0) {
        activeResearchers++;
        authorsList.push({
          name: author.name,
          count: authorPubCount,
          details: pubDetails
        });
      }
    });
    // If no researchers have publications under the current filters, skip this institution
    if (activeResearchers === 0) return;
    const ratio = pubCount / activeResearchers;
    rankings.push({
      institution: instKey,
      name: instInfo.name,
      region: instInfo.region,
      publications: pubCount,
      researcherCount: activeResearchers,
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