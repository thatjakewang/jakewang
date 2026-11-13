---
title: How to Update a Record in Another Kintone App When a Record Is Saved
date: 2026-11-13
category: kintone
tags: [REST API]
slug: kintone-update-record-in-another-app
---

You want saving a record to change a record in a different app, for example an order that sets the last order date on its customer's record. Lookup and Related Records fields only bring data into the record you're on, so to write to the other app you have to call the REST API with JavaScript after the save.

## Update the record after a save

```js
(() => {
  'use strict';

  const CUSTOMER_APP_ID = 12;
  const URL = kintone.api.url('/k/v1/record.json', true);

  const EVENTS = [
    'app.record.create.submit.success',
    'app.record.edit.submit.success',
    'app.record.index.edit.submit.success',
  ];

  kintone.events.on(EVENTS, async (event) => {
    const customerId = event.record.Customer_ID.value;
    const orderDate = event.record.Order_date.value;
    if (!customerId || !orderDate) {
      return event;
    }

    try {
      await kintone.api(URL, 'PUT', {
        app: CUSTOMER_APP_ID,
        updateKey: { field: 'Customer_ID', value: customerId },
        record: {
          Last_order_date: { value: orderDate },
        },
      });
    } catch (error) {
      alert(`The order was saved, but the customer was not updated: ${error.message}`);
    }
    return event;
  });
})();
```

To set it up:

1. In the Customers app, add a Text field with the field code `Customer_ID` and turn on **Prohibit duplicate values** in its settings. Add a Date field with the field code `Last_order_date`.
2. In the Orders app, add a Text field with the field code `Customer_ID` and a Date field with the field code `Order_date`.
3. Set `CUSTOMER_APP_ID` to the Customers app's ID, which is the number after `/k/` in its URL.
4. [Upload the file](/kintone/kintone-upload-javascript-css/) to the Orders app.

The `submit.success` events run after the record has been saved. The plain `submit` events run before, when the save can still fail, and the customer would then be updated for an order that doesn't exist. `app.record.index.edit.submit.success` is the same event for a record edited in place on the record list.

The handler is `async` and returns `event` after the request finishes. Kintone waits for the returned promise before it leaves the screen, so the request isn't cut off.

`PUT` on `/k/v1/record.json` is the Update Record API. `updateKey` picks the record to update by the value of a field instead of its record ID. That field must have **Prohibit duplicate values** turned on, so that the value can only ever match one record.

`record` lists only the fields to change. Every other field on the customer record stays as it is.

`kintone.api()` calls the REST API as the person saving the order. They need permission to edit records in the Customers app, and to edit the `Last_order_date` field.

If no customer has that ID, or the person isn't allowed to edit it, the request fails and the `catch` shows the reason. The order itself is already saved by then.

Some fields can't be updated this way: Calculated fields, fields a Lookup copies into, the status and assignee, and the created and updated fields. The field used as the `updateKey` can't be changed in the same request either.

## Update by record ID

If the order holds the customer's record ID, for example in a Number field that a Lookup fills in, use `id` instead of `updateKey`:

```js
await kintone.api(URL, 'PUT', {
  app: CUSTOMER_APP_ID,
  id: event.record.Customer_record_ID.value,
  record: {
    Last_order_date: { value: orderDate },
  },
});
```

Use one or the other. The API returns an error when both `id` and `updateKey` are set.

## Don't overwrite a newer value

As written, editing an old order sets the customer's last order date back to that order's date. To update only when the order is newer, read the customer first. Replace the `PUT` call inside the `try` with:

```js
const quote = (value) => `"${value.replace(/["\\]/g, '\\$&')}"`;

const found = await kintone.api(kintone.api.url('/k/v1/records.json', true), 'GET', {
  app: CUSTOMER_APP_ID,
  query: `Customer_ID = ${quote(customerId)} limit 1`,
  fields: ['$id', '$revision', 'Last_order_date'],
});
const customer = found.records[0];
const lastDate = customer && customer.Last_order_date.value;

if (customer && (!lastDate || lastDate < orderDate)) {
  await kintone.api(URL, 'PUT', {
    app: CUSTOMER_APP_ID,
    id: customer.$id.value,
    revision: customer.$revision.value,
    record: {
      Last_order_date: { value: orderDate },
    },
  });
}
```

A Date field's value is a string such as `2026-11-13`, so `<` compares two dates correctly. An empty date has no value, and the `!lastDate` check lets the first order fill it in.

`revision` is the version of the customer record that was read. If someone else changes that record between the read and the update, the revisions no longer match, the update fails, and the `catch` shows the message. Without `revision`, the update would go through and could undo their change.

This version does nothing when no customer has that ID, where the first one showed an error. For more on the query, see [How to Fetch Data From Another Kintone App With JavaScript](/kintone/kintone-fetch-data-from-another-app/).

## The two saves are not one transaction

The order is saved first and the customer is updated second. If the second step fails, the first is not undone, which is why the handler tells the person what happened so that someone can fix the customer by hand.

The handler only runs in the browser, on the screens the file is loaded for. Orders added through the REST API or a file import skip it, and the mobile view needs its own file with the `mobile.` event names. For an update that must never be missed, run it on a server instead, for example from a webhook.

To stop a bad record from being saved in the first place, see [How to Add Custom Validation to a Kintone Record Using JavaScript](/kintone/kintone-custom-validation-javascript/).

**References**

1. [Update Record – Kintone Developer Program](https://kintone.dev/en/docs/kintone/rest-api/records/update-record/)
2. [Get Records – Kintone Developer Program](https://kintone.dev/en/docs/kintone/rest-api/records/get-records/)
3. [Kintone REST API Request – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/api/kintone-rest-api-request/)
4. [Record Create Save Success event – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/create/create-submit-success-event/)
5. [Record Edit Save Success event – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/edit/edit-submit-success-event/)
6. [Record List Save Success event – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/idx/index-edit-submit-success-event/)
7. [Event Handling – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/event-handling/)
