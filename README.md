# TextAnimator Windows Installer

This repository builds the TextAnimator 3.2.0 Windows x64 installer through GitHub Actions.

The release asset will be a single `TextAnimator-v3.2.0-Setup.exe` installer (not a portable ZIP). It installs per-user under `%LOCALAPPDATA%\\Programs\\TextAnimator`, creates a Start Menu shortcut, offers an optional Desktop shortcut, and preserves user settings/credentials/queue data outside the install directory.

The workflow runs on pushes to `main`. It resolves Windows Python wheels, runs `pip check` and regression tests, bundles the Python runtime and application modules with PyInstaller, creates the Inno Setup installer, then publishes the `.exe` as a GitHub Release asset.
