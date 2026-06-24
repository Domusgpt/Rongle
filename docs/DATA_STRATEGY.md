# Data Strategy & Labeling Guide 📊
**Date:** 2026-02-10

To train the Rongle CNN to a 2026 industry standard, we need a high-quality, diverse dataset. This document outlines exactly what data is needed and how we will use the `llm_labeler.py` to process it.

---

## 1. Raw Data Requirements

We need 5,000+ screenshots in total. Please provide them in the following categories:

### A. OS Variety (Target Computers)
- **Windows 11:** 1,500 screenshots (various themes, light/dark mode).
- **Ubuntu/Debian (GNOME/KDE):** 1,500 screenshots.
- **macOS:** 1,000 screenshots.
- **Android (Mobile UI):** 1,000 screenshots.

### B. Application States
For each OS, capture:
- **Desktop:** Icons, taskbars, start menus.
- **Web Browsers:** Chrome/Firefox with various websites (social media, productivity tools).
- **System Settings:** Control panels, terminal windows, file explorers.
- **Dialogs:** Popups, login screens, error messages.

### C. Visual Conditions
Since Rongle uses physical capture (HDMI-to-CSI), data should include:
- Pixel-perfect screenshots (software-captured) for the "ideal" model.
- Photos of screens taken with the Android "Eye" in various lighting conditions.

---

## 2. Labeling Strategy (The "Gold" Standard)

We use a multi-stage labeling pipeline to ensure accuracy:

### Stage 1: LLM-Assisted Labeling (`llm_labeler.py`)
We use Gemini 2.0 Flash to auto-label the raw screenshots.
- **Classes:** `button`, `input_field`, `icon`, `text_label`, `checkbox`, `dropdown`.
- **Method:** The script sends each image to Gemini with a "Set-of-Mark" prompt, requesting precise bounding boxes.

### Stage 2: Manual Audit
A human (or a more powerful model like Gemini 1.5 Pro) audits 10% of the labels to ensure consistency and correct drift.

### Stage 3: Synthetic Augmentation
We apply the `RandomHDMINoise` transform during training to simulate:
- Compression artifacts.
- HDMI color-space shifts.
- Slight perspective distortion from physical camera mounting.

---

## 3. How to Contribute Data

1.  **Upload:** Place raw images in `data/raw/` directory.
2.  **Label:** Run the labeling script:
    ```bash
    export GEMINI_API_KEY="your_key"
    python -m rng_operator.training.llm_labeler --input data/raw/ --output data/labeled/
    ```
3.  **Verify:** Check the generated JSON files in `data/labeled/`.

---

## 4. Resource & Cost Analysis (2026 Industry Standard)

To achieve production-grade results efficiently, we recommend the following cloud-native approach:

### A. Recommended Datasets (Public)
- **Rico Dataset (Mobile):** 72k Android screens. We will use a curated 2,000-image subset.
- **Enrico (Desktop):** Labeled UI components for hierarchy understanding.
- **Custom Scrapes:** We will supplement with 1,000 screenshots of modern Windows 11 and Ubuntu (GNOME) UI.

### B. Cloud Compute Recommendation
For the fastest iteration, use a specialized GPU cloud provider.

| Provider | GPU Type | Price/hr | Estimated Time | Total Cost |
| :--- | :--- | :--- | :--- | :--- |
| **Lambda Labs** | NVIDIA A10 (24GB) | $0.60 | 4 hours | **$2.40** |
| **RunPod** | NVIDIA RTX 4090 | $0.70 | 3 hours | **$2.10** |
| **AWS (g5.xlarge)** | NVIDIA A10G | $1.00 | 4 hours | **$4.00** |

*Recommendation: **Lambda Labs** for its pre-configured ML environments.*

### C. Labeling Cost (Gemini 2.0 Flash)
Using the `llm_labeler.py` for high-precision bounding box generation.

- **Tokens per Image:** ~258 (Standard High-Res).
- **Dataset Size:** 5,000 images.
- **Total Input Tokens:** 1.29 Million.
- **Input Price:** $0.10 / 1M tokens.
- **Total Labeling Cost:** **~$0.15**.

---
*Target Metric: >95% Mean Average Precision (mAP) for standard UI elements.*
