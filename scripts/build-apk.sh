#!/usr/bin/env bash
# ============================================================================
# Rongle APK Build Script
#
# Builds a debug APK from the web app using Capacitor + Gradle.
#
# Prerequisites:
#   - Node.js 18+
#   - Android SDK (set ANDROID_HOME / ANDROID_SDK_ROOT)
#   - JDK 17+ (java -version)
#
# Usage:
#   ./scripts/build-apk.sh          # Build debug APK
#   ./scripts/build-apk.sh release  # Build release APK (needs signing)
#
# Output:
#   android/app/build/outputs/apk/debug/app-debug.apk
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "=== Rongle APK Builder ==="
echo ""

# 1. Check prerequisites
echo "[1/5] Checking prerequisites..."

if ! command -v node &>/dev/null; then
  echo "ERROR: Node.js not found. Install Node.js 18+."
  exit 1
fi

if ! command -v java &>/dev/null; then
  echo "ERROR: Java not found. Install JDK 17+."
  exit 1
fi

if [ -z "${ANDROID_HOME:-}" ] && [ -z "${ANDROID_SDK_ROOT:-}" ]; then
  # Try common locations
  for SDK_PATH in "$HOME/Android/Sdk" "$HOME/Library/Android/sdk" "/usr/lib/android-sdk"; do
    if [ -d "$SDK_PATH" ]; then
      export ANDROID_HOME="$SDK_PATH"
      export ANDROID_SDK_ROOT="$SDK_PATH"
      echo "  Found Android SDK at: $SDK_PATH"
      break
    fi
  done
  if [ -z "${ANDROID_HOME:-}" ]; then
    echo "ERROR: Android SDK not found. Set ANDROID_HOME or ANDROID_SDK_ROOT."
    echo "  Install Android Studio or use: sdkmanager 'platforms;android-34' 'build-tools;34.0.0'"
    exit 1
  fi
fi

echo "  Node: $(node --version)"
echo "  Java: $(java -version 2>&1 | head -1)"
echo "  SDK:  ${ANDROID_HOME:-${ANDROID_SDK_ROOT}}"
echo ""

# 2. Install deps if needed
echo "[2/5] Installing dependencies..."
if [ ! -d "node_modules" ]; then
  npm install
else
  echo "  node_modules exists, skipping."
fi
echo ""

# 3. Build web app
echo "[3/5] Building web app (Vite)..."
npm run build
echo ""

# 4. Sync to Android
echo "[4/5] Syncing to Android project..."
npx cap sync android
echo ""

# 5. Build APK
BUILD_TYPE="${1:-debug}"
echo "[5/5] Building $BUILD_TYPE APK..."

cd android

if [ "$BUILD_TYPE" = "release" ]; then
  ./gradlew assembleRelease
  APK_PATH="app/build/outputs/apk/release/app-release-unsigned.apk"
  echo ""
  echo "NOTE: Release APK is unsigned. Sign with:"
  echo "  apksigner sign --ks your-keystore.jks $APK_PATH"
else
  ./gradlew assembleDebug
  APK_PATH="app/build/outputs/apk/debug/app-debug.apk"
fi

cd ..

if [ -f "android/$APK_PATH" ]; then
  SIZE=$(du -h "android/$APK_PATH" | cut -f1)
  echo ""
  echo "=== BUILD SUCCESSFUL ==="
  echo "APK: android/$APK_PATH ($SIZE)"
  echo ""
  echo "Install on device:"
  echo "  adb install android/$APK_PATH"
  echo ""
  echo "Or transfer to phone and install directly."
else
  echo "ERROR: APK not found at expected path."
  exit 1
fi
