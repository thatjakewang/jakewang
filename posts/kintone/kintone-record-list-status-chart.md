---
title: How to Add a Status Chart to a Kintone List With Chart.js
date: 2026-11-05
category: kintone
tags: [List view, Process Management, Chart.js]
slug: kintone-record-list-status-chart
---

You want to see at a glance how many records are at each status, for example a bar chart of `Not started`, `In progress` and `Completed` above the record list. Kintone's graphs live on their own page, so you have to draw one above the list with JavaScript and Chart.js.

## Draw the chart above the list

```js
(() => {
  'use strict';

  const STATUSES = ['Not started', 'In progress', 'Completed'];
  const COLORS = ['#98a2b3', '#2e90fa', '#12b76a'];
  const URL = kintone.api.url('/k/v1/records.json', true);

  let chart;

  const countStatus = async (status) => {
    const filter = kintone.app.getQueryCondition();
    let query = `Status in ("${status}")`;
    if (filter) {
      query = `(${filter}) and ${query}`;
    }
    const resp = await kintone.api(URL, 'GET', {
      app: kintone.app.getId(),
      query: `${query} limit 1`,
      fields: ['$id'],
      totalCount: true,
    });
    return Number(resp.totalCount);
  };

  kintone.events.on('app.record.index.show', async (event) => {
    const space = kintone.app.getHeaderSpaceElement();
    if (!space) {
      return event;
    }

    let canvas = space.querySelector('canvas');
    if (!canvas) {
      const box = document.createElement('div');
      box.style.maxWidth = '480px';
      box.style.height = '240px';
      canvas = document.createElement('canvas');
      box.appendChild(canvas);
      space.appendChild(box);
    }

    const counts = await Promise.all(STATUSES.map(countStatus));
    if (chart) {
      chart.destroy();
    }
    chart = new Chart(canvas, {
      type: 'bar',
      data: {
        labels: STATUSES,
        datasets: [{ data: counts, backgroundColor: COLORS }],
      },
      options: {
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
      },
    });
    return event;
  });
})();
```

To set it up:

1. Turn on Process Management with the statuses `Not started`, `In progress` and `Completed`.
2. On the [JavaScript and CSS Customization](/kintone/kintone-upload-javascript-css/) page, click **Add Link** and enter `https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js`.
3. Upload this file below the link, then click **Save** and **Update App**.

Chart.js has to come first so `Chart` exists when this file runs.

`kintone.app.getHeaderSpaceElement()` returns the empty area above the record list. The `querySelector('canvas')` check reuses the same canvas when the list reloads, and `chart.destroy()` clears the old chart before drawing the new one.

`event.records` only holds the records on the current page, so counting them would miss everything on the other pages. Instead `countStatus()` asks the REST API how many records match each status. `totalCount: true` returns the number of matching records, and `limit 1` with `fields: ['$id']` keeps each response small, because only the count is used.

`kintone.app.getQueryCondition()` returns the list's current filter, so the chart counts the same records the list shows. It returns an empty string when there's no filter, which is why `query` only adds it when there is one.

`Status` is the field code of the status field, which isn't the same in every app, so check it in the form settings.

To change what a record shows at each status, see [How to Show Kintone Field Groups by Workflow Status](/kintone/kintone-workflow-field-groups/).

## Other chart types

Swap these into `type`:

| Chart | Type |
| --- | --- |
| Vertical bars | `'bar'` |
| Pie | `'pie'` |
| Doughnut | `'doughnut'` |
| Polar area | `'polarArea'` |

For a pie or doughnut, remove `plugins: { legend: { display: false } }`. Those charts have no axis labels, so the legend is what tells the colors apart.

**References**

1. [kintone.app.getHeaderSpaceElement() – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/app/get-record-list-header-element/)
2. [kintone.app.getQueryCondition() – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/app/get-record-list-query/)
3. [Get Records – Kintone Developer Program](https://kintone.dev/en/docs/kintone/rest-api/records/get-records/)
4. [Chart.js documentation](https://www.chartjs.org/docs/latest/)
