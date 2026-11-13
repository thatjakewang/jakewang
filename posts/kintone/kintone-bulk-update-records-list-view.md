---
title: How to Bulk Update Kintone Records From the List View
date: 2026-11-13
category: kintone
tags: [REST API, List view]
slug: kintone-bulk-update-records-list-view
---

You want to change one field on every record in a view at once, for example marking all the invoices in the current view as `Paid`. Kintone's record list only edits one record at a time, so you have to add a button that updates them through the REST API with JavaScript.

## Add a button that updates every record in the view

```js
(() => {
  'use strict';

  const FIELD = 'Payment_status';
  const VALUE = 'Paid';
  const LABEL = 'Mark all as paid';
  const BUTTON_ID = 'bulk-update-button';
  const URL = kintone.api.url('/k/v1/records.json', true);
  const GET_LIMIT = 500;
  const PUT_LIMIT = 100;

  const fetchIds = async () => {
    const filter = kintone.app.getQueryCondition();
    let query = `${FIELD} not in ("${VALUE}")`;
    if (filter) {
      query = `(${filter}) and ${query}`;
    }

    const ids = [];
    let offset = 0;
    while (true) {
      const resp = await kintone.api(URL, 'GET', {
        app: kintone.app.getId(),
        query: `${query} order by $id asc limit ${GET_LIMIT} offset ${offset}`,
        fields: ['$id'],
      });
      ids.push(...resp.records.map((r) => r.$id.value));
      if (resp.records.length < GET_LIMIT) {
        return ids;
      }
      offset += GET_LIMIT;
    }
  };

  const updateAll = async (ids, onProgress) => {
    for (let i = 0; i < ids.length; i += PUT_LIMIT) {
      const batch = ids.slice(i, i + PUT_LIMIT);
      await kintone.api(URL, 'PUT', {
        app: kintone.app.getId(),
        records: batch.map((id) => ({
          id,
          record: { [FIELD]: { value: VALUE } },
        })),
      });
      onProgress(i + batch.length);
    }
  };

  const run = async (button) => {
    button.disabled = true;
    let done = 0;
    try {
      const ids = await fetchIds();
      if (ids.length === 0) {
        alert('Nothing to update.');
      } else if (confirm(`Update ${ids.length} records?`)) {
        await updateAll(ids, (count) => {
          done = count;
          button.textContent = `${count} / ${ids.length}`;
        });
      }
    } catch (error) {
      alert(`Stopped after ${done} records: ${error.message}`);
    }

    if (done > 0) {
      location.reload();
      return;
    }
    button.textContent = LABEL;
    button.disabled = false;
  };

  kintone.events.on('app.record.index.show', (event) => {
    const space = kintone.app.getHeaderMenuSpaceElement();
    if (!space || document.getElementById(BUTTON_ID)) {
      return event;
    }

    const button = document.createElement('button');
    button.id = BUTTON_ID;
    button.type = 'button';
    button.textContent = LABEL;
    button.addEventListener('click', () => run(button));
    space.appendChild(button);
    return event;
  });
})();
```

To set it up:

1. On the form, add a Drop-down field with the field code `Payment_status` and the options `Unpaid` and `Paid`.
2. [Upload the file](/kintone/kintone-upload-javascript-css/).

`kintone.app.getHeaderMenuSpaceElement()` returns the empty area in the record list's header, which is where the button goes. `app.record.index.show` runs again each time the list reloads, so the `getElementById` check stops a second button from being added.

`kintone.app.getQueryCondition()` returns the list's current filter, so the button updates the same records the list shows, on every page and not just the current one. `fetchIds()` adds `not in ("Paid")` to that filter to skip the records that already have the value. For more on combining conditions, see [How to Query Another Kintone App With Multiple Conditions](/kintone/kintone-query-another-app-multiple-conditions/).

The Get Records API returns at most 500 records per call, so `fetchIds()` keeps asking for the next 500 with `offset`, the same way as in [How to Fetch Data From Another Kintone App With JavaScript](/kintone/kintone-fetch-data-from-another-app/). `order by $id asc` keeps the pages in a fixed order, and `fields: ['$id']` keeps each response small, because only the record ID is used. `offset` can't go past 10,000, so a view with more matching records than that stops with an error before anything is updated.

All the IDs are fetched before anything is updated. If the view is filtered to unpaid invoices, each update takes records out of the filter, and paging through it while updating would skip some.

`PUT` on `/k/v1/records.json` is the Update Records API. It takes at most 100 records per call, so `updateAll()` sends the IDs in batches of 100. Each entry names a record by its `id` and lists only the fields to change.

The count in `confirm()` is the last chance to back out. There is no undo, so check the view's filter before clicking **OK**.

The button shows the progress while the batches run, and the list reloads when they finish. If a request fails, the message says how many records were already updated.

`kintone.api()` calls the REST API as the person who clicked the button. They need permission to edit the records and the `Payment_status` field.

## Set more than one field

Add the other fields to `record`:

```js
record: {
  Payment_status: { value: 'Paid' },
  Paid_date: { value: '2026-11-13' },
},
```

A Date field takes a string in the form `2026-11-13`. Calculated fields, fields a Lookup copies into, and the status and assignee can't be set this way.

## The batches are not one transaction

Each call is all or nothing: if one record in a batch can't be updated, for example because the person isn't allowed to edit it, none of that batch's 100 are. The batches are separate, though. If the third one fails, the first two stay updated. Because `fetchIds()` skips records that already have the value, clicking the button again picks up where it stopped.

When every record has to change together or not at all, the Bulk Request API runs up to 20 requests as one, which covers 2,000 records.

Every updated record gets a new **Updated by** and **Updated datetime**, so a bulk update also changes what a view sorted by those shows first.

To see how the records are spread across statuses before changing them, see [How to Add a Status Chart to a Kintone List With Chart.js](/kintone/kintone-record-list-status-chart/).

**References**

1. [Update Records – Kintone Developer Program](https://kintone.dev/en/docs/kintone/rest-api/records/update-records/)
2. [Get Records – Kintone Developer Program](https://kintone.dev/en/docs/kintone/rest-api/records/get-records/)
3. [Bulk Request – Kintone Developer Program](https://kintone.dev/en/docs/kintone/rest-api/records/bulk-request/)
4. [kintone.app.getHeaderMenuSpaceElement() – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/app/get-record-list-header-menu-element/)
5. [kintone.app.getQueryCondition() – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/app/get-record-list-query/)
6. [Kintone REST API Request – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/api/kintone-rest-api-request/)
