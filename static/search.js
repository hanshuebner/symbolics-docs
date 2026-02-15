/* Client-side search for SAB documentation */

let searchIndex = null;

async function loadIndex() {
    if (searchIndex) return searchIndex;
    const resp = await fetch('search-index.json');
    searchIndex = await resp.json();
    return searchIndex;
}

function search(query) {
    if (!searchIndex || !query) return [];
    const terms = query.toLowerCase().split(/\s+/).filter(t => t.length > 0);
    const results = [];

    for (const entry of searchIndex) {
        const title = (entry.title || '').toLowerCase();
        const text = (entry.text || '').toLowerCase();
        const type = (entry.type || '').toLowerCase();

        let score = 0;
        let matched = true;
        for (const term of terms) {
            if (title.includes(term)) {
                score += 10;
            } else if (type.includes(term)) {
                score += 5;
            } else if (text.includes(term)) {
                score += 1;
            } else {
                matched = false;
                break;
            }
        }

        if (matched && score > 0) {
            results.push({ ...entry, score });
        }
    }

    results.sort((a, b) => b.score - a.score);
    return results.slice(0, 100);
}

function renderResults(results, container) {
    if (results.length === 0) {
        container.innerHTML = '<li>No results found.</li>';
        return;
    }
    container.innerHTML = results.map(r => {
        const snippet = (r.text || '').substring(0, 200);
        return `<li>
            <div class="title"><a href="${r.path}">${escapeHtml(r.title)}</a></div>
            <div class="path">${escapeHtml(r.type)} &mdash; ${escapeHtml(r.file)}</div>
            <div class="snippet">${escapeHtml(snippet)}</div>
        </li>`;
    }).join('');
}

function escapeHtml(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('search-input');
    const resultsList = document.getElementById('search-results');
    if (!input || !resultsList) return;

    let debounceTimer;
    input.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(async () => {
            await loadIndex();
            const results = search(input.value);
            renderResults(results, resultsList);
        }, 200);
    });

    // Load index on page load
    loadIndex();
});
