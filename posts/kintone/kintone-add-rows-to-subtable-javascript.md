---
title: How to Add Rows to a Kintone Subtable With JavaScript
date: 2026-11-14
category: kintone
tags: [Forms, Tables]
slug: kintone-add-rows-to-subtable-javascript
---

You want a table to fill itself with rows, for example an `Items` table that lists a package's standard items when someone picks a `Package`. Kintone's field settings can't add rows to a Table field (a subtable), and a Lookup field copies single values, not rows. To add rows, you have to change the table's value in an event handler with JavaScript.

## Add rows when a choice changes

```js
(() => {
  'use strict';

  const SOURCE_FIELD = 'Package';
  const TABLE_FIELD = 'Items';

  const PACKAGES = {
    Starter: [
      { item: 'Laptop', quantity: '1' },
      { item: 'Charger', quantity: '1' },
    ],
    Office: [
      { item: 'Laptop', quantity: '1' },
      { item: 'Monitor', quantity: '2' },
      { item: 'Keyboard', quantity: '1' },
    ],
  };

  const EVENTS = [
    `app.record.create.change.${SOURCE_FIELD}`,
    `app.record.edit.change.${SOURCE_FIELD}`,
  ];

  const newRow = ({ item, quantity }) => ({
    value: {
      Item: { type: 'SINGLE_LINE_TEXT', value: item },
      Quantity: { type: 'NUMBER', value: quantity },
    },
  });

  kintone.events.on(EVENTS, (event) => {
    const items = PACKAGES[event.changes.field.value];
    if (items) {
      const table = event.record[TABLE_FIELD];
      const filled = table.value.filter((row) => row.value.Item.value);
      table.value = [...filled, ...items.map(newRow)];
    }
    return event;
  });
})();
```

To set it up:

1. On the form, add a Drop-down field with the field code `Package` and the options `Starter` and `Office`.
2. Add a Table field with the field code `Items`. Inside it, add a Text field with the field code `Item` and a Number field with the field code `Quantity`.
3. [Upload the file](/kintone/kintone-upload-javascript-css/).

A table's `value` is an array with one object per row. Each row has a `value` of its own, which holds the row's fields by field code. A row that has been saved also has an `id`. A new row has none, and Kintone gives it one when the record is saved.

A new row has to list every field in the table, and each field needs its `type` as well as its `value`. Leave one out and the row isn't added. A field you want empty still goes in, with `''` as its value. The types are the ones the REST API uses, such as `SINGLE_LINE_TEXT`, `NUMBER`, `DROP_DOWN` and `DATE`.

A Number field's value is a string, so the quantities in `PACKAGES` are strings.

The table on a new record starts with one empty row. The `filter` drops rows that have no `Item`, so the package's rows don't end up under a blank one. Rows that someone has already filled in stay where they are.

Setting the table's value and returning the event puts the rows on the form. Nothing is saved until the person clicks **Save**, so they can still change or delete the rows. For more on change events, see [How to Auto-Fill a Kintone Field When Another Field Changes](/kintone/kintone-auto-fill-field-on-change/).

## Replace the rows instead of adding to them

As written, picking `Starter` and then `Office` leaves both sets of rows in the table. To show only the rows of the package that is picked, set the table to the new rows alone:

```js
table.value = items.map(newRow);
```

This also deletes rows that someone typed in by hand, so use it only when the table should always match the package.

## Set a default value in a row someone adds

A table has a change event of its own, named after the table's field code. It runs when a row is added or deleted. `event.changes.row` is the new row, or `null` when a row was deleted:

```js
const EVENTS = [
  'app.record.create.change.Items',
  'app.record.edit.change.Items',
];

kintone.events.on(EVENTS, (event) => {
  const row = event.changes.row;
  if (row && !row.value.Quantity.value) {
    row.value.Quantity.value = '1';
  }
  return event;
});
```

Each row someone adds with the **+** button now starts with a quantity of `1`. The row is already in the table at this point, so the handler only sets a value and doesn't need the `type`.

A field inside a table has a change event too, named after that field's code, as in `app.record.create.change.Quantity`. There, `event.changes.row` is the row that holds the field that changed.

## Add a row from a button

Outside an event handler, for example when someone clicks a button, the record on the form is read and written with `kintone.app.record.get()` and `kintone.app.record.set()`:

```js
button.addEventListener('click', () => {
  const current = kintone.app.record.get();
  current.record.Items.value.push(newRow({ item: 'Mouse', quantity: '1' }));
  kintone.app.record.set(current);
});
```

The same rule applies: the new row lists every field with its `type`. `get()` and `set()` only work on the create and edit screens, and they can't be called inside an event handler. To put the button on the form, see [How to Create a Button in a Kintone Space Field Using JavaScript](/kintone/kintone-space-field-button-javascript/).

## Add a row through the REST API

To add a row to a record that isn't open on the form, update the record through the REST API. The request replaces the whole table. A row sent with its `id` is kept, a row without an `id` is added, and a row that isn't in the request is deleted. So get the record first, and send its rows back together with the new one:

```js
const URL = kintone.api.url('/k/v1/record.json', true);
const params = { app: kintone.app.getId(), id: recordId };

const resp = await kintone.api(URL, 'GET', params);

const rows = resp.record.Items.value.map((row) => ({
  id: row.id,
  value: {
    Item: { value: row.value.Item.value },
    Quantity: { value: row.value.Quantity.value },
  },
}));
rows.push({
  value: {
    Item: { value: 'Mouse' },
    Quantity: { value: '1' },
  },
});

await kintone.api(URL, 'PUT', { ...params, record: { Items: { value: rows } } });
```

The REST API doesn't need the `type`. For the rest of the request, see [How to Update a Record in Another Kintone App When a Record Is Saved](/kintone/kintone-update-record-in-another-app/).

## Limits to keep in mind

The handlers above run in the browser, on the screens the file is loaded for. Records added through the REST API or a file import skip them. Tables aren't shown on the record list, so `EVENTS` has no record list event. The mobile view needs its own file with the `mobile.` event names.

Kintone ignores a value set on a Calculated field or a Lookup field inside a table, the same as outside one. A new row still has to list those fields.

Keep tables short. A table with a very large number of rows slows down the record's screen and REST API requests for it.

**References**

1. [Field Types – Kintone Developer Program](https://kintone.dev/en/docs/kintone/overview/field-types/)
2. [Event Object Actions – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/event-object-actions/)
3. [Record Create Field Change event – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/create/create-change-event/)
4. [Record Edit Field Change event – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/edit/edit-change-event/)
5. [Get Record Details – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/record/get-record/)
6. [Set Record Value – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/record/set-record-value/)
7. [Update Record – Kintone Developer Program](https://kintone.dev/en/docs/kintone/rest-api/records/update-record/)
