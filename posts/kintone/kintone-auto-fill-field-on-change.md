---
title: How to Auto-Fill a Kintone Field When Another Field Changes
date: 2026-11-13
category: kintone
tags: [Forms]
slug: kintone-auto-fill-field-on-change
---

You want a field to fill itself in when another field changes, for example a `Unit_price` that fills in when someone picks a `Plan`. A Calculated field can work a value out, but nobody can edit the result, and a Lookup field needs a click. To fill in a value that people can still change, you have to use a field change event with JavaScript.

## Fill the field when a choice changes

```js
(() => {
  'use strict';

  const SOURCE_FIELD = 'Plan';
  const TARGET_FIELD = 'Unit_price';

  const PRICES = {
    Basic: '1000',
    Standard: '2500',
    Premium: '5000',
  };

  const EVENTS = [
    `app.record.create.change.${SOURCE_FIELD}`,
    `app.record.edit.change.${SOURCE_FIELD}`,
    `app.record.index.edit.change.${SOURCE_FIELD}`,
  ];

  kintone.events.on(EVENTS, (event) => {
    const price = PRICES[event.changes.field.value];
    if (price !== undefined) {
      event.record[TARGET_FIELD].value = price;
    }
    return event;
  });
})();
```

To set it up:

1. On the form, add a Drop-down field with the field code `Plan` and the options `Basic`, `Standard` and `Premium`.
2. Add a Number field with the field code `Unit_price`.
3. [Upload the file](/kintone/kintone-upload-javascript-css/).

A change event's name ends with a field code, and it runs each time that field's value changes. The `create` and `edit` events cover the screens for adding and editing a record. `app.record.index.edit.change` is the same event for a record edited in place on the record list.

`event.changes.field` is the field that changed, and its `value` is the new value. Setting another field's `value` on `event.record` and returning the event puts that value on the form. Nothing is saved until the person clicks **Save**, so they can still type over the price.

A Number field's value is a string, so `PRICES` holds strings. A plan that isn't in `PRICES`, or a drop-down that has been cleared, leaves the price as it is.

Change events exist for Drop-down, Radio button, Check box, Multi-choice, Date, Time, Date and time, User selection, Department selection, Group selection, Text and Number fields. Text and Number fields run theirs when the cursor leaves the field, not on each keystroke. Text area, Rich text and Attachment fields have no change event.

The field you fill can't be a Calculated field, a Lookup field, a field a Lookup copies into or an Attachment field. Kintone ignores values set on those.

## Keep a value someone has typed

As written, picking another plan replaces a price that someone typed in. To fill the price only when it's empty, check it first:

```js
const target = event.record[TARGET_FIELD];
if (price !== undefined && !target.value) {
  target.value = price;
}
```

## Fill the field when the form opens

Change events don't run when the form opens. If `Plan` has a default value, a new record starts with that plan and no price. To fill the price then as well, add `app.record.create.show` to `EVENTS` and read the plan from the record, because that event has no `event.changes`:

```js
const price = PRICES[event.record[SOURCE_FIELD].value];
```

`event.record` already holds the new value during a change event, so the same line works for both.

`app.record.create.show` also runs when someone duplicates a record. Use it together with the empty check above, or the price copied from the original is replaced.

## Fill the field from another app

The value can come from another app, for example a customer's payment terms from a Customers app. The change events don't wait for a Promise the way the `submit` events do, so the handler can't `await` the request. Start the request, return the event, and set the field when the answer arrives:

```js
(() => {
  'use strict';

  const CUSTOMER_APP_ID = 12;
  const URL = kintone.api.url('/k/v1/records.json', true);

  const EVENTS = [
    'app.record.create.change.Customer_ID',
    'app.record.edit.change.Customer_ID',
  ];

  const quote = (value) => `"${value.replace(/["\\]/g, '\\$&')}"`;

  kintone.events.on(EVENTS, (event) => {
    const customerId = event.changes.field.value;
    if (!customerId) {
      return event;
    }

    kintone.api(URL, 'GET', {
      app: CUSTOMER_APP_ID,
      query: `Customer_ID = ${quote(customerId)} limit 1`,
      fields: ['Payment_terms'],
    }).then((resp) => {
      const current = kintone.app.record.get();
      if (!current || current.record.Customer_ID.value !== customerId) {
        return;
      }
      if (resp.records.length > 0) {
        current.record.Payment_terms.value = resp.records[0].Payment_terms.value;
        kintone.app.record.set(current);
      }
    }).catch(() => {
      // Leave the field as it is when the request fails.
    });

    return event;
  });
})();
```

Both apps need Text fields with the field codes `Customer_ID` and `Payment_terms`. Replace `12` with the Customers app's ID.

`kintone.app.record.get()` returns the record as it is on the form right now, and `kintone.app.record.set()` writes it back. Neither can be called inside an event handler, but by the time the request answers, the handler has already returned.

The answer can arrive after the person has typed a different customer ID. The handler compares the ID on the form with the one it asked about and drops the answer if they differ, so an old answer never overwrites a newer one.

`get()` and `set()` only work on the create and edit screens, which is why the record list event isn't in `EVENTS` here.

If a click is acceptable, a Lookup field copies values from another app without any code. For more on the request, see [How to Fetch Data From Another Kintone App With JavaScript](/kintone/kintone-fetch-data-from-another-app/).

## Auto-fill only runs on the form

These handlers run in the browser, on the screens the file is loaded for. Records added through the REST API or a file import skip them, so a record can still arrive with a plan and no price. The mobile view needs its own file with the `mobile.` event names.

A value set from a handler counts as a change to that field, so a change event on `Unit_price` runs too. That lets one auto-fill lead to another, but avoid two fields that fill each other.

To check the values when the record is saved, see [How to Add Custom Validation to a Kintone Record Using JavaScript](/kintone/kintone-custom-validation-javascript/).

**References**

1. [Record Create Field Change event – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/create/create-change-event/)
2. [Record Edit Field Change event – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/edit/edit-change-event/)
3. [Record List Field Change event – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/idx/index-edit-change-event/)
4. [Event Object Actions – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/event-object-actions/)
5. [Get Record Details – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/record/get-record/)
6. [Set Record Value – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/record/set-record-value/)
