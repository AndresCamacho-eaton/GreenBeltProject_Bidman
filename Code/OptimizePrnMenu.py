"""
    Menú de terminal para optimizar archivos PRN con BidManMaintenanceToolsV1_4_0.

    Uso (desde cualquier carpeta):
        python Code/OptimizePrnMenu.py

    1. Elegir una carpeta con PRNs dentro de ENCLOSC_PRNS (p. ej. PRNS/REALPRODUCT).
    2. Elegir los archivos (1,3,5-8 / all).
    3. Elegir el máximo de valores por OR nuevo (las fusiones más grandes se parten en bloques).
    4. Cada archivo se optimiza en una carpeta de salida (nunca se modifica el original),
       se vuelve a leer y se verifica tabla por tabla contra el original.
    5. Si la carpeta tiene GLOBALS.PRN, sus ORs se usan al optimizar y al verificar, y
       (opcional) los ORs repetidos se dejan una sola vez en un GLOBALS.PRN nuevo en la
       carpeta de salida.

    También corre las pruebas unitarias (test_BidManMaintenanceToolsV1_4_0).
"""

import os
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "ENCLOSC_PRNS"))
OUTPUT_DIR_NAME = "optimized"
GLOBALS_NAME = "GLOBALS.PRN"
DEFAULT_MAX_OR_VALUES = 50

sys.path.insert(0, HERE)
import BidManMaintenanceToolsV1_4_0 as BMMT

# ===================================================================================================

def ask(prompt, default=""):

    suffix = f" [{default}]" if default else ""
    try:
        answer = input(f"{prompt}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    return answer or default

def askYesNo(prompt, default=False):

    answer = ask(f"{prompt} (y/n)", "y" if default else "n").lower()
    return answer.startswith("y") or answer.startswith("s")

# ---------------------------------------------------------------------------------------------------

def parseSelection(text, count):

    # "all", "1,3,5-8" -> índices base 0. Devuelve None si el texto no es válido.
    text = text.strip().lower()
    if text in ("all", "a", "*", "todos"):
        return list(range(count))

    chosen = []
    for part in text.replace(" ", "").split(","):
        if not part:
            continue
        first, dash, last = part.partition("-")
        if not first.isdigit() or (dash and not last.isdigit()):
            return None
        a, b = int(first), int(last) if dash else int(first)
        if not (1 <= a <= b <= count):
            return None
        chosen.extend(i - 1 for i in range(a, b + 1) if i - 1 not in chosen)
    return chosen or None

# ===================================================================================================

def isPrn(name):
    return name.lower().endswith(".prn")

def prnFolders():

    # Carpetas bajo ENCLOSC_PRNS con al menos un .prn (sin las carpetas de salida).
    folders = []
    for path, dirs, files in os.walk(ROOT):
        dirs[:] = sorted(d for d in dirs if d != OUTPUT_DIR_NAME)
        prns = [f for f in files if isPrn(f)]
        if prns:
            folders.append((path, len(prns)))
    return folders

def findGlobals(folder):

    for name in os.listdir(folder):
        if name.upper() == GLOBALS_NAME:
            return os.path.join(folder, name)
    return None

def describe(path):

    # Conteo rápido sin parsear todo el archivo.
    lines = tables = 0
    with open(path, encoding="latin-1") as fh:
        for line in fh:
            lines += 1
            if line.startswith("TABLE TYPE"):
                tables += 1
    return lines, tables

# ===================================================================================================

def chooseFolder():

    folders = prnFolders()
    if not folders:
        print(f"No .prn files found under {ROOT}")
        return None

    print("\nFolders with PRN files:")
    for i, (path, count) in enumerate(folders, 1):
        globalsTag = "  (has GLOBALS.PRN)" if findGlobals(path) else ""
        print(f"  {i}) {os.path.relpath(path, ROOT)}  - {count} files{globalsTag}")

    default = str(len(folders))
    while True:
        choice = parseSelection(ask("Choose a folder", default), len(folders))
        if choice and len(choice) == 1:
            return folders[choice[0]][0]
        print("  Enter one number from the list.")

# ---------------------------------------------------------------------------------------------------

def chooseFiles(folder):

    globalsPath = findGlobals(folder)
    names = sorted((f for f in os.listdir(folder)
                    if isPrn(f) and os.path.isfile(os.path.join(folder, f))
                    and f.upper() != GLOBALS_NAME), key=str.lower)

    print(f"\nFiles in {os.path.relpath(folder, ROOT)}:")
    for i, name in enumerate(names, 1):
        lines, tables = describe(os.path.join(folder, name))
        print(f"  {i:>3}) {name:<32} {lines:>7,} lines {tables:>5} tables")

    if globalsPath:
        ors = len(BMMT.PrnFile(globalsPath).ors)
        print(f"\nGlobal ORs: {os.path.basename(globalsPath)} ({ors} ORs) - used for every file, "
              f"never modified.")
    else:
        print("\nNo GLOBALS.PRN in this folder: only the ORs defined inside each file are known.")

    while True:
        choice = parseSelection(ask("Files to optimize (e.g. 1,3,5-8 or all)"), len(names))
        if choice:
            return ([os.path.join(folder, names[i]) for i in choice], globalsPath,
                    [os.path.join(folder, name) for name in names])
        print("  Invalid selection.")

# ===================================================================================================

def summarize(source, result):

    name = os.path.basename(source)
    if "tables" not in result:
        return {"file": name, "error": result.get("error", "unknown error")}

    tables = result["tables"]
    mismatches = sum(len(m) for _, _, m in result["verification"])
    status = "OK"
    if result.get("error"):
        status = "FAILED: " + result["error"][:60]
    elif mismatches:
        status = "FAILED: behavior changed"
    elif result["inlineLists"]:
        status = "FAILED: INPUT list without OR"

    moved = result.get("consolidation", {})
    return {
        "file": name,
        "status": status,
        "tables": len(tables),
        "before": sum(t["rulesBefore"] for t in tables),
        "after": sum(t["rulesAfter"] for t in tables),
        "newOrs": len(result["newOrs"]),
        "largestOr": result.get("largestNewOr", 0),
        "orsRemoved": sum(len(moved.get(k, [])) for k in
                          ("duplicateLinesRemoved", "sameAsGlobal", "renamedToGlobal",
                           "movedToGlobals")),
        "orConflicts": sum(len(moved.get(k, [])) for k in ("conflictWithGlobal", "conflictInFile")),
        "tests": sum(n for _, n, _ in result["verification"]),
    }

# ---------------------------------------------------------------------------------------------------

def formatSummary(rows, project):

    out = [f"{'File':<28} {'Status':<26} {'Tables':>6} {'Rules before':>12} {'after':>7} "
           f"{'less':>6} {'New ORs':>7} {'Biggest':>7} {'ORs->glob':>9} {'Conflicts':>9} "
           f"{'Tests':>8}"]
    for r in rows:
        if "error" in r:
            out.append(f"{r['file']:<28} ERROR: {r['error']}")
            continue
        less = 100.0 * (r["before"] - r["after"]) / r["before"] if r["before"] else 0.0
        out.append(f"{r['file']:<28} {r['status']:<26} {r['tables']:>6} {r['before']:>12} "
                   f"{r['after']:>7} {less:>5.1f}% {r['newOrs']:>7} {r['largestOr']:>7} "
                   f"{r['orsRemoved']:>9} {r['orConflicts']:>9} {r['tests']:>8}")

    done = [r for r in rows if "error" not in r]
    before = sum(r["before"] for r in done)
    after = sum(r["after"] for r in done)
    ok = sum(1 for r in done if r["status"] == "OK")
    out.append("")
    out.append(f"{ok} of {len(rows)} files OK.  Rules: {before} -> {after}"
               + (f"  ({100.0 * (before - after) / before:.1f}% less)" if before else ""))
    out.append(f"Local OR definitions removed (now only in GLOBALS.PRN): "
               f"{sum(r['orsRemoved'] for r in done)}")
    out.append(f"New global ORs added to GLOBALS.PRN: {len(project['newGlobals'])}")
    if project["globalsOut"]:
        out.append(f"New GLOBALS.PRN: {project['globalsOut']}  (deploy it together with these files)")
    conflicts = sum(r["orConflicts"] for r in done)
    if conflicts:
        out.append(f"{conflicts} ORs need review (same name, different values) - "
                   f"see REVISAR in the per-file reports.")
    return "\n".join(out)

# ---------------------------------------------------------------------------------------------------

def askNumber(prompt, default):

    while True:
        answer = ask(prompt, str(default))
        if answer.isdigit() and int(answer) >= 2:
            return int(answer)
        print("  Enter a whole number of 2 or more.")

# ---------------------------------------------------------------------------------------------------

def optimizeFlow():

    folder = chooseFolder()
    if folder is None:
        return

    files, globalsPath, projectFiles = chooseFiles(folder)

    maxOrValues = askNumber("Max values per new OR (bigger merges are split in blocks)",
                            DEFAULT_MAX_OR_VALUES)
    consolidate = bool(globalsPath) and askYesNo(
        "Move repeated ORs to GLOBALS.PRN and remove them from the PRN files?", True)

    outputDir = ask("Output folder", os.path.join(folder, OUTPUT_DIR_NAME))
    outputDir = os.path.abspath(outputDir)
    if os.path.normcase(outputDir) == os.path.normcase(os.path.abspath(folder)):
        print("The output folder cannot be the input folder (the originals would be overwritten).")
        return

    os.makedirs(outputDir, exist_ok=True)
    targets = files + ([globalsPath] if consolidate else [])
    existing = [f for f in targets if os.path.exists(os.path.join(outputDir, os.path.basename(f)))]
    if existing and not askYesNo(f"{len(existing)} files already exist in the output folder. "
                                 f"Overwrite them?"):
        return

    print(f"\nOptimizing {len(files)} files -> {outputDir}\n")
    started = time.time()
    labels = {"optimize": "optimizing", "consolidate": "moving repeated ORs to",
              "verify": "verifying"}

    def progress(stage, name):
        print(f"  {labels[stage]} {name} ...", flush=True)

    project = BMMT.optimizeProject(files, outputDir, globalsPath=globalsPath,
                                   projectPaths=projectFiles, consolidate=consolidate,
                                   progress=progress, maxOrValues=maxOrValues)

    rows = [summarize(path, project["files"][path]) for path in files]

    # Un archivo que no pasó la verificación no debe poder usarse por error.
    for row in rows:
        if row.get("status", "FAILED").startswith("FAILED"):
            target = os.path.join(outputDir, row["file"])
            if os.path.exists(target):
                os.replace(target, target + ".FAILED")

    summary = formatSummary(rows, project)
    summaryPath = os.path.join(outputDir, "summary.txt")
    with open(summaryPath, "w", encoding="utf-8") as fh:
        fh.write(summary + "\n")

    print("\n" + summary)
    print(f"\nTotal time: {time.time() - started:.0f}s")
    print(f"Per-file reports: <file>.report.txt in {outputDir}")
    print(f"Summary saved to {summaryPath}")
    if any(r.get("status", "FAILED") != "OK" for r in rows):
        print("Files that failed were renamed to <file>.FAILED - do not use them.")

# ===================================================================================================

def runTests():

    print("\nRunning unit tests (test_BidManMaintenanceToolsV1_4_0) ...\n")
    suite = unittest.defaultTestLoader.loadTestsFromName("test_BidManMaintenanceToolsV1_4_0")
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return result.wasSuccessful()

# ===================================================================================================

def main():

    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass

    while True:
        print("\n=== BidMan PRN optimizer (V1_4_0) ===")
        print("  1) Optimize PRN files")
        print("  2) Run unit tests")
        print("  3) Run unit tests, then optimize")
        print("  q) Quit")
        choice = ask("Choose", "1").lower()

        if choice == "1":
            optimizeFlow()
        elif choice == "2":
            runTests()
        elif choice == "3":
            if runTests():
                optimizeFlow()
            else:
                print("\nTests failed - not optimizing.")
        elif choice in ("q", "quit", "exit"):
            return

# ---------------------------------------------------------------------------------------------------

if __name__ == "__main__":
    main()
