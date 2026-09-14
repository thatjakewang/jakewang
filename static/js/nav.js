/* Mobile hamburger menu for the site header (loaded with defer). */
(function () {
    var header = document.querySelector(".site-header");
    var toggle = document.querySelector(".nav-toggle");
    if (!header || !toggle) return;
    var content = document.querySelector(".container");

    function setOpen(open, restoreFocus) {
        var wasOpen = header.classList.contains("is-open");
        header.classList.toggle("is-open", open);
        document.body.classList.toggle("nav-open", open);
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
        toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
        if (content) content.inert = open;
        if (open || (wasOpen && restoreFocus)) toggle.focus();
    }

    toggle.addEventListener("click", function () {
        setOpen(!header.classList.contains("is-open"));
    });

    document.addEventListener("keydown", function (e) {
        if (!header.classList.contains("is-open")) return;
        if (e.key === "Escape") {
            e.preventDefault();
            setOpen(false, true);
        }
        if (e.key === "Tab") {
            var links = Array.from(header.querySelectorAll("a[href], button:not([disabled])"))
                .filter(function (el) { return el.getClientRects().length > 0; });
            var first = links[0];
            var last = links[links.length - 1];
            if (e.shiftKey && document.activeElement === first) {
                e.preventDefault();
                last.focus();
            } else if (!e.shiftKey && document.activeElement === last) {
                e.preventDefault();
                first.focus();
            }
        }
    });

    // Close after choosing a destination (mobile panel).
    header.querySelectorAll(".site-nav a, .header-cta").forEach(function (link) {
        link.addEventListener("click", function () { setOpen(false); });
    });

    // If the viewport grows past the mobile breakpoint, force-close.
    if (window.matchMedia) {
        var mq = window.matchMedia("(min-width: 721px)");
        var onChange = function (e) { if (e.matches) setOpen(false); };
        if (mq.addEventListener) mq.addEventListener("change", onChange);
        else if (mq.addListener) mq.addListener(onChange);
    }
})();
