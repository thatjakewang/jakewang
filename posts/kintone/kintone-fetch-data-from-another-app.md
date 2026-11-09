---
title: How to Fetch Data From Another Kintone App Using JavaScript and the REST API
date: 2026-11-09
category: kintone
tags: [JavaScript]
slug: kintone-fetch-data-from-another-app
---

You want a record to show data that lives in a different app, for example a Customers record showing the total of that customer's invoices from an Invoices app. Lookup fields copy one record and Related Records fields only list them, so to add them up you have to fetch the records with JavaScript and the REST API.

## Fetch the records and show the total

```js
(() => {
  'use strict';

  const INVOICE_APP_ID = 12;
  const SPACE_ID = 'invoice_total_space';
  const URL = kintone.api.url('/k/v1/records.json', true);
  const LIMIT = 500;

  const fetchAll = async (query) => {
    const records = [];
    let offset = 0;
    while (true) {
      const resp = await kintone.api(URL, 'GET', {
        app: INVOICE_APP_ID,
        query: `${query} limit ${LIMIT} offset ${offset}`,
        fields: ['Amount'],
      });
      records.push(...resp.records);
      if (resp.records.length < LIMIT) {
        return records;
      }
      offset += LIMIT;
    }
  };

  kintone.events.on('app.record.detail.show', async (event) => {
    const space = kintone.app.record.getSpaceElement(SPACE_ID);
    if (!space) {
      return event;
    }

    const customerId = event.record.Customer_ID.value.replace(/["\\]/g, '\\$&');
    const invoices = await fetchAll(`Customer_ID = "${customerId}"`);
    const total = invoices.reduce((sum, r) => sum + Number(r.Amount.value), 0);

    space.textContent = `Invoices: ${invoices.length}, total ${total.toLocaleString()}`;
    return event;
  });
})();
```

In the Invoices app, add a Text field with the field code `Customer_ID` and a Number field with the field code `Amount`. In the Customers app, add a Text field with the field code `Customer_ID` and a Blank space field with the Element ID `invoice_total_space`. Set `INVOICE_APP_ID` to the Invoices app's ID, which is the number after `/k/` in its URL. Upload the file to the Customers app under **App Settings** > **Customization and Integration** > **JavaScript and CSS Customization** > **JavaScript Files for PC**, then click **Update App**.

`kintone.api()` calls the REST API as the person viewing the record, so they need permission to view the Invoices app. Records they can't see are left out of the total.

The Get Records API returns at most 500 records per call, so `fetchAll()` keeps asking for the next 500 with `offset` until a call comes back with fewer. `fields: ['Amount']` keeps each response small, because only the amount is used. `offset` can't go past 10,000, so for more records than that, use a cursor instead.

The handler is `async` and returns `event` after the data arrives. Kintone waits for the returned promise before it finishes showing the record.

The `replace()` puts a backslash before any `"` or `\` in the customer ID. Without it, an ID containing a `"` would end the string early and break the query.

`textContent` sets the text as plain text, so the result can't be read as HTML.

## Get one record by its ID

If you already know the record ID, the Get Record API returns that record directly:

```js
const resp = await kintone.api(kintone.api.url('/k/v1/record.json', true), 'GET', {
  app: INVOICE_APP_ID,
  id: 25,
});
console.log(resp.record.Amount.value);
```

It throws an error if no record has that ID or the person can't view it, so wrap it in `try`/`catch` when the ID comes from another field.

**References**

1. [kintone.api() – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/other/kintone-rest-api-request/)
2. [Get Records – Kintone Developer Program](https://kintone.dev/en/docs/kintone/rest-api/records/get-records/)
3. [Get Record – Kintone Developer Program](https://kintone.dev/en/docs/kintone/rest-api/records/get-record/)
4. [kintone.app.record.getSpaceElement() – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/record/get-space-element/)
