---
title: How to Auto-Fill Kintone Fields When the Status Changes
date: 2026-11-15
category: kintone
tags: [Process Management, Forms]
slug: kintone-fill-fields-on-status-change
---

You want a record to note who completed it and when, for example a `Completed_by` and a `Completed_date` that fill in when someone moves the record to `Completed`. Process Management changes the status and the assignee, but it can't set any other field, so you have to fill them in with JavaScript when the status changes.

## Fill the fields when a record is completed

```js
(() => {
  'use strict';

  const STATUS = 'Completed';
  const USER_FIELD = 'Completed_by';
  const DATE_FIELD = 'Completed_date';

  const toDateString = (date) => {
    const pad = (n) => String(n).padStart(2, '0');
    const y = date.getFullYear();
    const m = pad(date.getMonth() + 1);
    const d = pad(date.getDate());
    return `${y}-${m}-${d}`;
  };

  kintone.events.on('app.record.detail.process.proceed', (event) => {
    if (event.nextStatus.value === STATUS) {
      event.record[USER_FIELD].value = kintone.getLoginUser().name;
      event.record[DATE_FIELD].value = toDateString(new Date());
    }
    return event;
  });
})();
```

To set it up:

1. Turn on Process Management with the statuses `Not started`, `In progress` and `Completed`.
2. On the form, add a Text field with the field code `Completed_by` and a Date field with the field code `Completed_date`.
3. [Upload the file](/kintone/kintone-upload-javascript-css/).

`app.record.detail.process.proceed` runs when someone clicks an action button on the record details screen, before the status changes. `event.status` is the status the record has now, `event.nextStatus` is the one it is moving to, and `event.action` is the button that was clicked. Each has the name in its `value`.

Setting a field's `value` on `event.record` and returning the event saves that value together with the status change. If the handler returns nothing, only the status changes.

`kintone.getLoginUser()` returns the person who is signed in, which is the person who clicked the button. `name` is their display name and `code` is their login name.

The date is formatted by hand because `toISOString()` uses UTC and can be a day off.

## Store the person in a User selection field

A Text field holds the name as it was that day. To keep a link to the person's account, use a User selection field and set an array with their login name:

```js
event.record[USER_FIELD].value = [{ code: kintone.getLoginUser().code }];
```

## Use the action instead of the status

Two buttons can lead to the same status, for example `Approve` and `Skip review` both moving a record to `Completed`. To tell them apart, check the action's name:

```js
if (event.action.value === 'Approve') {
  event.record.Approved_date.value = toDateString(new Date());
}
```

The name is the one on the button, in the language the person uses Kintone in if the action names are translated.

## Clear the fields when a record is sent back

If an action can move a record back from `Completed`, the fields should be emptied again:

```js
if (event.status.value === STATUS && event.nextStatus.value !== STATUS) {
  event.record[USER_FIELD].value = '';
  event.record[DATE_FIELD].value = null;
}
```

## Look something up first

The handler can return a Promise, and Kintone waits for it before changing the status. That lets it read another app first, for example copying an approval limit from a Settings app. Make the handler `async` and `await` the request, as in [How to Fetch Data From Another Kintone App With JavaScript](/kintone/kintone-fetch-data-from-another-app/). If the request fails, the status doesn't change.

## When the fields aren't filled

The event only runs for an action button clicked on the record details screen. A status changed through the REST API skips the handler, and so does [a bulk status update from the record list](/kintone/kintone-bulk-update-record-status/). The mobile view needs its own file with the event name `mobile.app.record.detail.process.proceed`.

The fields are saved as the person who clicked the button, so that person needs permission to edit the record and those fields.

When a status needs every assignee to act before the record moves on, the event runs each time one of them clicks, so the fields end up holding the last person and date.

Kintone ignores a value set on a Calculated field or a Lookup field.

To stop the status change when a field is missing, see [How to Add Custom Validation to a Kintone Record Using JavaScript](/kintone/kintone-custom-validation-javascript/). To lock the fields once the record is completed, see [How to Lock Kintone Fields by Workflow Status](/kintone/kintone-lock-fields-by-status/).

**References**

1. [Update Status Event – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/detail/detail-process-proceed-event/)
2. [Event Object Actions – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/event-object-actions/)
3. [Get Logged-in User – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/kintone/get-login-user/)
