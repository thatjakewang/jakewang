/* Period Performance switch on the Tesla dashboard. Every period is already
   rendered server-side; this only shows the chosen panel. */
(function () {
    var tabs = document.querySelectorAll(".period-tab[data-period]");

    tabs.forEach(function (tab) {
        tab.addEventListener("click", function () {
            tabs.forEach(function (other) {
                var active = other === tab;
                other.classList.toggle("is-active", active);
                other.setAttribute("aria-pressed", active ? "true" : "false");
                document.getElementById(other.getAttribute("aria-controls")).hidden = !active;
            });
        });
    });
})();
