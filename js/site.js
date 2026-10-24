// Vanilla replacements for the theme's jQuery behaviours: search toggle, mobile menu, confirm dialogs.
(function () {
    var $ = function (sel) { return document.querySelector(sel); };

    var searchForm = $('header#header form.search-form');
    var searchBox = $('header#header #search');
    var searchInput = $('header#header form.search-form input');

    var toggleSearch = $('#toggle-search');
    if (toggleSearch && searchForm) {
        toggleSearch.addEventListener('click', function () {
            searchForm.style.display = 'block';
            searchInput.focus();
        });
        document.addEventListener('mouseup', function (e) {
            if (!searchForm.contains(e.target) && e.target !== toggleSearch && !toggleSearch.contains(e.target)) {
                searchForm.style.display = '';
            }
        });
    }

    var mobileSearch = $('#mobile-search button');
    if (mobileSearch && searchBox) {
        mobileSearch.addEventListener('click', function (e) {
            e.preventDefault();
            searchBox.style.setProperty('display', 'block', 'important');
            searchForm.style.display = 'block';
            searchInput.focus();
        });
        document.addEventListener('mouseup', function (e) {
            if (!searchBox.contains(e.target) && !mobileSearch.contains(e.target)) {
                searchBox.style.removeProperty('display');
            }
        });
    }

    var nav = $('#main-nav');
    var openMenu = $('#mobile-menu button');
    var closeMenu = $('#main-nav button.close-menu');
    if (nav && openMenu) {
        openMenu.addEventListener('click', function (e) {
            e.preventDefault();
            nav.style.setProperty('display', 'block', 'important');
        });
    }
    if (nav && closeMenu) {
        closeMenu.addEventListener('click', function (e) {
            e.preventDefault();
            nav.style.removeProperty('display');
        });
    }

    // "Insert at cursor" buttons in the article form add the image's Markdown to the body.
    document.addEventListener('click', function (e) {
        var snippet = e.target.getAttribute && e.target.getAttribute('data-insert');
        var body = $('#body');
        if (!snippet || !body) { return; }
        var start = body.selectionStart, end = body.selectionEnd;
        body.value = body.value.slice(0, start) + '\n\n' + snippet + '\n\n' + body.value.slice(end);
        body.focus();
    });

    document.addEventListener('submit', function (e) {
        var message = e.target.getAttribute && e.target.getAttribute('data-confirm');
        if (message && !window.confirm(message)) {
            e.preventDefault();
        }
    });
})();
