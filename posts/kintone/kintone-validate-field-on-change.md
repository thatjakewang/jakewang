---
title: How to Validate a Kintone Field as Soon as It Changes
date: 2026-11-15
category: kintone
tags: [Forms, Validation]
slug: kintone-validate-field-on-change
---

You want people to see a mistake while they are still filling in the form, for example an `End date` that is earlier than the `Start date`. A check that runs when the record is saved only shows the error after someone clicks **Save**. To show it right away, you have to run the check in the fields' change events with JavaScript.

## Show the error when either field changes

```js
(() => {
  'use strict';

  const START_FIELD = 'Start_date';
  const END_FIELD = 'End_date';

  const SCREENS = [
    'app.record.create',
    'app.record.edit',
    'app.record.index.edit',
  ];

  const EVENTS = SCREENS.flatMap((screen) => [
    `${screen}.change.${START_FIELD}`,
    `${screen}.change.${END_FIELD}`,
    `${screen}.submit`,
  ]);

  kintone.events.on(EVENTS, (event) => {
    const record = event.record;
    const start = record[START_FIELD].value;
    const end = record[END_FIELD].value;

    record[END_FIELD].error = start && end && end < start
      ? 'The end date must be on or after the start date.'
      : null;
    return event;
  });
})();
```

To set it up:

1. On the form, add two Date fields with the field codes `Start_date` and `End_date`.
2. [Upload the file](/kintone/kintone-upload-javascript-css/).

A change event runs each time its field's value changes. Setting `error` on a field and returning the event shows the message in red under that field, the same as in a `submit` event.

The rule compares two fields, so the handler listens to both. Changing the start date can break the rule as easily as changing the end date can.

Setting `error` to `null` removes the message. Without it, the error would stay under the field after someone corrects the date.

The `submit` events are in `EVENTS` too, so the rule is checked again when someone clicks **Save**, and the save is cancelled if it still fails. That covers a record nobody touched the dates on, such as one that was imported with the wrong dates and then edited.

`app.record.index.edit` is a record edited in place on the record list. For more on the `submit` events, see [How to Add Custom Validation to a Kintone Record Using JavaScript](/kintone/kintone-custom-validation-javascript/).

## Check the format of a text field

The same pattern checks one field against a format, for example an `Employee_ID` that must be `E` followed by five digits:

```js
const FIELD = 'Employee_ID';
const FORMAT = /^E\d{5}$/;

const EVENTS = [
  `app.record.create.change.${FIELD}`,
  `app.record.edit.change.${FIELD}`,
  'app.record.create.submit',
  'app.record.edit.submit',
];

kintone.events.on(EVENTS, (event) => {
  const field = event.record[FIELD];
  field.error = field.value && !FORMAT.test(field.value)
    ? 'Use E followed by five digits, for example E01234.'
    : null;
  return event;
});
```

A Text or Number field's change event runs when the cursor leaves the field, not on each keystroke. The error appears when someone moves on to the next field, which is early enough to fix it before the rest of the form is filled in.

An empty field passes this check. To make it mandatory, turn on **Required field** in its settings.

## Show the error when the form opens

A record can already break the rule when someone opens it to edit. To show the error straight away, add the edit screen's `show` event to `EVENTS`:

```js
'app.record.edit.show',
```

The handler reads the values from `event.record`, so it works unchanged there.

## Which fields can be checked on change

Change events exist for Drop-down, Radio button, Check box, Multi-choice, Date, Time, Date and time, User selection, Department selection, Group selection, Text and Number fields. Text area, Rich text and Attachment fields have none, so check those in the `submit` events only.

A change event doesn't wait for a Promise the way a `submit` event does. A rule that has to look at another app, such as rejecting an invoice number that doesn't exist, belongs in the `submit` events. To set a field from another app when a field changes, see [How to Auto-Fill a Kintone Field When Another Field Changes](/kintone/kintone-auto-fill-field-on-change/).

## Validation is not enforcement

These checks only run in the browser, on the screens the file is loaded for. Records added through the REST API or a file import skip them. The mobile view needs its own file with the `mobile.` event names.

**References**

1. [Event Object Actions – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/event-object-actions/)
2. [Record Create Field Change event – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/create/create-change-event/)
3. [Record Edit Field Change event – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/edit/edit-change-event/)
4. [Record List Field Change event – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/idx/index-edit-change-event/)
5. [Record Create Submit event – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/create/create-submit-event/)
6. [Record Edit Submit event – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/edit/edit-submit-event/)
