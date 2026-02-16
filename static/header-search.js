/* Global header search - loaded on every page */

(function () {
    'use strict';

    var input = document.getElementById('header-search-input');
    var dropdown = document.getElementById('header-search-results');
    if (!input || !dropdown) return;

    var searchIndex = null;
    var serverAvailable = null; // null = unknown, true/false after probe
    var debounceTimer;

    function escapeHtml(s) {
        return s.replace(/&/g, '&amp;').replace(/</g, '&lt;')
                .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    // Resolve a path relative to the current page
    function resolveRelativePath(path) {
        // path is relative to site root (e.g. "doc/installed-442/file/file1.html")
        // We need to make it relative to the current page
        var base = document.querySelector('link[rel="stylesheet"]');
        if (base) {
            var cssHref = base.getAttribute('href');
            // cssHref is like "../../style.css" — extract the prefix
            var prefix = cssHref.replace('style.css', '');
            return prefix + path;
        }
        return path;
    }

    async function loadSearchIndex() {
        if (searchIndex) return searchIndex;
        // Resolve path to search-index.json relative to current page
        var jsonPath = resolveRelativePath('search-index.json');
        try {
            var resp = await fetch(jsonPath);
            searchIndex = await resp.json();
        } catch (e) {
            searchIndex = [];
        }
        return searchIndex;
    }

    function clientSearch(query) {
        if (!searchIndex || !query) return [];
        var terms = query.toLowerCase().split(/\s+/).filter(function (t) { return t.length > 0; });
        var results = [];

        for (var i = 0; i < searchIndex.length; i++) {
            var entry = searchIndex[i];
            var title = (entry.title || '').toLowerCase();
            var text = (entry.text || '').toLowerCase();
            var type = (entry.type || '').toLowerCase();

            var score = 0;
            var matched = true;
            for (var j = 0; j < terms.length; j++) {
                var term = terms[j];
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
                results.push({
                    title: entry.title,
                    type: entry.type,
                    path: entry.path,
                    text: entry.text,
                    score: score
                });
            }
        }

        results.sort(function (a, b) { return b.score - a.score; });
        return results.slice(0, 10);
    }

    async function serverSearch(query) {
        try {
            var resp = await fetch('/api/search?q=' + encodeURIComponent(query) + '&mode=hybrid&limit=10');
            if (!resp.ok) throw new Error('HTTP ' + resp.status);
            var data = await resp.json();
            return data.results || [];
        } catch (e) {
            serverAvailable = false;
            return null;
        }
    }

    async function probeServer() {
        if (serverAvailable !== null) return;
        try {
            var resp = await fetch('/api/status');
            if (!resp.ok) throw new Error('HTTP ' + resp.status);
            var data = await resp.json();
            serverAvailable = !!(data && data.ok);
        } catch (e) {
            serverAvailable = false;
        }
    }

    function renderDropdown(results) {
        if (results.length === 0) {
            dropdown.innerHTML = '<div class="dropdown-item dropdown-empty">No results found</div>';
            dropdown.classList.add('visible');
            return;
        }

        dropdown.innerHTML = results.map(function (r) {
            var href = resolveRelativePath(r.path);
            var snippet = (r.text || '').substring(0, 80);
            return '<a class="dropdown-item" href="' + escapeHtml(href) + '">' +
                '<span class="dropdown-title">' + escapeHtml(r.title) + '</span>' +
                '<span class="dropdown-type">' + escapeHtml(r.type || '') + '</span>' +
                (snippet ? '<span class="dropdown-snippet">' + escapeHtml(snippet) + '</span>' : '') +
                '</a>';
        }).join('');
        dropdown.classList.add('visible');
    }

    function hideDropdown() {
        dropdown.classList.remove('visible');
    }

    async function doSearch() {
        var query = input.value.trim();
        if (!query) {
            hideDropdown();
            return;
        }

        // Try server first if available
        await probeServer();
        if (serverAvailable) {
            var results = await serverSearch(query);
            if (results !== null) {
                renderDropdown(results);
                return;
            }
        }

        // Fallback to client-side
        await loadSearchIndex();
        var clientResults = clientSearch(query);
        renderDropdown(clientResults);
    }

    // Debounced input handler
    input.addEventListener('input', function () {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(doSearch, 300);
    });

    // Enter key navigates to full search page
    input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            var query = input.value.trim();
            if (query) {
                var searchPage = resolveRelativePath('search.html');
                window.location.href = searchPage + '?q=' + encodeURIComponent(query);
            }
        }
        if (e.key === 'Escape') {
            hideDropdown();
            input.blur();
        }
    });

    // Close dropdown on outside click
    document.addEventListener('click', function (e) {
        if (!e.target.closest('.header-search')) {
            hideDropdown();
        }
    });

    // Re-show dropdown on focus if there's content
    input.addEventListener('focus', function () {
        if (input.value.trim() && dropdown.innerHTML) {
            dropdown.classList.add('visible');
        }
    });
})();
