# 🛡️ Guardian Shield v2.0

<p align="center">
  <img src="https://img.shields.io/badge/version-2.0.0-00E5FF.svg?style=for-the-badge&logo=shield" alt="Version 2.0.0" />
  <img src="https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-38BDF8.svg?style=for-the-badge&logo=python" alt="Python" />
  <img src="https://img.shields.io/badge/license-MIT-10B981.svg?style=for-the-badge" alt="License MIT" />
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20Linux-F59E0B.svg?style=for-the-badge&logo=windows" alt="Platform" />
  <img src="https://img.shields.io/badge/tests-18%20passed-success.svg?style=for-the-badge" alt="Tests" />
</p>

<p align="center">
  <strong>Enterprise-Grade Shoulder-Surfing Detection & Active Privacy Viewport Protection</strong><br>
  <em>Protect sensitive screen contents from eavesdroppers, coffee shop onlookers, and unauthorized glances in real-time.</em>
</p>

---

## 📖 Table of Contents
- [Overview](#-overview)
- [Key Features](#-key-features)
- [How It Works](#-how-it-works)
- [Architecture & Event Pipeline](#-architecture--event-pipeline)
- [System Requirements](#-system-requirements)
- [Quick Start](#-quick-start)
- [Desktop Control Center (GUI)](#-desktop-control-center-gui)
- [Global Keyboard Shortcuts](#-global-keyboard-shortcuts)
- [CLI Reference](#-cli-reference)
- [How to Upload & Deploy to GitHub](#-how-to-upload--deploy-to-github)
- [Privacy & Security Guarantees](#-privacy--security-guarantees)
- [License](#-license)

---

## 🔍 Overview

In cafes, airports, coworking spaces, and financial trading floors, sensitive passwords, source code, and confidential documents are vulnerable to **shoulder-surfing** (visual eavesdropping).

**Guardian Shield v2.0** turns your standard laptop or USB webcam into an autonomous computer vision security sentry:
1. It continuously monitors the environment in front of your display at a lightweight, throttled capture rate (default **8 FPS**, consuming < 2% CPU).
2. It auto-fingerprints and recognizes you as the **Primary Device Owner** and ignores you.
3. When a **second person** enters the camera view or looks over your shoulder, it immediately alerts you with an on-screen HUD, flashing edge glow, and audible voice alert: *"Warning, peeper detected!"*.
4. With a single click or hotkey (`Ctrl+Shift+D`), it instantly obscures your display using **Gaussian Blur**, **Privacy Dim**, **Mosaic Pixelation**, or a **Decoy Spreadsheet**, unlocking in under 30 milliseconds via `Ctrl+Shift+U`.

---

## 🌟 Key Features

### 👁️ Scene-Aware Face & Gaze Tracking
- **Single-Owner Enforcement**: Exactly one person is recognized as the Primary User. Any secondary person entering the camera frame is strictly categorized as an `UNAUTHORIZED_PEEPER`.
- **Screen-Directed Gaze Tracking**: Distinguishes between innocent bystanders looking away versus onlookers staring directly at your monitor.
- **Passerby Filtering**: People walking by in the background without looking at your screen will not trigger false alarms.
- **Biometric Cosine Distance Whitelist**: Strict 0.18 tolerance prevents strangers from matching trusted profiles.

### 🚨 Dual-Layer Active Alert System
- **Central HUD Card**: Prominently displayed 480x200 card with countdown progress bar and one-click actions:
  - `[🛡️ Deploy Shield]` (Hotkey: `Ctrl+Shift+D`)
  - `[✕ Dismiss]`
  - `[➕ Whitelist Colleague]`
- **Screen-Edge Ambient Glow**: Flashes an amber, red, or pulsing crimson border along all 4 screen edges for immediate peripheral awareness.
- **Audible Warning & Speech Synthesis**: Audibly announces *"Warning, peeper detected!"* via native Windows Speech Synthesizer (`System.Speech`) alongside a warning chime.

### 🛡️ Instant Viewport Obscurity (< 30ms)
- **Gaussian Blur (`blur`)**: Smooth 35px radius blur obscuring live desktop contents.
- **Privacy Dim (`dim`)**: Dark 92% tint screen overlay.
- **Mosaic Pixelate (`mosaic`)**: Retro pixelated privacy block filter.
- **Decoy Spreadsheet (`decoy`)**: Convincing mock logistics spreadsheet document.
- **Zero-Friction Unlock**: Instant unlock via `Ctrl+Shift+U`, double-click, or central button.

### 🛑 Background Process Management
- **In-App Turn Off**: Dedicated `[🛑 Turn Off App (Exit)]` buttons in both the Sidebar and Dashboard header.
- **Smart Window Close (`[X]`)**: Prompts you to either keep monitoring in the system tray or turn off all background tasks completely.

---

## 🏗️ Architecture & Event Pipeline

Guardian Shield utilizes an asynchronous, decoupled **Publish-Subscribe EventBus**:

```
 ┌─────────────────┐
 │  CameraManager  │  (DirectShow / MSMF / Simulation fallback)
 └────────┬────────┘
          ▼
 ┌─────────────────┐
 │  FaceDetector   │  (Multi-backend: Haar, YuNet, Skin-Geometry)
 └────────┬────────┘
          ▼
 ┌─────────────────┐
 │ FaceRecognizer  │  (Strict Scene Classifier: Single Primary Owner)
 └────────┬────────┘
          ▼
 ┌─────────────────┐
 │  GazeAnalyzer   │  (Iris centroid displacement & head orientation)
 └────────┬────────┘
          ▼
 ┌─────────────────┐
 │ThreatClassifier │  (Weighted scoring: Gaze + Proximity + Count + Dwell)
 └────────┬────────┘
          ▼
 ┌─────────────────┐
 │    EventBus     │  (Decoupled PubSub Architecture)
 └────────┬────────┘
          ├──────────────────────────────┬──────────────────────────────┐
          ▼                              ▼                              ▼
 ┌─────────────────┐            ┌─────────────────┐            ┌─────────────────┐
 │ToastNotification│            │  ShieldOverlay  │            │   AuditLogger   │
 │(HUD Card & Glow)│            │ (Blur/Dim/Decoy)│            │(SQLite Database)│
 └─────────────────┘            └─────────────────┘            └─────────────────┘
```

---

## 💻 System Requirements

- **Operating System**: Windows 10 / Windows 11 (or Linux with X11/Xvfb)
- **Python**: Version 3.9, 3.10, 3.11, or 3.12
- **Hardware**: Any built-in or external USB webcam

---

## 🚀 Quick Start

### 1. Clone or Download the Repository
```bash
git clone https://github.com/your-username/guardian-shield.git
cd guardian-shield
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Launch Guardian Shield

- **Option A (One-Click Launcher)**: Double-click `run_guardian.bat`.
- **Option B (Command Line)**:
  ```bash
  python main.py
  ```
- **Option C (Simulation Stream — No Camera Required)**:
  ```bash
  python main.py --simulate
  ```

---

## 🖥️ Desktop Control Center (GUI)

The desktop window provides a dark glassmorphic cybersecurity dashboard:

1. **📊 Dashboard (Tab 0)**:
   - **Live Vision Mini Monitor**: View real-time video and bounding boxes without switching tabs.
   - **Protection Status Hero Card**: Shows live protection state with Pause / Resume and Deploy Shield controls.
   - **Key Metrics**: Live Threat Level, Detected Peepers counter, Total Alerts, and Shield Deployments.
   - **Recent Activity Feed**: Real-time log of security events.
2. **📷 Live Camera Feed (Tab 1)**:
   - **Camera Scanner**: Auto-detects connected webcams with a single click.
   - **Simulation Mode Switch**: Toggle between real webcam and test scenario stream.
   - **Face Enrollment**: 1-click buttons to enroll yourself as Primary Owner or whitelist a colleague.
3. **⚙️ Shield Settings (Tab 2)**:
   - Customize shield style (Blur, Dim, Mosaic, Decoy).
   - Set notification popup position (`center`, `bottom-right`, `top-right`, `bottom-left`).
   - Enable Auto-Shield mode and Session Lock on critical threats.
4. **👥 Trusted Faces (Tab 3)**:
   - Manage whitelisted colleagues and remove profiles.
5. **📋 Audit History (Tab 4)**:
   - Full SQLite event audit trail with search filter, CSV export, and clear logs.

---

## ⌨️ Global Keyboard Shortcuts

| Shortcut | Action | Description |
| :--- | :--- | :--- |
| `Ctrl+Shift+D` | **Deploy Shield** | Instantly obscures the screen with your chosen privacy style. |
| `Ctrl+Shift+U` | **Instant Unlock** | Immediately dismisses the privacy shield. |
| `Ctrl+Shift+P` | **Pause / Resume** | Toggles monitoring on or off globally. |

*Shortcuts are registered via global system hooks and work even when Guardian Shield is not the focused window.*

---

## 🛠️ CLI Reference

```
usage: main.py [-h] [--version] [--simulate] [--auto-shield] [--style {blur,dim,mosaic,decoy}]
               [--fps FPS] [--config CONFIG] [--headless]

Guardian Shield v2.0.0 — Shoulder-Surfing Detection & Privacy Protection

options:
  -h, --help            Show this help message and exit
  -v, --version         Show program's version number and exit
  --simulate            Run in simulation mode using synthetic camera frames
  --auto-shield         Enable Auto-Shield mode (instantly blurs screen on high threat)
  --style {blur,dim,mosaic,decoy}
                        Default shield visual style
  --fps FPS             Throttled frame rate limit for camera capture (default: 8)
  --config CONFIG       Path to custom settings.yaml file
  --headless            Run in console-only mode without desktop GUI overlay
```

---

## 🌐 How to Upload & Deploy to GitHub

Follow these simple steps to push Guardian Shield to your GitHub account:

### Method 1: Using Git Command Line (Recommended)

#### Step 1: Install Git (if not already installed)
Open PowerShell and run:
```powershell
winget install --id Git.Git -e --source winget
```
*(Restart your terminal after installation completes).*

#### Step 2: Initialize Git and Commit Your Code
Inside the project folder (`p1`):
```bash
git init
git add .
git commit -m "feat: initial commit for Guardian Shield v2.0.0 release"
```

#### Step 3: Create a New Repository on GitHub
1. Go to [github.com/new](https://github.com/new).
2. Enter the repository name: `guardian-shield`.
3. Choose **Public** (or Private).
4. Do **NOT** check "Initialize this repository with a README" (we already have a pristine README).
5. Click **Create repository**.

#### Step 4: Link Remote and Push
Copy your repository URL from GitHub and run:
```bash
git branch -M main
git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/guardian-shield.git
git push -u origin main
```

---

### Method 2: Using GitHub Desktop (Graphical Interface)

1. Download and install [GitHub Desktop](https://desktop.github.com/).
2. Click **File** > **Add Local Repository...**.
3. Select your project folder (`c:\Users\shrut\Desktop\p1`).
4. Click **Create a repository** if prompted.
5. Click **Publish repository** to push it directly to your GitHub account!

---

### Method 3: Using GitHub Web Interface (Direct Upload)

1. Create a new repository on [github.com/new](https://github.com/new).
2. Click the **"uploading an existing file"** link.
3. Drag and drop the files from the project folder (or upload `guardian-shield.zip`).
4. Commit your changes.

---

## 🔒 Privacy & Security Guarantees

- **100% On-Device Processing**: Guardian Shield never uploads video frames, facial imagery, or telemetry to the cloud. All computation occurs locally using OpenCV.
- **Biometric Privacy**: Faces are represented in memory as non-invertible 256-dimensional feature embeddings. Raw camera frames are never saved to disk.
- **Local SQLite Store**: Security audit logs are persisted exclusively in a local SQLite file (`guardian_audit.db`), which can be reviewed, exported to CSV, or cleared anytime from the UI.

---

## 📜 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
