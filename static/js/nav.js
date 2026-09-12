/* Mobile hamburger menu for the site header (loaded with defer). */
(function () {
    var header = document.querySelector(".site-header");
    var toggle = document.querySelector(".nav-toggle");
    if (!header || !toggle) return;

    function setOpen(open) {
        header.classList.toggle("is-open", open);
        document.body.classList.toggle("nav-open", open);
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
        toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
    }

    toggle.addEventListener("click", function () {
        setOpen(!header.classList.contains("is-open"));
    });

    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape") setOpen(false);
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
