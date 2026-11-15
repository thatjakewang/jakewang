---
title: How to Add a Live Progress Bar to a Kintone Form
date: 2026-11-15
category: kintone
tags: [Forms, CSS]
slug: kintone-form-progress-bar
---

You want a form to show how far along it is while someone fills it in, for example "3 of 5 fields filled in" with a bar that grows. A Calculated field can work out a number, but it can't count empty fields or draw anything. To show a summary that updates as people type, you have to draw it in a Blank space field with JavaScript and redraw it in the fields' change events.

## Show how many fields are filled in

```js
(() => {
  'use strict';

  const SPACE_ID = 'progress_space';
  const FIELDS = ['Customer', 'Email', 'Phone', 'Plan', 'Start_date'];

  const EVENTS = [
    'app.record.create.show',
    'app.record.edit.show',
    ...FIELDS.flatMap((field) => [
      `app.record.create.change.${field}`,
      `app.record.edit.change.${field}`,
    ]),
  ];

  const isFilled = (value) => (Array.isArray(value) ? value.length > 0 : Boolean(value));

  kintone.events.on(EVENTS, (event) => {
    const space = kintone.app.record.getSpaceElement(SPACE_ID);
    if (!space) {
      return event;
    }

    const filled = FIELDS.filter((field) => isFilled(event.record[field].value)).length;

    const label = document.createElement('p');
    label.className = 'form-progress-label';
    label.textContent = `${filled} of ${FIELDS.length} fields filled in`;

    const bar = document.createElement('progress');
    bar.className = 'form-progress-bar';
    bar.max = FIELDS.length;
    bar.value = filled;

    space.replaceChildren(label, bar);
    return event;
  });
})();
```

To set it up:

1. On the form, add Text fields with the field codes `Customer`, `Email` and `Phone`, a Drop-down field with the field code `Plan`, and a Date field with the field code `Start_date`.
2. Add a Blank space field with the Element ID `progress_space` at the top of the form.
3. [Upload the file](/kintone/kintone-upload-javascript-css/) as a JavaScript file.

`EVENTS` holds the `show` events, which draw the panel when the form opens, and a change event for each field in `FIELDS`, which redraw it. `event.record` already holds the new value during a change event, so the count is up to date.

`kintone.app.record.getSpaceElement()` returns the Blank space field's element, or `null` if no field has that Element ID. `replaceChildren()` swaps the old label and bar for the new ones, so the panel never appears twice.

`isFilled()` treats an empty string and a missing value as empty. A Check box, Multi-choice or User selection field's value is an array, which counts as filled when it has at least one entry.

A Text or Number field's change event runs when the cursor leaves the field, not on each keystroke, so the bar moves when someone goes on to the next field. Text area, Rich text and Attachment fields have no change event and can't be counted this way.

## Style the panel

```css
.form-progress-label {
  margin: 0 0 4px;
  color: #666666;
  font-size: 12px;
}

.form-progress-bar {
  width: 240px;
  height: 8px;
}
```

[Upload this file](/kintone/kintone-upload-javascript-css/) as a CSS file.

The class names are ones the JavaScript sets, not Kintone's own, so a Kintone update won't break the styling. A `<progress>` element is drawn by the browser, and it looks a little different in each one.

## Summarise a table instead

The same panel can describe a table, for example the number of rows in an `Items` table and their total. Listen to the table and to the fields inside it:

```js
const TABLE_EVENTS = ['Items', 'Quantity', 'Unit_price'].flatMap((field) => [
  `app.record.create.change.${field}`,
  `app.record.edit.change.${field}`,
]);
```

Then work the summary out from the rows:

```js
const rows = event.record.Items.value;
const total = rows.reduce((sum, row) => {
  const quantity = Number(row.value.Quantity.value || 0);
  const price = Number(row.value.Unit_price.value || 0);
  return sum + quantity * price;
}, 0);

label.textContent = `${rows.length} rows, total ${total.toLocaleString()}`;
```

A table's change event runs when a row is added or deleted, and the events for `Quantity` and `Unit_price` run when a value in a row changes. A Number field's value is a string, so `Number()` turns it into a number first, and an empty one counts as `0`.

If all you need is the total, a Calculated field with `SUM()` does it without code. The panel is for what a Calculated field can't show, such as the row count or several figures in one line. For more on tables, see [How to Add Rows to a Kintone Subtable With JavaScript](/kintone/kintone-add-rows-to-subtable-javascript/).

## The panel is only on the form

The panel is drawn on the create and edit screens. To show it on the record details screen as well, add `app.record.detail.show` to `EVENTS`.

Nothing is saved with the record. To keep a figure, put it in a field as described in [How to Auto-Fill a Kintone Field When Another Field Changes](/kintone/kintone-auto-fill-field-on-change/). The mobile view needs its own file with the `mobile.` event names.

To show a hint under a single field, see [How to Add Helper Text Below a Kintone Field With JavaScript](/kintone/kintone-field-helper-text/).

**References**

1. [kintone.app.record.getSpaceElement() – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/record/get-space-element/)
2. [Record Create Show event – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/create/create-show-event/)
3. [Record Create Field Change event – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/create/create-change-event/)
4. [Record Edit Field Change event – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/edit/edit-change-event/)
