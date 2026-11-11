---
title: How to Add Helper Text Below a Kintone Field With JavaScript
date: 2026-11-04
category: kintone
tags: [Forms, CSS]
slug: kintone-field-helper-text
---

You want a short hint under a field while people fill in a record, for example "Include the area code" under a `Phone` field. Kintone's field settings have no place for helper text, so you have to add it to a Blank space field with JavaScript and style it with CSS.

## Add the text to a Blank space field

```js
(() => {
  'use strict';

  const HELP = {
    phone_help: 'Include the area code, for example 03-1234-5678.',
  };

  const EVENTS = [
    'app.record.create.show',
    'app.record.edit.show',
  ];

  kintone.events.on(EVENTS, (event) => {
    for (const [spaceId, text] of Object.entries(HELP)) {
      const space = kintone.app.record.getSpaceElement(spaceId);
      if (!space || space.querySelector('.field-help')) {
        continue;
      }
      const help = document.createElement('p');
      help.className = 'field-help';
      help.textContent = text;
      space.appendChild(help);
    }
    return event;
  });
})();
```

To set it up:

1. On the form, add a Text field with the field code `Phone`.
2. Put a Blank space field with the Element ID `phone_help` directly below it, at the same width.
3. [Upload the file](/kintone/kintone-upload-javascript-css/) as a JavaScript file.

`HELP` maps each Blank space field's Element ID to its text, so you add helper text to another field by adding a Blank space field below it and one line to `HELP`.

`kintone.app.record.getSpaceElement()` returns the Blank space field's element, or `null` if no field has that Element ID. The `querySelector('.field-help')` check keeps the text from being added twice.

The text is only added on the create and edit screens, where people type. On the record details screen the Blank space field stays empty.

`textContent` sets the text as plain text, so characters like `<` show up as typed instead of being read as HTML.

## Style the text

```css
.field-help {
  margin: 0;
  color: #666666;
  font-size: 12px;
  line-height: 1.5;
}
```

[Upload this file](/kintone/kintone-upload-javascript-css/) as a CSS file.

The class name `field-help` is one the JavaScript sets, not one of Kintone's own, so a Kintone update won't break the styling. To make a hint stand out as a warning, change `color` to `#b42318`.

A Blank space field can hold a button too. See [How to Create a Button in a Kintone Space Field Using JavaScript](/kintone/kintone-space-field-button-javascript/).

**References**

1. [kintone.app.record.getSpaceElement() – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/record/get-space-element/)
2. [Record Create Show event – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/events/create/create-show-event/)
