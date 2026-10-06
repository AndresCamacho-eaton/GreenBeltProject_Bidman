# BidMan Pick Optimizer

> **In one sentence:** it makes BidMan PRN files **much smaller** (about 70% fewer rules) **without changing what they do**, and it proves that by testing every file.

---

## ⚡ Quick start (2 minutes)

**Double-click `BidMan Pick Optimizer.exe`.** No Python or installation needed.

1. Choose **`1`** (Optimize PRN files).
2. Choose the **folder**, for example `Products\ENCLOSC\PRNS`. Type **`o`** to paste any other folder path.
3. Type **`all`**, or pick files such as `1,3,5-8`.
4. Check the yellow list of **excluded files and tables**. Type `y` if you want to exclude more.
5. Press **Enter** to accept each default.
6. Your results go to **`Documents\BidMan Pick Optimizer\<product>\<folder>`**. Your original files are **never changed**.

✅ Green `OK` = the file is safe to use.  ❌ Red `FAILED` = don't use it (it's renamed to `.FAILED`).

The app lists the PRN folders under `C:\EG.BidManager\Dev\Dev\Src\Takeoffs\GTO\GTO.Web\Products`.

> Developers can also run it from source: `python Code\OptimizePrnMenu.py` (Python 3.10+, no extra packages). That version also has the unit-test options.

---

## 🤔 What does it do?

PRN tables often have many rules that differ in **only one value**. The tool merges them into **one rule** that uses an **OR** (a named list of values).

**Before** (3 rules):
```
R       tbl         F1    2     N1    100
R       tbl         F2    2     N1    100
R       tbl         F3    2     N1    100
```

**After** (1 rule plus 1 OR):
```
DEFINE OR:OR:frame_F1_F2_F3=F1;F2;F3
R       tbl         OR:frame_F1_F2_F3  2     N1    100
```

It also:

| What | Why |
|---|---|
| 🗑️ Removes rules that can **never win** (an earlier rule with the same result already covers them) | Less clutter |
| 🌍 Moves **ORs repeated in several files** into `GLOBALS.PRN`, once | Edit a list in one place, not in 10 |
| ✂️ Splits **huge ORs** into blocks (50 values max by default) | Keeps the files readable |

---

## 🛡️ Why it's safe

| Guarantee | How |
|---|---|
| Original files are never touched | Output always goes to a separate folder, and the tool refuses to write into the input folder |
| Behavior is the same | Every table is re-read and **tested with thousands of inputs** against the original |
| OUTPUT values are never modified | Checked character by character (`@` defaults and `a;b` pick lists stay exactly as written) |
| No lists inside INPUT cells | Every list must be a `DEFINE OR`. Checked on every file |
| A file that fails can't be used by mistake | It's renamed to `<file>.FAILED` |

---

## 🚫 Excluded files and tables

Some files and tables are **never optimized**. The menu lists them in yellow before every run, and they appear again in the summary.

| Always excluded | |
|---|---|
| **Files** | `PluginFramework.prn`, `REEVAL.PRN`, `SAVEITEMS.PRN`, `PRICEINFO.PRN`, `SummaryInfo.prn`, `UpgradeRevision.prn` |
| **Tables** (in whichever file they appear) | `GTO_Dictionary`, `AttrTabAssign`, `SetFeatures`, `PreConfigureActions` |

- Uppercase or lowercase doesn't matter (`reeval.prn` = `REEVAL.PRN`).
- **Excluded files** are **copied unchanged** into the output folder. They're also re-tested with the new `GLOBALS.PRN` to prove it doesn't change them.
- **Excluded tables** are copied **exactly as they are**. Their ORs are never renamed.
- **To exclude more in one run:** answer `y` to *"Exclude more files or tables from this run?"* and pick file numbers or type table names. Type `?` to list the table names.
- **To exclude more permanently:** add the names to `EXCLUDED_FILES` / `EXCLUDED_TABLES` at the top of `Code/OptimizePrnMenu.py`.

---

## 📏 The rules it follows

1. **INPUT cells never contain `value;value`.** Lists must be declared with `DEFINE OR:name=...`.
2. **OUTPUT cells are never changed** and never use OR names. Text there is always a plain value.
3. **OR scope:** each file sees **its own ORs plus `GLOBALS.PRN`**. Files can't see each other's ORs.
4. **Lookup order:** the file's own OR first, then the global one. Reusing a global name inside a file is **not recommended** (it can cause bugs), so the tool never creates one.
5. **Only names written by a person become global.** Names the optimizer made up stay local.
6. **Suspicious rules are reported, never deleted** (for example, a rule with the same inputs as an earlier one but a different output).

---

## 📂 What you get in the output folder

| File | What it is |
|---|---|
| `<file>.prn` | The optimized file |
| `<file>.prn.report.txt` | Details for that file (in Spanish, see below) |
| `GLOBALS.PRN` | Always there: the **new** one if this run added global ORs, otherwise the original, copied unchanged. ⚠️ Deploy it **together with** the other files |
| `summary.txt` | One line per file plus totals |
| `<file>.prn.FAILED` | A file that didn't pass verification. **Don't use it.** The original is copied next to it |
| Files that weren't optimized + `.PIK` + `.XML` | **Copied unchanged**, so the folder is a complete set ready to deploy |

---

## 📊 Reading the summary

| Column | Meaning |
|---|---|
| **Status** | `OK`, or why it failed |
| **Rules before / after / less** | How much smaller the file got |
| **New ORs** | ORs the optimizer created |
| **Biggest** | Size of the largest new OR |
| **ORs->glob** | Local ORs removed because they now live in `GLOBALS.PRN` |
| **Conflicts** | 🟡 Problems in the **original** files that need a person (see below) |
| **Tests** | How many inputs were tested |

### 🟡 What "Conflicts" means

These are **not** optimizer errors. The file still passed. They're problems that were **already in your original files**, so the tool leaves them alone:

- **A local OR has the same name as a global OR but different values.** BidMan uses the local one, which is easy to get wrong.
  Example: `ReducedVolts` has `Wye Delta (Closed)` in one file and `Wye Delta(Closed)` in `GLOBALS.PRN`.
- **The same OR is defined twice in one file with different values.**
  Example: `ECO_Motor_Voltage_CAN` in `CTO.PRN`.

👉 Search for **`REVISAR`** in the `.report.txt` files to find them. Fix them in the source files: rename the OR, merge the values, or fix the typo.

### Words to look for in the reports

| Word | Meaning |
|---|---|
| `ERROR` | Something is wrong with the output. The file is marked `FAILED` |
| `REVISAR` | "Review": a person needs to decide something |
| `AVISO` | "Notice": for your information |

---

## 📈 Last full run (real product, 39 files + 6 excluded)

- ✅ **39 of 39 files OK**, 0 behavior differences, 0 changed OUTPUT cells
- 📉 **176,928 → 49,138 rules** (72% fewer)
- 🌍 3,813 repeated OR definitions removed, 264 new global ORs
- ⏱️ About 2–4 minutes

---

## 🧰 Menu options

| Option | What it does |
|---|---|
| `1` | Optimize PRN files |
| `2` | Run the unit tests (only when run from source) |
| `3` | Run the tests, then optimize (only when run from source) |
| `q` | Quit |

While a file is being optimized or checked, a line shows the current table, e.g. `working on table GTO_Dictionary  2/12`. It updates in place and disappears when the file is done.

Colors and the table line only show in a real terminal. To turn them off, set the `NO_COLOR` environment variable.

---

## 🗂️ Project files (for developers)

| File | What it is |
|---|---|
| `Code/OptimizePrnMenu.py` | The menu (start here) |
| `Code/app_info.py` | App name, version, author, contact and copyright (used everywhere) |
| `RELEASES.md` | Every build with its date and SHA-256 fingerprint (written by `build_exe.py`) |
| `Code/welcome_art.py` | The ASCII runner shown when the app opens (`ART` + a color map `COLORS`). Edit it by hand |
| `Code/build_exe.py` | Builds `dist/BidMan Pick Optimizer.exe` |
| `Code/BidManMaintenanceToolsV1_4_0.py` | The engine: read, optimize, verify, write |
| `Code/test_BidManMaintenanceToolsV1_4_0.py` | Unit tests (`python -m unittest test_BidManMaintenanceToolsV1_4_0`, from `Code`) |
| `ENCLOSC_PRNS/PRNS/REALPRODUCT/` | Real product files and `GLOBALS.PRN` |
| `SESSION_HANDOFF.md` | Detailed technical notes and open items |

**Building the `.exe`** (after changing the code or the icon):
```
.\venv\Scripts\python.exe -m pip install pyinstaller pillow     (once)
.\venv\Scripts\python.exe Code\build_exe.py [path\to\icon.ico|.png|.jpg]
```
The result is `dist\BidMan Pick Optimizer.exe`, one file you can share. The icon is saved as `Code\app_icon.ico` and reused on the next build. The app name, version, author and contact are in `Code/app_info.py`. Each build adds a line with its SHA-256 fingerprint to `RELEASES.md`.

**Using it from Python:**
```python
import BidManMaintenanceToolsV1_4_0 as BMMT
BMMT.optimizeProject(files, outputDir, globalsPath="GLOBALS.PRN", projectPaths=files, maxOrValues=50)
```

---

## 👤 Author

Created by **Andrés J. Camacho** ([andresjcamacho@eaton.com](mailto:andresjcamacho@eaton.com)) as a Green Belt project. © 2026 Eaton.

**Special thanks** to **Edgardo R. Medrano** for his help getting this project started.

The author's name is in the app's welcome screen and **About** option, in the `.exe` properties (right-click → Properties → Details), and on the first line of every report and `summary.txt`.

To check that a copy of the app is an official build, run `Get-FileHash "BidMan Pick Optimizer.exe"` in PowerShell and compare the hash with [`RELEASES.md`](RELEASES.md).

---

## ❓ FAQ

**Can it break my PRN files?**
No. It never writes over the originals, and every output is tested against its original. If anything differs, the file is marked `FAILED`.

**Do I have to deploy the new `GLOBALS.PRN`?**
Yes, if it was created. The optimized files rely on the ORs that were moved there.

**Why are some tables skipped?**
Either they're on the exclusion list (see above), or their rows don't line up with the `HEADING` columns (a value spills into the next column) are left untouched on purpose, because the tool can't read them with certainty.

**Why does a file still have repeated ORs?**
They're only moved to `GLOBALS.PRN` when a person-written name fits safely. Otherwise they stay local, which is safe, and the report says so.
