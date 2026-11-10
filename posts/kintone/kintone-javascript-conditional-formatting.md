---
title: How to Apply Conditional Formatting to Kintone Fields Using JavaScript
date: 2026-11-04
category: kintone
tags: [List view, Styling]
slug: kintone-javascript-conditional-formatting
---

You want a field to stand out when it has a certain value, for example a red, bold `Priority` when it's `High`. Kintone's form settings can't style fields by value, so you have to do it with JavaScript.

## Style a field when its value matches

```js
(() => {
  'use strict';

  const FIELD = 'Priority';
  const VALUE = 'High';

  const STYLE = {
    color: '#b42318',
    backgroundColor: '#fef3f2',
    fontWeight: 'bold',
  };

  kintone.events.on('app.record.detail.show', (event) => {
    if (event.record[FIELD].value === VALUE) {
      const el = kintone.app.record.getFieldElement(FIELD);
      if (el) {
        Object.assign(el.style, STYLE);
      }
    }
    return event;
  });

  kintone.events.on('app.record.index.show', (event) => {
    const cells = kintone.app.getFieldElements(FIELD);
    if (!cells) {
      return event;
    }
    event.records.forEach((record, i) => {
      if (record[FIELD].value === VALUE) {
        Object.assign(cells[i].style, STYLE);
      }
    });
    return event;
  });
})();
```

To set it up:

1. On the form, add a Drop-down field with the field code `Priority` and an option `High`.
2. Add `Priority` to the list view as a column.
3. [Upload the file](/kintone/kintone-upload-javascript-css/).

`kintone.app.record.getFieldElement()` returns the field's value element on the record details screen. It doesn't work on the create and edit screens, so the formatting only appears once the record is saved.

`kintone.app.getFieldElements()` returns one element per row in a List view, in the same order as `event.records`. It returns `null` if the field isn't in the view, so the field has to be one of the view's columns. It also returns `null` in a Calendar view or a Custom view, so the handler does nothing there.

The styling is applied when the list loads. If you change a record's `Priority` by editing it in the list, reload the page to update its formatting.

`Object.assign(el.style, STYLE)` copies every property in `STYLE` onto the element, so you change the look by editing `STYLE` only.

## Other styles

Swap these into `STYLE`:

| Style | Property |
| --- | --- |
| Text color | `color: '#b42318'` |
| Background color | `backgroundColor: '#fef3f2'` |
| Bold | `fontWeight: 'bold'` |
| Font size | `fontSize: '16px'` |
| Underline | `textDecoration: 'underline'` |
| Strikethrough | `textDecoration: 'line-through'` |
| Border color | `border: '2px solid #d92d20'` |

## Highlight the whole row

Replace the `app.record.index.show` handler with this:

```js
kintone.events.on('app.record.index.show', (event) => {
  const cells = kintone.app.getFieldElements(FIELD);
  if (!cells) {
    return event;
  }
  event.records.forEach((record, i) => {
    if (record[FIELD].value !== VALUE) {
      return;
    }
    const row = cells[i].closest('tr');
    for (const cell of row.cells) {
      cell.style.backgroundColor = '#fef3f2';
    }
  });
  return event;
});
```

Kintone has no API for a whole row, so this finds the row from one of its cells with `closest('tr')` and colors every cell in it. Coloring each cell, not the `tr`, still works if the cells have a background of their own.

Field labels have no API at all. Styling them means relying on Kintone's internal class names, which can change with any update, so I'd leave labels alone.

**References**

1. [kintone.app.record.getFieldElement() – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/record/get-record-field-element/)
2. [kintone.app.getFieldElements() – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/app/get-record-list-field-elements/)
