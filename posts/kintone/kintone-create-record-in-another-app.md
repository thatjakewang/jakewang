---
title: How to Create a Record in Another Kintone App When a Record Is Saved
date: 2026-11-13
category: kintone
tags: [REST API]
slug: kintone-create-record-in-another-app
---

You want saving a record to add a record to a different app, for example a new order that creates a shipping task in a Tasks app. Kintone's Action button can copy a record into another app, but someone has to click it for each record. To create the record automatically, you have to call the REST API with JavaScript after the save.

## Create the record after a new record is saved

```js
(() => {
  'use strict';

  const TASK_APP_ID = 15;
  const URL = kintone.api.url('/k/v1/record.json', true);

  kintone.events.on('app.record.create.submit.success', async (event) => {
    const order = event.record;

    try {
      await kintone.api(URL, 'POST', {
        app: TASK_APP_ID,
        record: {
          Title: { value: `Ship order ${event.recordId}` },
          Customer_name: { value: order.Customer_name.value },
          Due_date: { value: order.Due_date.value },
          Order_ID: { value: event.recordId },
        },
      });
    } catch (error) {
      alert(`The order was saved, but its task was not created: ${error.message}`);
    }
    return event;
  });
})();
```

To set it up:

1. In the Orders app, add a Text field with the field code `Customer_name` and a Date field with the field code `Due_date`.
2. In the Tasks app, add Text fields with the field codes `Title` and `Customer_name`, a Date field with the field code `Due_date`, and a Number field with the field code `Order_ID`.
3. Set `TASK_APP_ID` to the Tasks app's ID, which is the number after `/k/` in its URL.
4. [Upload the file](/kintone/kintone-upload-javascript-css/) to the Orders app.

`app.record.create.submit.success` runs once, after a new record has been saved. The edit events aren't used here, because they would add another task every time the order is edited.

`event.recordId` is the ID the order was just given. It doesn't exist before the save, which is why this runs on `submit.success` and not on `submit`. Storing it in the task's `Order_ID` is what ties the two records together.

`POST` on `/k/v1/record.json` is the Add Record API. `record` holds the new record's fields by field code. A field you leave out gets its default value, and a field code the Tasks app doesn't have is ignored.

The handler is `async` and returns `event` after the request finishes. Kintone waits for the returned promise before it leaves the screen, so the request isn't cut off.

`kintone.api()` calls the REST API as the person saving the order. They need permission to add records in the Tasks app. If they don't have it, or a required field in the Tasks app is missing from `record`, the request fails and the `catch` shows the reason. The order itself is already saved by then.

Calculated fields, fields a Lookup copies into, and the status and assignee can't be set when adding a record.

## Show the task on the order

No code is needed for this. In the Orders app, add a Related Records field that reads from the Tasks app, and set its condition to match the order's Record number with the task's `Order_ID`. The order then lists its task, with a link to it.

## Keep the task in step when the order is edited

If the due date changes on the order, the task still shows the old one. To update the task on every save, and create it only when it doesn't exist yet, use the Update Records API with `upsert`:

```js
(() => {
  'use strict';

  const TASK_APP_ID = 15;
  const URL = kintone.api.url('/k/v1/records.json', true);

  const EVENTS = [
    'app.record.create.submit.success',
    'app.record.edit.submit.success',
    'app.record.index.edit.submit.success',
  ];

  kintone.events.on(EVENTS, async (event) => {
    const order = event.record;

    try {
      await kintone.api(URL, 'PUT', {
        app: TASK_APP_ID,
        upsert: true,
        records: [{
          updateKey: { field: 'Order_ID', value: event.recordId },
          record: {
            Title: { value: `Ship order ${event.recordId}` },
            Customer_name: { value: order.Customer_name.value },
            Due_date: { value: order.Due_date.value },
          },
        }],
      });
    } catch (error) {
      alert(`The order was saved, but its task was not updated: ${error.message}`);
    }
    return event;
  });
})();
```

In the Tasks app, turn on **Prohibit duplicate values** for `Order_ID` first. `updateKey` only works with a field that has it.

With `upsert: true`, Kintone looks for a task whose `Order_ID` is this order's ID. If there is one, it's updated. If there isn't, a new task is added with that `Order_ID`. Either way, an order never ends up with two tasks, so the edit events are safe to use.

`Order_ID` isn't listed in `record` this time. The field used as the `updateKey` can't be changed in the same request.

Every save now overwrites the fields listed in `record`. If someone changes the due date on the task itself, the next save of the order puts the order's date back. List only the fields that should always follow the order.

For updating a record that already exists, without creating one, see [How to Update a Record in Another Kintone App When a Record Is Saved](/kintone/kintone-update-record-in-another-app/).

## The two saves are not one transaction

The order is saved first and the task is created second. If the second step fails, the first is not undone, which is why the handler tells the person what happened so that someone can add the task by hand.

Deleting an order doesn't delete its task. The task stays in the Tasks app with an `Order_ID` that no longer matches anything.

The handler only runs in the browser, on the screens the file is loaded for. Orders added through the REST API or a file import skip it, and the mobile view needs its own file with the `mobile.` event names.

To change many records at once instead of one per save, see [How to Bulk Update Kintone Records From the List View](/kintone/kintone-bulk-update-records-list-view/).

**References**

1. [Add Record – Kintone Developer Program](https://kintone.dev/en/docs/kintone/rest-api/records/add-record/)
2. [Update Records – Kintone Developer Program](https://kintone.dev/en/docs/kintone/rest-api/records/update-records/)
3. [Kintone REST API Request – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/api/kintone-rest-api-request/)
4. [Record Create Save Success event – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/create/create-submit-success-event/)
5. [Record Edit Save Success event – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/edit/edit-submit-success-event/)
6. [Record List Save Success event – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/idx/index-edit-submit-success-event/)
