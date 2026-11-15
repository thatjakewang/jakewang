---
title: How to Bulk Update the Status of Kintone Records
date: 2026-11-15
category: kintone
tags: [REST API, Process Management, List view]
slug: kintone-bulk-update-record-status
---

You want to move every record in a view to the next status at once, for example completing all the requests that are `In progress`. Kintone's action buttons only work on one record at a time, on its details screen, so you have to add a button that changes the statuses through the REST API with JavaScript.

## Add a button that runs an action on every record in the view

```js
(() => {
  'use strict';

  const FROM_STATUS = 'In progress';
  const ACTION = 'Complete';
  const LABEL = 'Complete all';
  const BUTTON_ID = 'bulk-status-button';
  const RECORDS_URL = kintone.api.url('/k/v1/records.json', true);
  const STATUS_URL = kintone.api.url('/k/v1/records/status.json', true);
  const GET_LIMIT = 500;
  const PUT_LIMIT = 100;

  const fetchIds = async () => {
    const filter = kintone.app.getQueryCondition();
    let query = `Status in ("${FROM_STATUS}")`;
    if (filter) {
      query = `(${filter}) and ${query}`;
    }

    const ids = [];
    let offset = 0;
    while (true) {
      const resp = await kintone.api(RECORDS_URL, 'GET', {
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
      await kintone.api(STATUS_URL, 'PUT', {
        app: kintone.app.getId(),
        records: batch.map((id) => ({ id, action: ACTION })),
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
        alert(`No records are ${FROM_STATUS}.`);
      } else if (confirm(`Run "${ACTION}" on ${ids.length} records?`)) {
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

1. Turn on Process Management with the statuses `Not started`, `In progress` and `Completed`, and an action named `Complete` that moves a record from `In progress` to `Completed`.
2. [Upload the file](/kintone/kintone-upload-javascript-css/).

`PUT` on `/k/v1/records/status.json` is the Update Statuses API. Each entry names a record by its `id` and the `action` to run on it. The action is the name on the button, not the status it leads to. If the action names are translated, use the name in the language of the person who clicks.

An action only exists at one status, so `fetchIds()` adds `Status in ("In progress")` to the list's current filter. Without it, a record at another status would make the request fail. `Status` is the field code of the status field, which isn't the same in every app, so check it in the form settings.

The API takes at most 100 records per call, so `updateAll()` sends the IDs in batches of 100. The button, the paging and the progress count work the same way as in [How to Bulk Update Kintone Records From the List View](/kintone/kintone-bulk-update-records-list-view/), which explains them in full.

All the IDs are fetched before any status changes. Each change takes a record out of the `In progress` filter, and paging through it while updating would skip some.

The count in `confirm()` is the last chance to back out. There is no undo, so check the view's filter before clicking **OK**.

## Only records assigned to you

`kintone.api()` calls the REST API as the person who clicked the button. Kintone only lets them run the action on a record they can view, and only if they are one of its assignees or the record has no assignee. A record assigned to someone else makes the request fail.

To skip those, add the person's login name to the query in `fetchIds()`:

```js
const me = kintone.getLoginUser().code;
let query = `Status in ("${FROM_STATUS}") and Assignee in ("${me}")`;
```

`Assignee` is the field code of the assignee field. Like `Status`, check it in the form settings.

## Choose the next assignee

If the next status is set up so that the person picks who it goes to, give each entry an `assignee` with that person's login name:

```js
records: batch.map((id) => ({ id, action: ACTION, assignee: 'manager01' })),
```

## What a bulk status change skips

A status changed through the REST API doesn't run the `app.record.detail.process.proceed` event. Any script that depends on it is skipped, such as the one in [How to Auto-Fill Kintone Fields When the Status Changes](/kintone/kintone-fill-fields-on-status-change/) or a check that blocks the action. If those fields matter, set them with the Update Records API in the same button.

Each call is all or nothing: if one record in a batch can't be moved, none of that batch's 100 are. The batches are separate, though. If the third one fails, the first two stay changed. Because `fetchIds()` only picks records still at `In progress`, clicking the button again picks up where it stopped.

To see how many records are at each status, see [How to Add a Status Chart to a Kintone List With Chart.js](/kintone/kintone-record-list-status-chart/).

**References**

1. [Update Statuses – Kintone Developer Program](https://kintone.dev/en/docs/kintone/rest-api/records/update-statuses/)
2. [Get Records – Kintone Developer Program](https://kintone.dev/en/docs/kintone/rest-api/records/get-records/)
3. [Query string – Kintone Developer Program](https://kintone.dev/en/docs/kintone/overview/query-string/)
4. [kintone.app.getHeaderMenuSpaceElement() – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/app/get-record-list-header-menu-element/)
5. [kintone.app.getQueryCondition() – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/app/get-record-list-query/)
6. [Get Logged-in User – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/kintone/get-login-user/)
