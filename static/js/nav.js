/* Mobile hamburger menu for the site header (loaded with defer). */
(function () {
    var header = document.querySelector(".site-header");
    var toggle = document.querySelector(".nav-toggle");
    if (!header || !toggle) return;
    var content = document.querySelector(".container");

    function isOpen() {
        return header.classList.contains("is-open");
    }

    function setOpen(open, restoreFocus) {
        var wasOpen = isOpen();
        header.classList.toggle("is-open", open);
        document.body.classList.toggle("nav-open", open);
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
        toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
        if (content) content.inert = open;
        if (open || (wasOpen && restoreFocus)) toggle.focus();
    }

    // Keep Tab inside the open menu: wrap from the last control to the first
    // and back.
    function trapFocus(e) {
        var controls = Array.from(header.querySelectorAll("a[href], button:not([disabled])"))
            .filter(function (el) { return el.getClientRects().length > 0; });
        var first = controls[0];
        var last = controls[controls.length - 1];
        if (e.shiftKey && document.activeElement === first) {
            e.preventDefault();
            last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
            e.preventDefault();
            first.focus();
        }
    }

    toggle.addEventListener("click", function () {
        setOpen(!isOpen());
    });

    document.addEventListener("keydown", function (e) {
        if (!isOpen()) return;
        if (e.key === "Escape") {
            e.preventDefault();
            setOpen(false, true);
        } else if (e.key === "Tab") {
            trapFocus(e);
        }
    });

    // Close after choosing a destination (mobile panel).
    header.querySelectorAll(".site-nav a, .header-cta").forEach(function (link) {
        link.addEventListener("click", function () { setOpen(false); });
    });

    // If the viewport grows past the mobile breakpoint (720px in style.css),
    // force-close.
    window.matchMedia("(min-width: 721px)").addEventListener("change", function (e) {
        if (e.matches) setOpen(false);
    });
})();
