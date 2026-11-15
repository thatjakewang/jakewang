---
title: How to Show or Hide Kintone Fields Based on a Field Value
date: 2026-11-15
category: kintone
tags: [Forms]
slug: kintone-show-hide-fields-by-value
---

You want a form to show only the fields that apply to what someone picked, for example the address fields only when the `Delivery_method` is `Deliver`. Kintone's form shows every field all the time, so you have to show and hide the fields with JavaScript when the choice changes.

## Show the fields for each choice

```js
(() => {
  'use strict';

  const SOURCE_FIELD = 'Delivery_method';

  const SHOWN = {
    Deliver: ['Address', 'Delivery_notes'],
    Pickup: ['Pickup_store'],
  };

  const FIELDS = [...new Set(Object.values(SHOWN).flat())];

  const EVENTS = [
    'app.record.create.show',
    'app.record.edit.show',
    'app.record.detail.show',
    'app.record.print.show',
    `app.record.create.change.${SOURCE_FIELD}`,
    `app.record.edit.change.${SOURCE_FIELD}`,
  ];

  kintone.events.on(EVENTS, (event) => {
    const shown = SHOWN[event.record[SOURCE_FIELD].value] || [];
    for (const field of FIELDS) {
      kintone.app.record.setFieldShown(field, shown.includes(field));
    }
    return event;
  });
})();
```

To set it up:

1. On the form, add a Drop-down field with the field code `Delivery_method` and the options `Deliver` and `Pickup`.
2. Add Text fields with the field codes `Address` and `Pickup_store`, and a Text area field with the field code `Delivery_notes`.
3. [Upload the file](/kintone/kintone-upload-javascript-css/).

`SHOWN` maps each choice to the fields visible for it. `FIELDS` is every field named in `SHOWN`, so a field is hidden whenever the current choice doesn't list it. With nothing picked, all of them are hidden.

`kintone.app.record.setFieldShown()` hides or shows a field by its field code. It does nothing for a field code that doesn't exist, so check the codes if a field stays visible.

The change events run when someone picks another option, and `event.record` already holds the new value then. The `show` events run when a screen opens, so a saved record opens with the right fields showing. The details and print screens are in `EVENTS` too. Without them, the hidden fields would come back when someone views or prints the record.

For the other field types that have a change event, see [How to Auto-Fill a Kintone Field When Another Field Changes](/kintone/kintone-auto-fill-field-on-change/).

## Clear the fields you hide

A hidden field keeps its value. If someone types an address and then switches to `Pickup`, the address is still saved with the record. To empty a field when the choice hides it, clear it in the change events:

```js
kintone.events.on(EVENTS, (event) => {
  const shown = SHOWN[event.record[SOURCE_FIELD].value] || [];
  const changed = event.type.includes('.change.');
  for (const field of FIELDS) {
    const isShown = shown.includes(field);
    kintone.app.record.setFieldShown(field, isShown);
    if (changed && !isShown) {
      event.record[field].value = '';
    }
  }
  return event;
});
```

The `changed` check keeps the `show` events from clearing anything, so opening a record never changes it. An empty string clears a Text or Text area field.

## Don't make a hidden field required

**Required field** in a field's settings applies whether the field is showing or not. If `Address` is required and hidden, the record can't be saved, and the person can't see the field that is stopping them.

Leave the setting off for fields that can be hidden, and check them when the record is saved instead:

```js
kintone.events.on(['app.record.create.submit', 'app.record.edit.submit'], (event) => {
  const record = event.record;
  if (record.Delivery_method.value === 'Deliver' && !record.Address.value) {
    record.Address.error = 'Enter the delivery address.';
  }
  return event;
});
```

For more on these checks, see [How to Add Custom Validation to a Kintone Record Using JavaScript](/kintone/kintone-custom-validation-javascript/).

## Hide a whole section

`setFieldShown()` takes more than single fields:

- A Group field's code hides every field inside the group.
- A Table field's code hides the whole table.
- The code of a field inside a table hides that column.
- A Blank space field's Element ID hides the space, along with anything a script has put in it.

To keep `SHOWN` short, put each choice's fields in a Group field and list the group. For groups that follow a record's status, see [How to Show Kintone Field Groups by Workflow Status](/kintone/kintone-workflow-field-groups/).

## Hiding is not security

Hiding a field only changes what's on the form. Anyone who can view the record can still see the value in list views, exports and the REST API. For fields people mustn't see, use **Field Permissions** instead.

The handler only runs on the screens in `EVENTS`. `setFieldShown()` doesn't work on the record list, and the mobile view needs its own file with the `mobile.` event names.

**References**

1. [kintone.app.record.setFieldShown() – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/record/show-or-hide-a-field/)
2. [Record Create Field Change event – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/create/create-change-event/)
3. [Record Edit Field Change event – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/edit/edit-change-event/)
4. [Record Create Show event – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/create/create-show-event/)
5. [Event Object Actions – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/event-object-actions/)
