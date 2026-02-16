/* Semantic search client - enhances search page when API server is available */

(function () {
    'use strict';

    const input = document.getElementById('search-input');
    const resultsList = document.getElementById('search-results');
    const modeSelector = document.getElementById('search-mode');
    const statusEl = document.getElementById('server-status');
    if (!input || !resultsList) return;

    let serverAvailable = false;
    let debounceTimer;

    function escapeHtml(s) {
        return s.replace(/&/g, '&amp;').replace(/</g, '&lt;')
                .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function setStatus(text, ok) {
        if (!statusEl) return;
        statusEl.textContent = text;
        statusEl.className = 'server-status ' + (ok ? 'status-ok' : 'status-off');
    }

    function renderResults(results) {
        if (results.length === 0) {
            resultsList.innerHTML = '<li>No results found.</li>';
            return;
        }
        resultsList.innerHTML = results.map(function (r) {
            const sourceBadge = r.source
                ? '<span class="source-badge source-' + escapeHtml(r.source) + '">' + escapeHtml(r.source) + '</span>'
                : '';
            const snippet = r.text ? '<div class="snippet">' + escapeHtml(r.text.substring(0, 200)) + '</div>' : '';
            return '<li>' +
                '<div class="title"><a href="' + escapeHtml(r.path) + '">' + escapeHtml(r.title) + '</a> ' + sourceBadge + '</div>' +
                '<div class="path">' + escapeHtml(r.type || '') + '</div>' +
                snippet +
                '</li>';
        }).join('');
    }

    async function searchServer(query) {
        const mode = modeSelector ? modeSelector.value : 'hybrid';
        try {
            const resp = await fetch('/api/search?q=' + encodeURIComponent(query) + '&mode=' + mode + '&limit=50');
            if (!resp.ok) throw new Error('HTTP ' + resp.status);
            const data = await resp.json();
            return data.results || [];
        } catch (e) {
            console.warn('Server search failed, falling back to client-side:', e);
            serverAvailable = false;
            setStatus('Server offline - using client-side search', false);
            if (modeSelector) modeSelector.disabled = true;
            return null;
        }
    }

    async function doSearch() {
        const query = input.value.trim();
        if (!query) {
            resultsList.innerHTML = '';
            return;
        }

        if (serverAvailable) {
            const results = await searchServer(query);
            if (results !== null) {
                renderResults(results);
                return;
            }
        }

        // Fall back to client-side keyword search (search.js)
        if (typeof window.loadIndex === 'function' && typeof window.search === 'function') {
            await window.loadIndex();
            const results = window.search(query);
            renderResults(results);
        }
    }

    input.addEventListener('input', function () {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(doSearch, 300);
    });

    if (modeSelector) {
        modeSelector.addEventListener('change', function () {
            if (input.value.trim()) doSearch();
        });
    }

    // Check for ?q= parameter and auto-run search
    function checkQueryParam() {
        var params = new URLSearchParams(window.location.search);
        var q = params.get('q');
        if (q && input) {
            input.value = q;
            // Also fill in the header search input if present
            var headerInput = document.getElementById('header-search-input');
            if (headerInput) headerInput.value = q;
            // Trigger search after a short delay to allow index/server probe to settle
            setTimeout(doSearch, 100);
        }
    }
    checkQueryParam();

    // Probe for API availability
    fetch('/api/status')
        .then(function (resp) {
            if (!resp.ok) throw new Error('HTTP ' + resp.status);
            return resp.json();
        })
        .then(function (data) {
            if (data.ok) {
                serverAvailable = true;
                const parts = [];
                if (data.has_semantic) parts.push('semantic');
                if (data.has_keyword) parts.push('keyword');
                setStatus('Server: ' + parts.join(' + '), true);
                if (modeSelector) modeSelector.disabled = false;
            }
        })
        .catch(function () {
            setStatus('Client-side search only', false);
            if (modeSelector) modeSelector.disabled = true;
        });
})();
