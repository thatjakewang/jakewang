---
title: How to Show Kintone Field Groups by Workflow Status
date: 2026-11-05
updated: 2026-11-10
category: kintone
tags: [Process Management, Forms]
slug: kintone-workflow-field-groups
---

You want a record to show only the fields that matter at its current step, for example the review fields only once a request is in review. Kintone's form shows every field at every status, so you have to hide the other Group fields with JavaScript.

## Show the groups for each status

```js
(() => {
  'use strict';

  const GROUPS = ['Request', 'Review', 'Approval'];

  const SHOWN = {
    'Not started': ['Request'],
    'In progress': ['Request', 'Review'],
    'Completed': ['Request', 'Review', 'Approval'],
  };

  const ON_CREATE = ['Request'];

  const EVENTS = [
    'app.record.create.show',
    'app.record.detail.show',
    'app.record.edit.show',
    'app.record.print.show',
  ];

  kintone.events.on(EVENTS, (event) => {
    const shown = event.type === 'app.record.create.show'
      ? ON_CREATE
      : SHOWN[event.record.Status.value] || GROUPS;
    for (const group of GROUPS) {
      const isShown = shown.includes(group);
      kintone.app.record.setFieldShown(group, isShown);
    }
    return event;
  });
})();
```

To set it up:

1. Turn on Process Management with the statuses `Not started`, `In progress` and `Completed`.
2. On the form, add three Group fields with the field codes `Request`, `Review` and `Approval`.
3. Put each step's fields inside its group.
4. [Upload the file](/kintone/kintone-upload-javascript-css/).

`SHOWN` maps each status to the groups visible at that status, and `GROUPS` lists every group the script controls. A status missing from `SHOWN` shows all of them, so a status you add later doesn't hide anything by accident.

`event.record.Status.value` is the record's current status. `Status` is the field code of the status field, which isn't the same in every app, so check it in the form settings.

`kintone.app.record.setFieldShown()` hides or shows a field by its field code. Hiding a Group field hides every field inside it.

A new record has no status until it's saved, so the create screen can't look one up in `SHOWN`. It shows the groups in `ON_CREATE` instead, which is the first step's.

The print screen is in `EVENTS` too. Without it, the hidden groups would come back when someone prints the record.

## Open the current step's group

Group fields can start closed. To open the group for the current step, add this after the `for` loop:

```js
const current = shown[shown.length - 1];
kintone.app.record.setGroupFieldOpen(current, true);
```

The last group in each `SHOWN` list is the current step, so that's the one this opens. The earlier groups keep their open or closed setting.

## Hiding is not security

Hiding a group only changes what's on screen. The fields keep their values, and anyone who can view the record can still see them in list views, exports and the REST API. For fields people mustn't see, use **Field Permissions** instead.

To see how many records are at each status, see [How to Add a Status Chart to a Kintone List With Chart.js](/kintone/kintone-record-list-status-chart/).

To stop a record from moving to the next status until its fields are filled in, see [How to Add Custom Validation to a Kintone Record Using JavaScript](/kintone/kintone-custom-validation-javascript/).

**References**

1. [kintone.app.record.setFieldShown() – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/record/show-or-hide-a-field/)
2. [kintone.app.record.setGroupFieldOpen() – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/record/open-field-group/)
