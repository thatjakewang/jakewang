---
title: How to Query Another Kintone App Using Multiple Conditions in JavaScript
date: 2026-11-09
category: kintone
tags: [JavaScript]
slug: kintone-query-another-app-multiple-conditions
---

You want records from another app that match more than one condition, for example a Customers record listing that customer's invoices that are unpaid and past their due date. The Get Records API takes a single query string, so you have to join the conditions with `and` or `or` in JavaScript.

## Join the conditions with `and`

```js
(() => {
  'use strict';

  const INVOICE_APP_ID = 12;
  const SPACE_ID = 'overdue_space';
  const URL = kintone.api.url('/k/v1/records.json', true);

  const quote = (value) => `"${value.replace(/["\\]/g, '\\$&')}"`;

  kintone.events.on('app.record.detail.show', async (event) => {
    const space = kintone.app.record.getSpaceElement(SPACE_ID);
    if (!space) {
      return event;
    }

    const conditions = [
      `Customer_ID = ${quote(event.record.Customer_ID.value)}`,
      `Payment_status in ("Unpaid")`,
      `Due_date < TODAY()`,
    ];

    const resp = await kintone.api(URL, 'GET', {
      app: INVOICE_APP_ID,
      query: `${conditions.join(' and ')} order by Due_date asc limit 500`,
      fields: ['Invoice_no', 'Due_date', 'Amount'],
    });

    const list = document.createElement('ul');
    for (const r of resp.records) {
      const item = document.createElement('li');
      item.textContent = `${r.Invoice_no.value} (due ${r.Due_date.value}): ${Number(r.Amount.value).toLocaleString()}`;
      list.appendChild(item);
    }
    space.replaceChildren(list);
    return event;
  });
})();
```

In the Invoices app, add a Text field `Customer_ID`, a Text field `Invoice_no`, a Drop-down field `Payment_status` with the options `Unpaid` and `Paid`, a Date field `Due_date` and a Number field `Amount`, using those as the field codes. In the Customers app, add a Text field with the field code `Customer_ID` and a Blank space field with the Element ID `overdue_space`. Set `INVOICE_APP_ID` to the Invoices app's ID, which is the number after `/k/` in its URL. Upload the file to the Customers app under **App Settings** > **Customization and Integration** > **JavaScript and CSS Customization** > **JavaScript Files for PC**, then click **Update App**.

Each condition is one string in `conditions`, and `join(' and ')` puts them together, so the query becomes `Customer_ID = "C-001" and Payment_status in ("Unpaid") and Due_date < TODAY()`. To add a condition, add a line to the array.

Which operator works depends on the field type. A Drop-down field can't use `=`, so `Payment_status` uses `in`, which also takes several options, like `in ("Unpaid", "Partly paid")`. `TODAY()` is the current date in the viewing person's time zone.

`quote()` wraps a value in double quotes and puts a backslash before any `"` or `\` inside it. Use it for any value that comes from a field, so a `"` in the data can't end the string early and break the query.

`order by` and `limit` go after all the conditions. `limit 500` is the most one call can return, so for more records than that, fetch the next 500 with `offset`.

## Mix `and` with `or`

`and` is evaluated before `or`, so put the `or` part in parentheses:

```js
const conditions = [
  `Customer_ID = ${quote(event.record.Customer_ID.value)}`,
  `(Payment_status in ("Unpaid") or Amount >= 100000)`,
];
```

Without the parentheses, the query would return every invoice of 100,000 or more from all customers, not just this one.

## Skip conditions that are empty

When a condition comes from a field that may be blank, add it only if there's a value:

```js
const conditions = [
  `Customer_ID = ${quote(event.record.Customer_ID.value)}`,
];
const region = event.record.Region.value;
if (region) {
  conditions.push(`Region = ${quote(region)}`);
}
```

Otherwise `Region = ""` would only match invoices whose region is blank.

## Operators by field type

| Field type | Example |
| --- | --- |
| Text | `Customer_ID = "C-001"`, `Name like "Tokyo"` |
| Number | `Amount >= 100000` |
| Date | `Due_date < TODAY()`, `Due_date >= "2026-11-01"` |
| Drop-down, Radio button | `Payment_status in ("Unpaid")` |
| Check box, Multi-choice | `Tags in ("Urgent")` |
| Status | `Status in ("In progress")` |

`not in` and `not like` work wherever `in` and `like` do. `like` matches any value that contains the text.

**References**

1. [Query Operators and Functions – Kintone Developer Program](https://kintone.dev/en/docs/kintone/overview/query-string/)
2. [Get Records – Kintone Developer Program](https://kintone.dev/en/docs/kintone/rest-api/records/get-records/)
3. [kintone.api() – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/other/kintone-rest-api-request/)
