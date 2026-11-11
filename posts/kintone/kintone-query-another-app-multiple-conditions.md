---
title: How to Query Another Kintone App With Multiple Conditions
date: 2026-11-09
updated: 2026-11-10
category: kintone
tags: [REST API, Queries]
slug: kintone-query-another-app-multiple-conditions
---

You want records from another app that match more than one condition, for example a Customers record listing that customer's invoices that are unpaid and past their due date. The Get Records API takes a single query string, so you have to join the conditions with `and` or `or` in JavaScript.

This builds on [How to Fetch Data From Another Kintone App With JavaScript](/kintone/kintone-fetch-data-from-another-app/), which uses the same two apps.

## Join the conditions with `and`

```js
(() => {
  'use strict';

  const INVOICE_APP_ID = 12;
  const SPACE_ID = 'overdue_space';
  const URL = kintone.api.url('/k/v1/records.json', true);
  const LIMIT = 500;

  const quote = (value) => `"${value.replace(/["\\]/g, '\\$&')}"`;

  kintone.events.on('app.record.detail.show', async (event) => {
    const space = kintone.app.record.getSpaceElement(SPACE_ID);
    const customerId = event.record.Customer_ID.value;
    if (!space || !customerId) {
      return event;
    }

    const conditions = [
      `Customer_ID = ${quote(customerId)}`,
      `Payment_status in ("Unpaid")`,
      `Due_date < TODAY()`,
    ];

    try {
      const resp = await kintone.api(URL, 'GET', {
        app: INVOICE_APP_ID,
        query: `${conditions.join(' and ')} order by Due_date asc limit ${LIMIT}`,
        fields: ['Invoice_no', 'Due_date', 'Amount'],
      });

      if (resp.records.length === 0) {
        space.textContent = 'No overdue invoices.';
        return event;
      }

      const list = document.createElement('ul');
      for (const r of resp.records) {
        const item = document.createElement('li');
        item.textContent = `${r.Invoice_no.value} (due ${r.Due_date.value}): ${Number(r.Amount.value).toLocaleString()}`;
        list.appendChild(item);
      }
      space.replaceChildren(list);

      if (resp.records.length === LIMIT) {
        const note = document.createElement('p');
        note.textContent = `Showing the first ${LIMIT} only.`;
        space.appendChild(note);
      }
    } catch (error) {
      space.textContent = 'Could not load invoices.';
    }
    return event;
  });
})();
```

To set it up:

1. In the Invoices app, add these fields, using the names as the field codes:
    - a Text field `Customer_ID`
    - a Text field `Invoice_no`
    - a Drop-down field `Payment_status` with the options `Unpaid` and `Paid`
    - a Date field `Due_date`
    - a Number field `Amount`
2. In the Customers app, add a Text field with the field code `Customer_ID` and a Blank space field with the Element ID `overdue_space`.
3. Set `INVOICE_APP_ID` to the Invoices app's ID, which is the number after `/k/` in its URL.
4. [Upload the file](/kintone/kintone-upload-javascript-css/) to the Customers app.

Each condition is one string in `conditions`, and `join(' and ')` puts them together, so the query becomes `Customer_ID = "C-001" and Payment_status in ("Unpaid") and Due_date < TODAY()`. To add a condition, add a line to the array.

Which operator works depends on the field type. A Drop-down field can't use `=`, so `Payment_status` uses `in`, which also takes several options, like `in ("Unpaid", "Partly paid")`. `TODAY()` is the date on which the query runs.

`quote()` wraps a value in double quotes and puts a backslash before any `"` or `\` inside it. Use it for any value that comes from a field, so a `"` in the data can't end the string early and break the query.

`order by` and `limit` go after all the conditions. `limit 500` is the most one call can return. When exactly 500 come back there may be more, so the script says it is showing the first 500 only. To get the rest, fetch the next 500 with `offset`, as `fetchAll()` does in the post linked above.

When nothing matches, the script says so. An empty list would leave the space blank, which looks the same as a script that didn't run.

## Mix `and` with `or`

Always put the `or` part in parentheses:

```js
const conditions = [
  `Customer_ID = ${quote(customerId)}`,
  `(Payment_status in ("Unpaid") or Amount >= 100000)`,
];
```

The parentheses keep the customer condition applying to both halves. Without them, the query can be read as "this customer's unpaid invoices, or any invoice of 100,000 or more", which pulls in other customers' invoices.

## Skip conditions that are empty

When a condition comes from a field that may be blank, add it only if there's a value:

```js
const conditions = [
  `Customer_ID = ${quote(customerId)}`,
];
const region = event.record.Region.value;
if (region) {
  conditions.push(`Region = ${quote(region)}`);
}
```

Otherwise `Region = ""` would only match invoices whose region is blank. The main script stops early on a blank `Customer_ID` for the same reason.

## Operators by field type

| Field type | Example |
| --- | --- |
| Text | `Customer_ID = "C-001"`, `Name like "Tokyo"` |
| Number | `Amount >= 100000` |
| Date | `Due_date < TODAY()`, `Due_date >= "2026-11-01"` |
| Drop-down, Radio button | `Payment_status in ("Unpaid")` |
| Check box, Multi-choice | `Tags in ("Urgent")` |
| Status | `Status in ("In progress")` |

`not in` and `not like` work wherever `in` and `like` do. `like` matches values that contain the keyword, with the same limits as Kintone's own search, so part of a word may not match. Use `=` when you need an exact match.

**References**

1. [Query Operators and Functions – Kintone Developer Program](https://kintone.dev/en/docs/kintone/overview/query-string/)
2. [Get Records – Kintone Developer Program](https://kintone.dev/en/docs/kintone/rest-api/records/get-records/)
3. [Kintone REST API Request – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/api/kintone-rest-api-request/)
