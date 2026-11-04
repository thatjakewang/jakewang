---
title: How to Create a Button in a Kintone Space Field Using JavaScript
date: 2026-11-04
category: [kintone, javascript]
slug: kintone-space-field-button-javascript
---

You want a button on a Kintone record form, for example one that sets a Date field to today. Kintone has no button field, so you have to add one to a Blank space field with JavaScript.

## Add the button to a Blank space field

```js
(() => {
  'use strict';

  const SPACE_ID = 'set_today_space';
  const DATE_FIELD = 'Due_date';

  const EVENTS = [
    'app.record.create.show',
    'app.record.edit.show',
  ];

  const toDateString = (date) => {
    const pad = (n) => String(n).padStart(2, '0');
    const y = date.getFullYear();
    const m = pad(date.getMonth() + 1);
    const d = pad(date.getDate());
    return `${y}-${m}-${d}`;
  };

  kintone.events.on(EVENTS, (event) => {
    const space = kintone.app.record.getSpaceElement(SPACE_ID);
    if (!space || space.querySelector('button')) {
      return event;
    }

    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = 'Set to today';
    button.addEventListener('click', () => {
      const current = kintone.app.record.get();
      current.record[DATE_FIELD].value = toDateString(new Date());
      kintone.app.record.set(current);
    });

    space.appendChild(button);
    return event;
  });
})();
```

On the form, add a Blank space field with the Element ID `set_today_space` and a Date field with the field code `Due_date`. Upload the file under **App Settings** > **Customization and Integration** > **JavaScript and CSS Customization** > **JavaScript Files for PC**, then click **Update App**.

`kintone.app.record.getSpaceElement()` returns the Blank space field's element, or `null` if no field has that Element ID. The `querySelector('button')` check keeps the button from being added twice.

`kintone.app.record.set()` can't be called inside a `kintone.events.on` handler, so the button reads and writes the record in its click handler instead. `set()` only works on the create and edit screens, so the button is only added there.

The date is formatted by hand because `toISOString()` uses UTC and can be a day off.

**References**

1. [kintone.app.record.getSpaceElement() – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/record/get-space-element/)
2. [kintone.app.record.set() – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/record/set-record-value/)
3. [Record Create Show event – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/create/create-show-event/)
