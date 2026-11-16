<h1><picture><source media="(prefers-color-scheme: dark)" srcset="assets/brand/hamartia-mark-light.svg"><img src="docs/assets/hamartia-favicon.svg" width="28" height="28" alt=""></picture> Hamartia</h1>

**Turn missed questions into a steady practice and review loop.** Hamartia is a local-first desktop study tool for learners across curricula. Record exams and questions, see patterns in saved mistakes, and plan focused practice without an AI provider.

[**Read the user guide**](https://nec0ti.github.io/hamartia/) · [Download the latest release](https://github.com/Nec0ti/hamartia/releases/latest) · [Browse the source](https://github.com/Nec0ti/hamartia)

The guide is available in English and Turkish.

## What you can do

| Area | Guide |
| --- | --- |
| Exams, missed questions, practice, and review | [Study workflows](https://nec0ti.github.io/hamartia/study-workflows/) |
| Supported formats, scoring profiles, and curriculum references | [Exam formats and Maarif](https://nec0ti.github.io/hamartia/exam-formats-and-maarif/) |
| Local records and optional provider requests | [Privacy and consent](https://nec0ti.github.io/hamartia/privacy-and-consent/) |
| Create, move, and restore a backup | [Backup and restore](https://nec0ti.github.io/hamartia/backup-and-restore/) |

The built-in full-mock formats are TYT/AYT. Single-subject exams and topic practice are generic; scoring rules can be selected or defined as versioned profiles. User-entered profiles and curriculum references do not claim official alignment.

## Download and install

Get the current package from [GitHub Releases](https://github.com/Nec0ti/hamartia/releases/latest): Windows installer for Windows 10/11, `.deb` for Debian-based Linux, or AppImage for compatible Linux desktops. See the [installation guide](https://nec0ti.github.io/hamartia/install/) for platform steps.

## Run from source

Python 3.12 and Node.js 22 are required.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
cd frontend && npm ci && cd ..
.venv/bin/python scripts/dev.py
```

The local interface opens at `http://127.0.0.1:5173`. Press Ctrl+C to stop both services. See [Contributing](https://nec0ti.github.io/hamartia/contributing/) before changing the project.

## Your data and AI

Study records and question images stay in this OS user's local application-data folder. Hamartia does not sync them between computers; create a ZIP backup in Settings when moving data. Backups exclude configured API keys and ChatGPT sign-in credentials.

AI is optional. The Study Agent and question analysis are separate features. If enabled, they send data to the provider you select after a consent step; a configured OpenAI-compatible endpoint can be remote. Read [Privacy and consent](https://nec0ti.github.io/hamartia/privacy-and-consent/) and [Study Agent and providers](https://nec0ti.github.io/hamartia/study-agent/) before enabling them. No real model execution is part of automated tests or benchmarks.

## Project

Hamartia is original software under the [MIT License](LICENSE). The [backlog](backlog.md) tracks planned work and outstanding manual checks. Contributions and forks are welcome; start with the [contribution guide](https://nec0ti.github.io/hamartia/contributing/).
