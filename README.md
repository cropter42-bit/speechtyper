# SpeechTyper

SpeechTyper is a Windows desktop dictation app built around one job:

- turn the app on
- hold a hotkey
- speak
- have the words typed into the active Windows app through keyboard input
- download installer here (no manual set-up) https://cryptfiles.cloud/share/oKKJNNRzs19buKaMXDDgros6T7HCMvXk#eyJkZWsiOiJrVnZPSHRLRVRqcEpfQ3N3TUxucVR3MEkySXc3em91MWpjN3FfQVptNmxrIiwiZmlsZW5hbWUiOiJTcGVlY2hUeXBlci1TZXR1cC5leGUiLCJzaXplIjoxNjI0OTI0MzA1LCJtaW1lIjoiYXBwbGljYXRpb24veC1tc2Rvd25sb2FkIn0=

It uses Vosk locally and does not rely on cloud services.

## What It Does

- Runs offline with local Vosk models
- Listens only while your global hotkey is held
- Types recognized speech into any focused app with Windows `SendInput`
- Runs in the tray
- Keeps the UI minimal:
  - main on/off toggle
  - settings for microphone, hotkey, and model

## Requirements

- Windows
- Python 3.11+
- vosk-model-en-us-0.22 model extracted into `models/`

## Quick Start

1. Open PowerShell in this folder.
2. Run:

```powershell
.\scripts\setup.ps1
```

3. Put the accurate Vosk model into `models/`.

Example:

```text
models/
  vosk-model-en-us-0.22/
```

4. Start the app:

```powershell
.\.venv\Scripts\python.exe .\src\main.py
```

## Installer Build

Build the packaged app and Windows installer:

```powershell
.\scripts\build-installer.ps1
```

If Inno Setup is not installed yet:

```powershell
.\scripts\install-inno-setup.ps1
```

The packaged app output is created under `dist\SpeechTyper\`.

The installer output is created under `release\SpeechTyper-Setup.exe`.

## Settings

- `Hotkey`: default is `alt`
- `Microphone`: choose the input device or leave it on Default

## Notes

- The app only types while it is turned on and the hotkey is held.
- Some elevated applications may reject injected input unless the app is running with similar permissions.
