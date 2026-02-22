# Building the Android APK

This guide explains how to build the standalone Android App (`.apk`) for Rongle. This allows you to run the Controller interface on your phone without needing a PC web server.

## Prerequisites

1.  **Node.js 20+** installed.
2.  **Java JDK 17+** installed (`java -version`).
3.  **Android Studio** installed (including Android SDK and Command Line Tools).
    *   Set `ANDROID_HOME` environment variable.

## Step 1: Initialize Android Project

If you haven't already:

```bash
# In the root of the repo
npm install
npm run android:init
```

## Step 2: Build and Sync

This compiles the React code and copies it into the native Android container.

```bash
npm run android:sync
```

## Step 3: Build the APK

You can build the debug APK directly from the command line:

```bash
cd android
./gradlew assembleDebug
```

*Note: On Windows, use `gradlew.bat assembleDebug`.*

## Step 4: Locate and Install

The APK will be located at:
`android/app/build/outputs/apk/debug/app-debug.apk`

1.  **Transfer:** Copy this file to your Pixel 10 (via USB or Google Drive).
2.  **Install:** Tap the file on your phone. You may need to "Allow installation from unknown sources".

## Step 5: Configuration on Phone

Once the app is running:
1.  Open the App.
2.  Go to the **Settings** panel (Gear icon).
3.  **Portal URL:** Enter the address of your backend (e.g., `http://192.168.1.5:8000` if running the Portal, or leave blank if using direct connection settings, though the current frontend enforces Portal Proxy for VLM).
    *   *Tip:* If just testing locally, you still need the backend running on your PC/Pi. The APK replaces the *Frontend Server*, not the *Operator Backend*.
