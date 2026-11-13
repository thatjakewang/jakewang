/* The Tesla dashboard's interactive parts. Everything is already rendered
   server-side; this only chooses what is shown. */

/* Tab groups: the Period Performance switch and the Monthly Cost view switch.
   Each tab names its panel in aria-controls; choosing one shows that panel and
   hides the others in the same group. */
(function () {
    document.querySelectorAll(".period-tabs").forEach(function (group) {
        var tabs = group.querySelectorAll(".period-tab");

        function showPanel(selected) {
            tabs.forEach(function (tab) {
                var active = tab === selected;
                tab.classList.toggle("is-active", active);
                tab.setAttribute("aria-pressed", active ? "true" : "false");
                document.getElementById(tab.getAttribute("aria-controls")).hidden = !active;
            });
        }

        tabs.forEach(function (tab) {
            tab.addEventListener("click", function () { showPanel(tab); });
        });
    });
})();

/* Monthly Cost chart: a readout of the month under the pointer or focus. The
   same numbers are in each column's label and in the table below the chart. */
(function () {
    var plots = document.querySelectorAll(".cost-plot");

    plots.forEach(function (plot) {
        var tooltip = plot.querySelector(".cost-tooltip");

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

        plot.querySelectorAll(".cost-column").forEach(function (column) {
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

        // A tap outside this plot's columns dismisses a readout opened by a tap.
        document.addEventListener("click", function (e) {
            var column = e.target.closest(".cost-column");
            if (!column || !plot.contains(column)) hide();
        });
    });
})();
