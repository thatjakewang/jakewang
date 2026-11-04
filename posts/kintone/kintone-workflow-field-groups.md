---
title: How to Show Only Relevant Field Groups Based on a Workflow Status in Kintone Using JavaScript
date: 2026-11-05
category: kintone
tags: [JavaScript]
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

  const EVENTS = [
    'app.record.detail.show',
    'app.record.edit.show',
  ];

  kintone.events.on(EVENTS, (event) => {
    const status = event.record.Status.value;
    const shown = SHOWN[status] || GROUPS;
    for (const group of GROUPS) {
      const isShown = shown.includes(group);
      kintone.app.record.setFieldShown(group, isShown);
    }
    return event;
  });
})();
```

Turn on Process Management with the statuses `Not started`, `In progress` and `Completed`. On the form, add three Group fields with the field codes `Request`, `Review` and `Approval`, and put each step's fields inside its group. Upload the file under **App Settings** > **Customization and Integration** > **JavaScript and CSS Customization** > **JavaScript Files for PC**, then click **Update App**.

`SHOWN` maps each status to the groups visible at that status, and `GROUPS` lists every group the script controls. A status missing from `SHOWN` shows all of them, so a status you add later doesn't hide anything by accident.

`event.record.Status.value` is the record's current status. `Status` is the field code of the status field, which isn't the same in every app, so check it in the form settings.

`kintone.app.record.setFieldShown()` hides or shows a field by its field code. Hiding a Group field hides every field inside it.

The create screen is left out because a new record has no status until it's saved.

## Open the current step's group

Group fields can start closed. To open the group for the current step, add this after the `for` loop:

```js
const current = shown[shown.length - 1];
kintone.app.record.setGroupFieldOpen(current, true);
```

The last group in each `SHOWN` list is the current step, so that's the one this opens. The earlier groups keep their open or closed setting.

Hiding a group only changes what's on screen. The fields keep their values, and anyone who can view the record can still see them in list views, exports and the REST API. For fields people mustn't see, use **Field Permissions** instead.

**References**

1. [kintone.app.record.setFieldShown() – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/record/show-or-hide-a-field/)
2. [kintone.app.record.setGroupFieldOpen() – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/record/open-field-group/)
