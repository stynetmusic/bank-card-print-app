# Handoff for Alex (and agent) — UF Print / bank-card-print-app

**Date:** 2026-07-27  
**Author side:** Paul (`dancingteeth`) + Cursor agent  
**Repo:** https://github.com/stynetmusic/bank-card-print-app  
**Branch:** `modular-refactor-plus-build-fixes`  
**PR:** https://github.com/stynetmusic/bank-card-print-app/pull/1  

Do **not** merge to `main` until a Win7 x64 smoke test of the CI artifact passes.

---

## 1. Goal / product constraint

| Item | Decision |
|------|----------|
| Minimum OS | **Windows 7 SP1 x64** |
| Majority of customers | Win10/11 — same artifact should run there |
| Build machine | **GitHub Actions only** (Windows runner). **Never** PyInstaller on Mac |
| Ship format | **onedir** folder `UF_Print_Cards_App/` = `.exe` + `_internal/` (whole folder) |

---

## 2. What was wrong (root causes of customer EXE failures)

Customer screenshots showed **several different failures** from **inconsistent build recipes**, not one bug:

| Symptom | Likely cause |
|---------|----------------|
| `GetSystemTimePreciseAsFileTime` / `KERNEL32.dll` | Too-new Python/PyInstaller (API is Win8+). Hits **Win7**. |
| `DLL load failed … QtWidgets` / «Не найдена указанная процедура» | Qt/PyQt ABI mismatch — often **PyQt6** or mixed Qt on Win7 |
| «Невозможно запустить это приложение на вашем ПК» | Wrong arch / incomplete package / non-Windows binary |
| Builds “compiled on Mac” | PyInstaller **does not cross-compile**. Mac ≠ Windows PE |

### Repo mishmash (before this PR)

- App + `build.spec` + `requirements.txt` → **PyQt5** + `pyinstaller==4.10`
- `build-win7.yml` installed **PyQt6** + PyInstaller **5.13**, then ran **PyQt5** `build.spec`
- `main.spec` was a **PyQt6** fork of the same app
- README / `WINDOWS_BUILD_GUIDE.md` still told people to use **PyQt6** / Python **3.11**
- CI used `windows-2019` → **GitHub retired that runner (2025-06-30)** → jobs sat forever on *“Waiting for a runner…”*

`dist/` / `build/` are **PyInstaller outputs**. Not required from a collaborator machine; CI recreates them. Do not expect them in git.

---

## 3. What we changed on this branch

### 3.1 Build / CI (priority for shipping)

- Single workflow: `.github/workflows/build.yml`
  - Runner: **`windows-2022`** (2019 is gone)
  - Python: **3.8.10 x64**
  - Deps: **`pip install -r requirements.txt`** only
  - Spec: **`build.spec`** → artifact `UF_Print_Cards_Windows7_x64`
- Deleted: `.github/workflows/build-win7.yml`, `main.spec` (PyQt6)
- Docs aligned: `README.md`, `WINDOWS_BUILD_GUIDE.md`
- Locked stack in `requirements.txt`:

```text
PyQt5==5.15.4
numpy<1.24.0
Pillow>=10.1.0,<11
reportlab>=3.6.0,<4
pyinstaller==4.10
```

### 3.2 App structure (UCR blockers)

Was one ~1818-line `main.py`. Now:

| Path | Role |
|------|------|
| `main.py` | Thin entry (~57 lines) |
| `ufprint/bootstrap.py` | Logging, VC++ check, Qt DLL paths |
| `ufprint/editor.py` | Image editor widget |
| `ufprint/framing.py` | Pure PIL framing (WYSIWYG) |
| `ufprint/orders.py` | SQLite orders |
| `ufprint/company_config.py` | Org JSON |
| `ufprint/pdf_export.py` | Print PDF + КП |
| `ufprint/app_window.py` | Main window |
| `ufprint/styles.py` | QSS |
| `tests/` | Pure unit tests (no GUI) |
| `requirements-dev.txt` | `pytest` |

### 3.3 Product fix: preview = export

PDF print and КП now use **`get_framed_image()`** (respects move/zoom), not raw `get_image()`. Empty areas use a **white** letterbox for print.

Also: `active_editors()`, `capture_state()`, shared `erase_at()`, hard-fail on failed PyQt import.

---

## 4. Current CI status (as of handoff write-up)

1. First PR run stuck forever on `windows-2019` → cancelled.  
2. Switched to `windows-2022` → run started.  
3. That run **failed** at a **post-install sanity check**, not during `pip install`:

```text
AttributeError: module 'PyQt5' has no attribute 'QtCore'
```

Install of PyQt5 5.15.4 / PyInstaller 4.10 **succeeded**. The check used `PyQt5.QtCore` incorrectly; it must be `from PyQt5.QtCore import QT_VERSION_STR` (or `import PyQt5.QtCore`).  

**Agent action:** fix that one line in `build.yml`, push, re-run Actions, download artifact.

Failed run example: https://github.com/stynetmusic/bank-card-print-app/actions/runs/30266101124  

---

## 5. How Alex should pull and test

```bash
git fetch origin
git checkout modular-refactor-plus-build-fixes
git pull
```

Or use PR #1 on GitHub.

After CI is green:

1. Actions → latest successful **Build Windows 7 x64 EXE**  
2. Download artifact **`UF_Print_Cards_Windows7_x64`**  
3. Unpack **entire** `UF_Print_Cards_App` (exe + `_internal`)  
4. On customer PC: install [VC++ Redistributable x64](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist) if needed  
5. Smoke on **real Win7 x64** (and ideally Win10/11):
   - App starts  
   - Load side A/B  
   - Move/zoom → **Export PDF** / **КП** match canvas  
   - Save order  

**Do not** build Windows EXE on Mac. Edit on Mac; ship CI artifacts (or build on a Windows x64 machine with the same pins).

Local tests (optional, Mac/Linux OK for pure tests):

```bash
pip install -r requirements-dev.txt
# + Pillow/reportlab from requirements.txt as needed
pytest
```

---

## 6. Next priorities (ordered)

### P0 — unblock ship

1. **Fix CI PyQt5 version check** in `.github/workflows/build.yml` (see §4).  
2. **Green Actions build** → publish artifact.  
3. **Win7 x64 smoke test** of that artifact (start + PDF framing).  
4. Only then **merge PR #1 → `main`**.

### P1 — product / reliability (from code review advisories)

5. **CMYK vs eraser:** CMYK rebuilds from `base_image` and wipes eraser work — warn or preserve edits.  
6. **Orders store paths only:** reopen loses edits; persist edited assets or label as path-only.  
7. **Undo:** history mainly on move-release; eraser/CMYK not consistently snapshotted.  
8. **Hygiene:** stop committing `card_printing.db` / huge root `.exe` / sample PDF / AppleDouble `._*` (`.gitignore` started; clean history later if needed).

### P2 — structure / quality

9. Keep growing features **outside** a new god-file; prefer new modules under `ufprint/`.  
10. Add a couple GUI smoke notes for Alex’s agent (manual checklist is enough until Qt is in CI).  
11. Optional later: dual artifacts (Win7-pinned vs modern) — **not needed** until Win7 pins block a required feature.

---

## 7. Rules for Alex’s agent

- Target OS minimum = **Win7 x64**; change pins only with explicit Win7 retest.  
- **One** Qt binding: **PyQt5**. Never reintroduce PyQt6 into Win7 CI/`build.spec`.  
- **One** spec: `build.spec`.  
- Runner label: **`windows-2022`** (or newer supported), never `windows-2019`.  
- Ship **folder**, not lone exe.  
- Prefer fixing CI on this branch over pushing half-broken recipes to `main`.  
- After green CI + Win7 OK → merge PR; tag a release if you use Releases for customer drops.

---

## 8. Quick message you can paste to Alex

> Branch/PR: `modular-refactor-plus-build-fixes` / PR #1.  
> We fixed the PyQt5/PyQt6 + docs mess and the “stuck forever” CI (`windows-2019` is dead → `windows-2022`).  
> App is modularized; PDF export should match move/zoom.  
> Latest CI fail is a bad PyQt import check after a successful pip install — fix that line, rebuild, then test the artifact on Win7 (whole `UF_Print_Cards_App` folder).  
> Full notes: `HANDOFF_FOR_ALEX.md` on the branch. Don’t build the Windows exe on Mac.

---

## 9. File map for agents

```
main.py                          # entry
ufprint/                         # application package
.github/workflows/build.yml      # only Windows build workflow
build.spec                       # PyInstaller onedir
requirements.txt                 # Win7-pinned runtime + bundler
requirements-dev.txt             # pytest
tests/                           # pure unit tests
WINDOWS_BUILD_GUIDE.md           # build rules
HANDOFF_FOR_ALEX.md              # this document
```
