/* Light and dark themes. Light is the default; dark is used only once the
   visitor has chosen it with the header's toggle, and the choice is kept in
   localStorage.

   Loaded in <head> without defer, so the theme is set before the first paint
   and a dark page never flashes light. It is a file rather than an inline
   script because the Content-Security-Policy allows no inline scripts. */
(function () {
    var KEY = "theme";
    var COLORS = { light: "#ffffff", dark: "#15171c" };
    var root = document.documentElement;

    function stored() {
        try {
            return localStorage.getItem(KEY);
        } catch (e) {
            // Storage can be blocked (private mode, site settings).
            return null;
        }
    }

    function current() {
        return root.getAttribute("data-theme") === "dark" ? "dark" : "light";
    }

    function apply(theme) {
        if (theme === "dark") {
            root.setAttribute("data-theme", "dark");
        } else {
            root.removeAttribute("data-theme");
        }
        // The browser's own chrome (mobile address bar) follows the page.
        var meta = document.querySelector('meta[name="theme-color"]');
        if (meta) meta.setAttribute("content", COLORS[theme]);
        var toggle = document.querySelector(".theme-toggle");
        if (toggle) {
            toggle.setAttribute(
                "aria-label",
                theme === "dark" ? "Switch to light mode" : "Switch to dark mode"
            );
        }
    }

    apply(stored() === "dark" ? "dark" : "light");

    document.addEventListener("DOMContentLoaded", function () {
        var toggle = document.querySelector(".theme-toggle");
        if (!toggle) return;
        // The button didn't exist yet when the theme was first applied.
        apply(current());
        toggle.addEventListener("click", function () {
            var next = current() === "dark" ? "light" : "dark";
            apply(next);
            try {
                localStorage.setItem(KEY, next);
            } catch (e) {
                // The theme still changes for this page.
            }
        });
    });
})();
