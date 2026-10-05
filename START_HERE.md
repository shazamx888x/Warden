# Start here: building Warden step by step

This copy of the project starts with all eight Warden controls **switched off**.
You switch them on yourself, one chapter at a time, so the demo in chapter 5
and the demo in chapter 13 show different results.

## 1. Put this version in your project folder

Copy everything in this `Warden` folder into `D:\Warden`, replacing files when
Windows asks. Your `.venv` folder is left alone, so you don't need to reinstall.

## 2. Follow the guide

The updated guide is `docs/Warden_Build_Guide.docx` (PDF copy in `assets/`).
In short, from the project folder in Git Bash:

| Chapter | Do this |
|---|---|
| 5  | `python -m warden.demo`: attacks land, **0 of 8** controls built |
| 7  | `cp -r chapter_files/ch07/. .` then run the two checks below (W1, W2) |
| 8  | `cp -r chapter_files/ch08/. .` (W3) |
| 9  | `cp -r chapter_files/ch09/. .` (W4) |
| 10 | `cp -r chapter_files/ch10/. .` (W5) |
| 11 | `cp -r chapter_files/ch11/. .` (W6, W7) |
| 12 | `cp -r chapter_files/ch12/. .` (W8): **8 of 8** |
| 13 | `python -m pytest tests -q` and `python -m warden.demo`: every attack stopped |

The two checks to run after every copy:

    python -m pytest tests/test_build_steps.py -v
    python -m warden.demo

Copy the chapter folders **in order**, and don't skip one.

## 3. If you want to start over

Copy the starter files back in from this zip (`src/warden/gateway/*.py` and
`src/warden/policy/tool_policy.py`), and you're back at 0 of 8.
