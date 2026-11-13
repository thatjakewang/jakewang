/* Period Performance switch on the Tesla dashboard. Every period is already
   rendered server-side; this only shows the chosen panel. */
(function () {
    var tabs = document.querySelectorAll(".period-tab[data-period]");

    function showPeriod(selected) {
        tabs.forEach(function (tab) {
            var active = tab === selected;
            tab.classList.toggle("is-active", active);
            tab.setAttribute("aria-pressed", active ? "true" : "false");
            document.getElementById(tab.getAttribute("aria-controls")).hidden = !active;
        });
    }

    tabs.forEach(function (tab) {
        tab.addEventListener("click", function () { showPeriod(tab); });
    });
})();
