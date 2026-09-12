/**
 * Shared utilities for dashboard pages
 *
 * Contains:
 *   - fetch / error helpers
 *   - table builder
 */

/* =========================================
   Fetch / error / loader helpers
   ========================================= */

/** Fetch JSON; throws on non-2xx */
async function safeFetch(url) {
    const res = await fetch(url, { credentials: "omit" });
    if (!res.ok) {
        throw new Error(`Request failed: ${res.status} ${res.statusText}`);
    }
    return res.json();
}

/** Set the text content of an element by id (no-op if missing) */
function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

/** Pluralization suffix: plural(1) === "", plural(2) === "s" */
const plural = n => (n === 1 ? "" : "s");

/** Mark a KPI card value element as errored */
function setKpiError(id, label = "Error") {
    const el = document.getElementById(id);
    if (!el) return;
    const card = el.closest(".kpi-card");
    if (card) card.classList.add("error");
    el.textContent = label;
    el.classList.add("error");
}

/** Mark a group of KPI cards as errored: the first reads "Error", the rest "—" */
function setKpiErrors(ids) {
    ids.forEach((id, i) => setKpiError(id, i === 0 ? "Error" : "—"));
}

/** Show an error message inside a container, replacing whatever it holds */
function showError(elementId, message = "Failed to load data") {
    const el = document.getElementById(elementId);
    if (!el) return;
    el.innerHTML = `<p class="dashboard-error">${message}</p>`;
}

/** Fetch JSON and hand it to render(); on failure log the error and run onError().
    Wraps the try/catch + console.error boilerplate shared by every loader. */
async function loadJSON(url, label, render, onError) {
    try {
        render(await safeFetch(url));
    } catch (err) {
        console.error(`Failed to load ${label}:`, err);
        onError(err);
    }
}

/** Draw one widget from an already-fetched payload, isolating its failures.
    Pages that fetch every widget in one request need this: without it a single
    renderer throwing would abort the rest of the page, which separate requests
    per widget used to prevent for free. */
function renderWidget(label, render, onError) {
    try {
        render();
    } catch (err) {
        console.error(`Failed to render ${label}:`, err);
        onError(err);
    }
}

/* =========================================
   Table builder
   ========================================= */

/**
 * Build and inject a dashboard-table into a container element.
 *
 * @param {string}   containerId  - ID of the wrapper element
 * @param {Array}    headers      - [{ label, cls }]
 * @param {Array}    rows         - array of data objects
 * @param {Function} cellMapper   - (row) => [{ value, cls }, ...]
 */
function buildTable(containerId, headers, rows, cellMapper) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const table = document.createElement("table");
    table.className = "dashboard-table";

    const thead = table.createTHead();
    const headerRow = thead.insertRow();
    headers.forEach(({ label, cls }) => {
        const th = document.createElement("th");
        th.textContent = label;
        if (cls) th.className = cls;
        headerRow.appendChild(th);
    });

    const tbody = table.createTBody();
    rows.forEach(row => {
        const tr = tbody.insertRow();
        cellMapper(row).forEach(({ value, cls }) => {
            const td = tr.insertCell();
            td.textContent = value;
            if (cls) td.className = cls;
        });
    });

    container.replaceChildren(table);
}
