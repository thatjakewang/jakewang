---
title: How to Lock Kintone Fields by Workflow Status
date: 2026-11-15
category: kintone
tags: [Process Management, Forms]
slug: kintone-lock-fields-by-status
---

You want some fields to stop being editable once a record has moved on, for example the `Amount` once a request is `In progress`. Kintone's permissions can lock a whole record by its status, but Field Permissions can't depend on the status, so to lock single fields you have to disable them with JavaScript when the edit screen opens.

## Disable the fields for each status

```js
(() => {
  'use strict';

  const LOCKED = {
    'In progress': ['Customer', 'Amount'],
    'Completed': ['Customer', 'Amount', 'Due_date'],
  };

  const EVENTS = [
    'app.record.edit.show',
    'app.record.index.edit.show',
  ];

  kintone.events.on(EVENTS, (event) => {
    const locked = LOCKED[event.record.Status.value] || [];
    for (const field of locked) {
      event.record[field].disabled = true;
    }
    return event;
  });
})();
```

To set it up:

1. Turn on Process Management with the statuses `Not started`, `In progress` and `Completed`.
2. On the form, add a Text field with the field code `Customer`, a Number field with the field code `Amount` and a Date field with the field code `Due_date`.
3. [Upload the file](/kintone/kintone-upload-javascript-css/).

`LOCKED` maps each status to the fields that can't be edited at that status. A status that isn't in `LOCKED` locks nothing, so `Not started` leaves every field open.

Setting `disabled` to `true` on a field and returning the event greys the field out. Its value still shows, and it is saved unchanged with the rest of the record.

`app.record.edit.show` runs when the edit screen opens. `app.record.index.edit.show` is the same event for a record edited in place on the record list. Without it, someone could change a locked field from the list.

`event.record.Status.value` is the record's current status. `Status` is the field code of the status field, which isn't the same in every app, so check it in the form settings.

The create screen isn't in `EVENTS`, because a new record has no status yet. The status can't change while the edit screen is open either, so the fields only need to be set once, when it opens.

## Lock the fields in a table

A Table field has no `disabled` of its own. Set it on the fields in each row:

```js
for (const row of event.record.Items.value) {
  row.value.Quantity.disabled = true;
  row.value.Unit_price.disabled = true;
}
```

This stops the values in the existing rows from being changed. The buttons that add and delete rows still work, so it doesn't freeze the table as a whole. For more on a table's rows, see [How to Add Rows to a Kintone Subtable With JavaScript](/kintone/kintone-add-rows-to-subtable-javascript/).

## Lock a field when another field changes

`disabled` can be set in a change event too. To lock `Amount` as soon as a `Confirmed` Check box field is ticked, and open it again when the tick is removed:

```js
const EVENTS = [
  'app.record.create.show',
  'app.record.edit.show',
  'app.record.create.change.Confirmed',
  'app.record.edit.change.Confirmed',
];

kintone.events.on(EVENTS, (event) => {
  const confirmed = event.record.Confirmed.value.length > 0;
  event.record.Amount.disabled = confirmed;
  return event;
});
```

A Check box field's value is an array of the ticked options, so it is ticked when the array isn't empty. For more on change events, see [How to Auto-Fill a Kintone Field When Another Field Changes](/kintone/kintone-auto-fill-field-on-change/).

## A locked field is not protected

Disabling a field only changes the form. The value can still be changed through the REST API, a file import or the mobile view, which needs its own file with the `mobile.` event names. Treat the lock as a guard against mistakes.

When a record mustn't change at all after a status, set that up in the app's record permissions instead, which apply everywhere.

A script can still set a locked field. The values filled in by [How to Auto-Fill Kintone Fields When the Status Changes](/kintone/kintone-fill-fields-on-status-change/) are saved whether the field is locked on the form or not.

To hide fields by status instead of locking them, see [How to Show Kintone Field Groups by Workflow Status](/kintone/kintone-workflow-field-groups/).

**References**

1. [Event Object Actions – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/event-object-actions/)
2. [Record Edit Show event – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/edit/edit-show-event/)
3. [Record List Inline Edit Show event – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/idx/index-edit-show-event/)
4. [Record Edit Field Change event – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/edit/edit-change-event/)
