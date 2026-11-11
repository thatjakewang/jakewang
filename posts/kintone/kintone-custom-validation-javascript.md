---
title: How to Add Custom Validation to a Kintone Record Using JavaScript
date: 2026-11-11
category: kintone
tags: [Forms, Validation]
slug: kintone-custom-validation-javascript
---

You want to stop a record from being saved when its values don't make sense together, for example an `End date` that is earlier than the `Start date`. Kintone's field settings can require a field or limit its range, but they can't compare one field with another, so you have to check the values with JavaScript when the record is saved.

## Show an error on the field

```js
(() => {
  'use strict';

  const START_FIELD = 'Start_date';
  const END_FIELD = 'End_date';

  const EVENTS = [
    'app.record.create.submit',
    'app.record.edit.submit',
    'app.record.index.edit.submit',
  ];

  kintone.events.on(EVENTS, (event) => {
    const record = event.record;
    const start = record[START_FIELD].value;
    const end = record[END_FIELD].value;

    if (start && end && end < start) {
      record[END_FIELD].error = 'The end date must be on or after the start date.';
    }
    return event;
  });
})();
```

To set it up:

1. On the form, add two Date fields with the field codes `Start_date` and `End_date`.
2. [Upload the file](/kintone/kintone-upload-javascript-css/).

The `submit` events run when someone clicks **Save**, before the record is saved. Setting `error` on a field and returning the event cancels the save and shows the message in red under that field.

`app.record.index.edit.submit` is the same event for a record edited in place on the record list. Without it, someone could save the wrong dates from the list.

A Date field's value is a string such as `2026-11-11`, so `<` compares two dates correctly without turning them into `Date` objects. An empty Date field has no value, and the `start && end` check skips the comparison then. To make a field mandatory, turn on **Required field** in its settings instead.

## Show an error at the top of the record

When a rule isn't about one field, set `event.error` instead:

```js
if (!record.Phone.value && !record.Email.value) {
  event.error = 'Enter a phone number or an email address.';
}
```

The message appears at the top of the record, and the save is cancelled the same way. You can set `event.error` and field errors in the same handler.

## Check a rule against another app

A `submit` handler can return a Promise, and Kintone waits for it before saving. That lets a rule look at other records first, for example rejecting an invoice number that isn't in an Invoices app:

```js
kintone.events.on(EVENTS, async (event) => {
  const record = event.record;
  const number = record.Invoice_number.value;
  if (!number) {
    return event;
  }

  const resp = await kintone.api(kintone.api.url('/k/v1/records.json', true), 'GET', {
    app: 12,
    query: `Invoice_number = "${number.replace(/["\\]/g, '\\$&')}" limit 1`,
    fields: ['$id'],
  });

  if (resp.records.length === 0) {
    record.Invoice_number.error = 'No invoice has this number.';
  }
  return event;
});
```

Replace `12` with the other app's ID. If the request fails, the Promise is rejected and the save is cancelled. For more on the request, see [How to Fetch Data From Another Kintone App With JavaScript](/kintone/kintone-fetch-data-from-another-app/).

## Block a status change

Moving a record to the next status doesn't run the `submit` events. To check a rule at that point, use `app.record.detail.process.proceed`:

```js
kintone.events.on('app.record.detail.process.proceed', (event) => {
  if (event.nextStatus.value === 'Completed' && !event.record.End_date.value) {
    event.error = 'Set the end date before completing the record.';
  }
  return event;
});
```

This event only takes `event.error`. An error set on a field isn't shown.

## Validation is not enforcement

These checks only run in the browser, on the screens the file is loaded for. Records added through the REST API, a file import or the mobile view skip them, so treat them as a guard against mistakes and not as a rule the data always obeys. The mobile view needs its own file with the `mobile.` event names.

**References**

1. [Record Create Submit event – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/create/create-submit-event/)
2. [Record Edit Submit event – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/edit/edit-submit-event/)
3. [Record List Inline Edit Submit event – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/idx/index-edit-submit-event/)
4. [Record Details Process Proceed event – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/detail/detail-process-proceed-event/)
5. [Event Object Actions – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/event-object-actions/)
