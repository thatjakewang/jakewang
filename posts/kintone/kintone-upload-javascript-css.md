---
title: How to Add JavaScript and CSS Files to a Kintone App
date: 2026-11-10
category: kintone
tags: [Setup]
slug: kintone-upload-javascript-css
---

You have a JavaScript or CSS file that customizes a Kintone app and need it to run. Kintone only loads files that are registered in the app's settings, so you have to upload the file there and update the app.

## Upload a file

1. Open the app and go to **App Settings** > **Customization and Integration** > **JavaScript and CSS Customization**.
2. Under **JavaScript Files for PC**, click **Upload File** and choose your `.js` file. A `.css` file goes under **CSS Files for PC** instead.
3. Click **Save**.
4. Click **Update App**.

The file doesn't run until you click **Update App**. Saving alone only changes the settings draft, so the live app keeps using the old files.

You need permission to manage the app to see these settings.

## Load a library from a URL

To use a library such as Chart.js, click **Add Link** instead of **Upload File** and enter the library's URL. Files run from top to bottom, so drag the library above any file that uses it.

## Replace a file after editing it

Kintone keeps the copy you uploaded, not a link to the file on your computer. After you edit the file, delete the old one from the list, upload the new one, then click **Save** and **Update App** again.

## Check that the file runs

Open the app, then open the browser's developer tools with `F12` and look at the **Console** tab. A typo in a field code or an Element ID usually shows up there as an error naming the line.

## Mobile

Files under **JavaScript Files for PC** only run in the desktop view. The mobile view has its own upload section on the same page, and the code is not the same: event names start with `mobile.`, as in `mobile.app.record.detail.show`, and the functions live under `kintone.mobile.app` instead of `kintone.app`. The posts in this category are written for the desktop view.

**References**

1. [Kintone JavaScript API – Kintone Developer Program](https://kintone.dev/en/docs/kintone/js-api/)
