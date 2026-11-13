/* The Tesla dashboard's two interactive parts. Everything is already rendered
   server-side; this only chooses what is shown. */

/* Period Performance switch: shows the chosen period's panel. */
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

/* Monthly Cost chart: a readout of the month under the pointer or focus. The
   same numbers are in each column's label and in the table below the chart. */
(function () {
    var plot = document.querySelector(".cost-plot");
    if (!plot) return;
    var tooltip = plot.querySelector(".cost-tooltip");
    var columns = plot.querySelectorAll(".cost-column");

    function show(column) {
        tooltip.querySelectorAll("[data-readout]").forEach(function (part) {
            part.textContent = column.dataset[part.dataset.readout];
        });
        tooltip.hidden = false;
        // Centre on the column, but keep the box inside the plot's width.
        var half = tooltip.offsetWidth / 2;
        var centre = column.offsetLeft + column.offsetWidth / 2;
        var left = Math.max(half, Math.min(centre, plot.clientWidth - half));
        tooltip.style.left = left + "px";
    }

    function hide() {
        tooltip.hidden = true;
    }

    columns.forEach(function (column) {
        column.addEventListener("pointerenter", function (e) {
            if (e.pointerType === "mouse") show(column);
        });
        column.addEventListener("pointerleave", function (e) {
            if (e.pointerType === "mouse" && document.activeElement !== column) hide();
        });
        column.addEventListener("focus", function () { show(column); });
        column.addEventListener("blur", hide);
        // A tap doesn't focus a button in every browser, so show on click too.
        column.addEventListener("click", function () { show(column); });
    });

    // A tap outside the columns dismisses a readout opened by a tap.
    document.addEventListener("click", function (e) {
        if (!e.target.closest(".cost-column")) hide();
    });
})();
