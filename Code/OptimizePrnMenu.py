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
import shutil
import sys
import time
import unittest

# True cuando corre como .exe (PyInstaller): sin pruebas unitarias en el menú.
FROZEN = getattr(sys, "frozen", False)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
# Nombre, versión, autor y contacto: se cambian en app_info.py.
from app_info import (APP_NAME, APP_VERSION, AUTHOR, AUTHOR_EMAIL, COPYRIGHT, REPOSITORY,
                      SIGNATURE, SPECIAL_THANKS)
# Carpetas donde se buscan PRNs. La de Products es la de BidMan; la del proyecto solo existe
# al correr desde el código fuente. En el menú también se puede pegar cualquier otra carpeta.
PRODUCTS_ROOT = r"C:\EG.BidManager\Dev\Dev\Src\Takeoffs\GTO\GTO.Web\Products"
PROJECT_ROOT = os.path.normpath(os.path.join(HERE, "..", "ENCLOSC_PRNS"))
ROOTS = (PRODUCTS_ROOT,) if FROZEN else (PRODUCTS_ROOT, PROJECT_ROOT)
OUTPUT_DIR_NAME = "optimized"
GLOBALS_NAME = "GLOBALS.PRN"
DEFAULT_MAX_OR_VALUES = 50

# Archivos y tablas que nunca se optimizan (no distingue mayúsculas). Un archivo excluido no se
# escribe en la carpeta de salida (se sigue usando el original), pero se revisa para que los
# ORs globales nuevos no lo afecten. Una tabla excluida queda exactamente igual. Para excluir
# algo siempre, agregarlo aquí; en el menú se pueden excluir más archivos o tablas por corrida.
EXCLUDED_FILES = ("PluginFramework.prn", "REEVAL.PRN", "SAVEITEMS.PRN", "PRICEINFO.PRN",
                  "SummaryInfo.prn", "UpgradeRevision.prn")
EXCLUDED_TABLES = ("GTO_Dictionary", "AttrTabAssign", "SetFeatures", "PreConfigureActions")
# Otros archivos de la carpeta que se copian sin cambios a la carpeta de salida.
COPY_EXTENSIONS = (".pik", ".xml")

import BidManMaintenanceToolsV1_4_0 as BMMT

# ===================================================================================================

# Colores ANSI. Solo se usan en una terminal real (no al redirigir a un archivo, ni con la
# variable de entorno NO_COLOR). summary.txt y los reportes siempre se escriben sin colores.
STYLES = {
    "title": "1;36",    # cian, negrita
    "option": "1;33",   # amarillo, negrita
    "prompt": "1",      # negrita
    "dim": "90",        # gris ("2"/tenue puede quedar invisible en algunas terminales)
    "default": "33",    # amarillo: el valor por defecto de cada pregunta
    "ok": "1;32",       # verde
    "fail": "1;31",     # rojo
    "warn": "33",       # amarillo
    "info": "36",       # cian
    "step": "35",       # magenta
}
useColor = False

def enableColor():

    global useColor
    useColor = sys.stdout.isatty() and "NO_COLOR" not in os.environ
    if useColor and os.name == "nt":
        os.system("")   # activa las secuencias ANSI en la consola de Windows

def paint(text, style):
    return f"\033[{STYLES[style]}m{text}\033[0m" if useColor else text

# ---------------------------------------------------------------------------------------------------

class LiveLine:

    """
        Una línea de estado que se reescribe en el mismo lugar ("working on table X 3/12") y
        se borra al terminar. Solo en una terminal real; al redirigir la salida no se escribe.
    """

    def __init__(self):
        self.width = 0
        self.enabled = sys.stdout.isatty()

    def show(self, text, style="dim"):
        if not self.enabled:
            return
        # Más corta que la terminal: si se parte en dos renglones, "\r" ya no la borra.
        text = text[:shutil.get_terminal_size().columns - 1]
        padding = " " * max(0, self.width - len(text))
        sys.stdout.write("\r" + paint(text, style) + padding)
        sys.stdout.flush()
        self.width = len(text)

    def clear(self):
        if self.width:
            sys.stdout.write("\r" + " " * self.width + "\r")
            sys.stdout.flush()
            self.width = 0

# ---------------------------------------------------------------------------------------------------

def ask(prompt, default=""):

    suffix = " " + paint(f"[{default}]", "default") if default else ""
    try:
        answer = input(f"{paint(prompt, 'prompt')}{suffix}: ").strip()
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

def prnFolders(roots=ROOTS):

    # Carpetas con al menos un .prn bajo cada raíz que exista (sin las carpetas de salida).
    folders = []
    for root in roots:
        for path, dirs, files in os.walk(root):
            dirs[:] = sorted((d for d in dirs if d.lower() != OUTPUT_DIR_NAME), key=str.lower)
            prns = [f for f in files if isPrn(f)]
            if prns:
                folders.append((path, len(prns)))
    return folders

def folderLabel(path):

    # "ENCLOSC\PRNS" para carpetas bajo una raíz conocida; si no, la ruta completa.
    for root in ROOTS:
        try:
            rel = os.path.relpath(path, root)
        except ValueError:      # otra unidad
            continue
        if not rel.startswith(".."):
            return os.path.join(os.path.basename(root), rel) if rel != "." else os.path.basename(root)
    return path

def documentsFolder():

    # Carpeta Documentos real del usuario (puede estar redirigida a OneDrive).
    try:
        import ctypes.wintypes
        buffer = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buffer)   # 5 = CSIDL_PERSONAL
        if buffer.value:
            return buffer.value
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), "Documents")

def defaultOutputDir(folder):

    # Los resultados van a Documentos\<APP_NAME>\<producto>\<carpeta>, fuera del árbol
    # de productos de BidMan, para que nunca se desplieguen o mezclen por error.
    label = folderLabel(folder)
    if os.path.isabs(label):
        label = os.path.basename(folder)
    return os.path.join(documentsFolder(), APP_NAME, label)

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
    if folders:
        print(paint("\nFolders with PRN files:", "title"))
        for i, (path, count) in enumerate(folders, 1):
            globalsTag = paint("  (has GLOBALS.PRN)", "info") if findGlobals(path) else ""
            print(f"  {paint(f'{i:>2})', 'option')} {folderLabel(path)}  "
                  f"{paint(f'- {count} files', 'dim')}{globalsTag}")
    else:
        print(paint(f"\nNo PRN folders found in {', '.join(ROOTS)}", "warn"))
    print(f"  {paint(' o)', 'option')} Other folder (paste its path)")
    print(f"  {paint(' q)', 'option')} Back to the main menu")

    while True:
        answer = ask("Choose a folder")
        if answer.lower() in ("", "q", "quit", "back"):
            return None
        if answer.lower() in ("o", "other"):
            answer = ask("Folder with the PRN files").strip('"')
        if os.path.isdir(answer):
            if any(isPrn(f) for f in os.listdir(answer)):
                return os.path.abspath(answer)
            print(paint("  That folder has no .prn files.", "warn"))
            continue
        choice = parseSelection(answer, len(folders)) if folders else None
        if choice and len(choice) == 1:
            return folders[choice[0]][0]
        print(paint("  Enter one number from the list, o, or a folder path.", "warn"))

# ---------------------------------------------------------------------------------------------------

def chooseFiles(folder):

    globalsPath = findGlobals(folder)
    allNames = sorted((f for f in os.listdir(folder)
                       if isPrn(f) and os.path.isfile(os.path.join(folder, f))
                       and f.upper() != GLOBALS_NAME), key=str.lower)
    excludedFiles = {f.lower() for f in EXCLUDED_FILES}
    skipped = [f for f in allNames if f.lower() in excludedFiles]
    names = [f for f in allNames if f.lower() not in excludedFiles]

    print(paint(f"\nFiles in {folderLabel(folder)}:", "title"))
    for i, name in enumerate(names, 1):
        lines, tables = describe(os.path.join(folder, name))
        print(f"  {paint(f'{i:>3})', 'option')} {name:<32} "
              f"{paint(f'{lines:>7,} lines {tables:>5} tables', 'dim')}")

    if globalsPath:
        ors = len(BMMT.PrnFile(globalsPath).ors)
        print(paint(f"\nGlobal ORs: {os.path.basename(globalsPath)} ({ors} ORs) - used for every "
                    f"file, never modified.", "info"))
    else:
        print(paint("\nNo GLOBALS.PRN in this folder: only the ORs defined inside each file are "
                    "known.", "warn"))

    if skipped:
        print(paint("\nExcluded by default (never optimized, keep using the originals):", "warn"))
        for name in skipped:
            print(paint(f"  - {name}", "warn"))

    # Los archivos excluidos siguen en projectFiles: se revisan para que un OR global nuevo no
    # cambie su significado.
    projectFiles = [os.path.join(folder, name) for name in allNames]
    while True:
        choice = parseSelection(ask("Files to optimize (e.g. 1,3,5-8 or all)"), len(names))
        if choice:
            return [os.path.join(folder, names[i]) for i in choice], globalsPath, projectFiles, skipped
        print(paint("  Invalid selection.", "warn"))

# ---------------------------------------------------------------------------------------------------

def chooseExclusions(files):

    """
        Muestra las tablas excluidas por defecto que hay en los archivos elegidos y deja excluir
        más archivos o tablas en esta corrida. Devuelve (archivos a optimizar, archivos
        excluidos en esta corrida, nombres de tablas excluidas).
    """

    print(paint("\nReading table names ...", "dim"))
    tablesByFile = {path: [t.name for t in BMMT.PrnFile(path).tables if t.name] for path in files}
    allTables = {name.lower(): name for names in tablesByFile.values() for name in names}

    def found(skipTables):
        wanted = {t.lower() for t in skipTables}
        return [(os.path.basename(path), name) for path, names in tablesByFile.items()
                for name in names if name.lower() in wanted]

    skipTables = list(EXCLUDED_TABLES)
    defaults = found(skipTables)
    if defaults:
        print(paint("Tables excluded by default (left exactly as they are):", "warn"))
        for fileName, table in defaults:
            print(paint(f"  - {table}  ({fileName})", "warn"))
    else:
        print(paint("None of the tables excluded by default are in the selected files.", "dim"))

    extraFiles = []
    if not askYesNo("Exclude more files or tables from this run?", False):
        return files, extraFiles, skipTables

    print(paint("\nSelected files:", "title"))
    for i, path in enumerate(files, 1):
        print(f"  {paint(f'{i:>3})', 'option')} {os.path.basename(path)}")
    while True:
        answer = ask("Files to exclude (e.g. 2,5 - Enter for none)")
        if not answer:
            break
        choice = parseSelection(answer, len(files))
        if choice:
            extraFiles = [files[i] for i in choice]
            break
        print(paint("  Invalid selection.", "warn"))
    files = [f for f in files if f not in extraFiles]

    while True:
        answer = ask("Tables to exclude (names separated by commas, ? = list them, Enter for none)")
        if answer == "?":
            for path in files:
                print(f"  {paint(os.path.basename(path), 'info')}: "
                      f"{', '.join(tablesByFile[path]) or '(no tables)'}")
            continue
        names = [n.strip() for n in answer.split(",") if n.strip()]
        unknown = [n for n in names if n.lower() not in allTables]
        if unknown:
            print(paint(f"  Not found in the selected files: {', '.join(unknown)}. "
                        f"Type ? to see the table names.", "warn"))
            continue
        skipTables += [allTables[n.lower()] for n in names]
        break

    if extraFiles:
        print(paint("Also excluded in this run: " +
                    ", ".join(os.path.basename(f) for f in extraFiles), "warn"))
    extraTables = found(skipTables[len(EXCLUDED_TABLES):])
    if extraTables:
        print(paint("Also excluded in this run: " +
                    ", ".join(f"{t} ({f})" for f, t in extraTables), "warn"))
    return files, extraFiles, skipTables

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
    elif result.get("changedOutputs"):
        status = "FAILED: OUTPUT value changed"
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
        "repeatedLocal": len(moved.get("notGlobal", [])),
        "tests": sum(n for _, n, _ in result["verification"]),
        "excludedTables": [t["name"] for t in tables if t["skipped"] == "tabla excluida"],
    }

# ---------------------------------------------------------------------------------------------------

def formatSummary(rows, project, color=False, excludedFiles=(), copied=()):

    # color=True solo para la pantalla; summary.txt se escribe sin colores.
    # excludedFiles: nombres de los archivos que no se optimizaron (por defecto o por elección).
    # copied: [(nombre, problema o None)] de copyUnoptimized.
    def c(text, style):
        return paint(text, style) if color else text

    out = [c(f"{'File':<28} {'Status':<26} {'Tables':>6} {'Rules before':>12} {'after':>7} "
             f"{'less':>6} {'New ORs':>7} {'Biggest':>7} {'ORs->glob':>9} {'Conflicts':>9} "
             f"{'Tests':>8}", "title")]
    for r in rows:
        if "error" in r:
            out.append(f"{r['file']:<28} " + c(f"ERROR: {r['error']}", "fail"))
            continue
        less = 100.0 * (r["before"] - r["after"]) / r["before"] if r["before"] else 0.0
        status = c(f"{r['status']:<26}", "ok" if r["status"] == "OK" else "fail")
        conflicts = c(f"{r['orConflicts']:>9}", "warn") if r["orConflicts"] else f"{0:>9}"
        out.append(f"{r['file']:<28} {status} {r['tables']:>6} {r['before']:>12} "
                   f"{r['after']:>7} {less:>5.1f}% {r['newOrs']:>7} {r['largestOr']:>7} "
                   f"{r['orsRemoved']:>9} {conflicts} {r['tests']:>8}")

    done = [r for r in rows if "error" not in r]
    before = sum(r["before"] for r in done)
    after = sum(r["after"] for r in done)
    ok = sum(1 for r in done if r["status"] == "OK")
    out.append("")
    out.append(c(f"{ok} of {len(rows)} files OK.", "ok" if ok == len(rows) else "fail")
               + f"  Rules: {before} -> {after}"
               + (f"  ({100.0 * (before - after) / before:.1f}% less)" if before else ""))
    out.append(f"Local OR definitions removed (now only in GLOBALS.PRN): "
               f"{sum(r['orsRemoved'] for r in done)}")
    out.append(f"New global ORs added to GLOBALS.PRN: {len(project['newGlobals'])}")
    repeated = sum(r["repeatedLocal"] for r in done)
    if repeated:
        out.append(f"Repeated ORs kept local (no hand-written name fits as a global name): "
                   f"{repeated} - see the per-file reports.")
    if project["globalsOut"]:
        out.append(c(f"New GLOBALS.PRN: {project['globalsOut']}  (deploy it together with these "
                     f"files)", "info"))
    conflicts = sum(r["orConflicts"] for r in done)
    if conflicts:
        out.append(c(f"{conflicts} ORs need review (same name, different values) - "
                     f"see REVISAR in the per-file reports.", "warn"))
    if excludedFiles:
        out.append(c(f"Excluded files (not optimized, copied unchanged): {', '.join(excludedFiles)}",
                     "warn"))
    tables = [f"{t} ({r['file']})" for r in done for t in r["excludedTables"]]
    if tables:
        out.append(c(f"Excluded tables (kept in place, exactly as they were): {', '.join(tables)}",
                     "warn"))
    if copied:
        out.append(c(f"Copied unchanged into the output folder ({len(copied)}): "
                     f"{', '.join(name for name, _ in copied)}", "info"))
        for name, problem in copied:
            if problem:
                out.append(c(f"ERROR: {name} (copied unchanged): {problem} - do not deploy the "
                             f"new GLOBALS.PRN with it.", "fail"))
    return "\n".join(out)

# ---------------------------------------------------------------------------------------------------

def extraFilesToCopy(folder):

    # Archivos que no son PRN pero se despliegan con ellos (.PIK, .XML): se copian sin cambios.
    return [os.path.join(folder, f) for f in sorted(os.listdir(folder), key=str.lower)
            if f.lower().endswith(COPY_EXTENSIONS) and os.path.isfile(os.path.join(folder, f))]

def copyUnoptimized(folder, outputDir, projectFiles, optimized, failed, globalsPath, globalsOut):

    """
        Deja en la carpeta de salida el juego completo para desplegar: copia sin cambios cada
        PRN que no se optimizó (excluido, no elegido, o que falló la verificación; en ese caso
        el original queda junto al <archivo>.FAILED) y los archivos .PIK y .XML.
        GLOBALS.PRN: si la corrida no escribió uno nuevo (sin ORs globales nuevos, o sin mover
        ORs repetidos), se copia el original; así nunca falta ni queda uno viejo de otra corrida.
        Si hay un GLOBALS.PRN nuevo, cada PRN copiado se verifica con él.
        Devuelve [(nombre, problema o None)].
    """

    done = {os.path.normcase(p) for p in optimized} - {os.path.normcase(p) for p in failed}
    prns = [p for p in projectFiles if os.path.normcase(p) not in done]
    globalsCopy = [globalsPath] if globalsPath and not globalsOut else []

    copied = []
    for path in globalsCopy + prns + extraFilesToCopy(folder):
        name = os.path.basename(path)
        shutil.copy2(path, os.path.join(outputDir, name))
        problem = None
        if globalsOut and isPrn(name):
            print(f"  {paint('checking  ', 'ok')} {name} with the new GLOBALS.PRN ...", flush=True)
            try:
                _, mismatches = BMMT.verifyWithNewGlobals(path, globalsPath, globalsOut)
                if mismatches:
                    problem = f"{len(mismatches)} differences with the new GLOBALS.PRN"
            except Exception as error:
                problem = f"{type(error).__name__}: {error}"
        copied.append((name, problem))
    return copied

# ---------------------------------------------------------------------------------------------------

def askNumber(prompt, default):

    while True:
        answer = ask(prompt, str(default))
        if answer.isdigit() and int(answer) >= 2:
            return int(answer)
        print(paint("  Enter a whole number of 2 or more.", "warn"))

# ---------------------------------------------------------------------------------------------------

def optimizeFlow():

    folder = chooseFolder()
    if folder is None:
        return

    files, globalsPath, projectFiles, skipped = chooseFiles(folder)
    files, extraFiles, skipTables = chooseExclusions(files)
    excludedFiles = skipped + [os.path.basename(f) for f in extraFiles]
    if not files:
        print(paint("Nothing to optimize: every selected file is excluded.", "warn"))
        return

    maxOrValues = askNumber("Max values per new OR (bigger merges are split in blocks)",
                            DEFAULT_MAX_OR_VALUES)
    consolidate = bool(globalsPath) and askYesNo(
        "Move repeated ORs to GLOBALS.PRN and remove them from the PRN files?", True)

    outputDir = ask("Output folder", defaultOutputDir(folder)).strip('"')
    outputDir = os.path.abspath(outputDir)
    if os.path.normcase(outputDir) == os.path.normcase(os.path.abspath(folder)):
        print(paint("The output folder cannot be the input folder (the originals would be "
                    "overwritten).", "fail"))
        return

    os.makedirs(outputDir, exist_ok=True)
    # Todo lo que se escribe en la salida: PRNs optimizados o copiados, .PIK y GLOBALS.PRN.
    targets = projectFiles + extraFilesToCopy(folder) + ([globalsPath] if globalsPath else [])
    existing = [f for f in targets if os.path.exists(os.path.join(outputDir, os.path.basename(f)))]
    if existing and not askYesNo(f"{len(existing)} files already exist in the output folder. "
                                 f"Overwrite them?"):
        return

    print(paint(f"\nOptimizing {len(files)} files -> {outputDir}", "title"))
    if excludedFiles:
        print(paint(f"  skipping files: {', '.join(excludedFiles)}", "warn"))
    print(paint(f"  skipping tables named: {', '.join(skipTables)}", "warn") + "\n")
    started = time.time()
    labels = {"optimize": ("optimizing", "info"), "consolidate": ("moving repeated ORs to", "step"),
              "verify": ("verifying", "ok")}
    live = LiveLine()

    def progress(stage, name):
        live.clear()
        label, style = labels[stage]
        print(f"  {paint(f'{label:<10}', style)} {name} ...", flush=True)

    def tableProgress(stage, current, total, table):
        verb = "working on" if stage == "optimize" else "checking"
        live.show(f"             {verb} table {table or '(no name)'}  {current}/{total}")

    project = BMMT.optimizeProject(files, outputDir, globalsPath=globalsPath,
                                   projectPaths=projectFiles, consolidate=consolidate,
                                   progress=progress, tableProgress=tableProgress,
                                   maxOrValues=maxOrValues, skipTables=skipTables)
    live.clear()

    rows = [summarize(path, project["files"][path]) for path in files]

    # Un archivo que no pasó la verificación no debe poder usarse por error: se renombra a
    # .FAILED y en su lugar se copia el original.
    failed = []
    for path, row in zip(files, rows):
        if row.get("status", "FAILED").startswith("FAILED"):
            failed.append(path)
            target = os.path.join(outputDir, row["file"])
            if os.path.exists(target):
                os.replace(target, target + ".FAILED")

    print(paint("\nCopying the files that were not optimized ...", "title"))
    copied = copyUnoptimized(folder, outputDir, projectFiles, files, failed, globalsPath,
                             project["globalsOut"])

    summary = formatSummary(rows, project, excludedFiles=excludedFiles, copied=copied)
    summaryPath = os.path.join(outputDir, "summary.txt")
    with open(summaryPath, "w", encoding="utf-8") as fh:
        fh.write(f"{SIGNATURE} - {time.strftime('%Y-%m-%d %H:%M')}\n\n{summary}\n")

    print("\n" + formatSummary(rows, project, color=True, excludedFiles=excludedFiles,
                               copied=copied))
    print(paint(f"\nTotal time: {time.time() - started:.0f}s", "dim"))
    print(f"Per-file reports: <file>.report.txt in {outputDir}")
    print(f"Summary saved to {summaryPath}")
    if any(r.get("status", "FAILED") != "OK" for r in rows):
        print(paint("Files that failed were renamed to <file>.FAILED - do not use them. "
                    "Their originals were copied in their place.", "fail"))

# ===================================================================================================

def runTests():

    print(paint("\nRunning unit tests (test_BidManMaintenanceToolsV1_4_0) ...\n", "title"))
    suite = unittest.defaultTestLoader.loadTestsFromName("test_BidManMaintenanceToolsV1_4_0")
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if result.wasSuccessful():
        print(paint(f"All {result.testsRun} tests passed.", "ok"))
    else:
        print(paint(f"{len(result.failures) + len(result.errors)} of {result.testsRun} tests "
                    f"failed.", "fail"))
    return result.wasSuccessful()

# ===================================================================================================

# Colores del icono (24 bits) para las letras del dibujo ASCII de bienvenida.
ART_COLORS = {"w": (238, 242, 245), "d": (174, 184, 196), "g": (61, 245, 140), "o": (255, 176, 32)}

def welcomeLines(art, colors, color=True):

    """
        Líneas del dibujo ASCII de bienvenida (welcome_art.ART), todas del mismo ancho para que
        el texto de al lado quede alineado. Con color=True cada carácter toma el color que
        indica welcome_art.COLORS en la misma posición.
    """

    art, colors = art.strip("\n").split("\n"), colors.strip("\n").split("\n")
    width = max(len(line) for line in art)
    lines = []
    for y, line in enumerate(art):
        line = line.ljust(width)
        if not color:
            lines.append(line)
            continue
        mask = colors[y] if y < len(colors) else ""
        out, current = "", None
        for x, ch in enumerate(line):
            key = mask[x] if x < len(mask) and ch != " " else None
            if key != current:
                rgb = ART_COLORS.get(key)
                out += "\033[38;2;{};{};{}m".format(*rgb) if rgb else "\033[0m"
                current = key
            out += ch
        lines.append(out + ("\033[0m" if current else ""))
    return lines

def showWelcome():

    # Dibujo del icono en ASCII con el nombre de la app al lado. Solo si cabe en la ventana;
    # si no, el menú ya muestra el título.
    try:
        from welcome_art import ART, COLORS
    except ImportError:
        return
    art = welcomeLines(ART, COLORS, color=useColor)
    middle = len(art) // 2
    # Renglón del dibujo -> (texto, estilo o None).
    lines = {
        middle - 4: (APP_NAME, "title"),
        middle - 3: (f"version {APP_VERSION}", "dim"),
        middle - 2: (f"Created by {AUTHOR} · {AUTHOR_EMAIL}", "option"),
        middle: ("Smaller PRN files, same behavior.", None),
        middle + 1: ("Every file is tested against its original.", None),
        middle + 2: ("Your original files are never changed.", "ok"),
        middle + 4: ("To see more information go to:", None),
        middle + 5: (REPOSITORY, "info"),
    }
    # Solo si cabe completo: un renglón partido desarma el dibujo.
    width = max(len(line) for line in ART.split("\n"))
    if shutil.get_terminal_size().columns < 2 + width + 4 + max(len(t) for t, _ in lines.values()) + 1:
        return

    print()
    for i, line in enumerate(art):
        text, style = lines.get(i, ("", None))
        print(f"  {line}    {paint(text, style) if style else text}".rstrip())

def showAbout():

    print(paint(f"\n{APP_NAME}", "title") + paint(f"  version {APP_VERSION}", "dim"))
    print(f"  Created by   {AUTHOR}")
    print(f"  Contact      {AUTHOR_EMAIL}")
    print(f"  Copyright    {COPYRIGHT}")
    print(f"  More info    {paint(REPOSITORY, 'info')}")
    if SPECIAL_THANKS:
        print(f"  Thanks to    {', '.join(SPECIAL_THANKS)}, for the help getting this project started")

# ===================================================================================================

def main():

    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass
    enableColor()
    if os.name == "nt":
        os.system(f"title {APP_NAME}")

    # Las pruebas unitarias son para desarrollo: en el .exe solo se ofrece optimizar.
    options = [("1", "Optimize PRN files")]
    if not FROZEN:
        options += [("2", "Run unit tests"), ("3", "Run unit tests, then optimize")]
    options += [("a", "About"), ("q", "Quit")]

    showWelcome()
    while True:
        print(paint(f"\n=== {APP_NAME} (v{APP_VERSION}) ===", "title"))
        for key, text in options:
            print(f"  {paint(key + ')', 'option')} {text}")
        choice = ask("Choose", "1").lower()

        if choice == "1":
            optimizeFlow()
        elif choice == "2" and not FROZEN:
            runTests()
        elif choice == "3" and not FROZEN:
            if runTests():
                optimizeFlow()
            else:
                print(paint("\nTests failed - not optimizing.", "fail"))
        elif choice in ("a", "about"):
            showAbout()
        elif choice in ("q", "quit", "exit"):
            return

# ---------------------------------------------------------------------------------------------------

def run():

    # En el .exe la ventana se cierra al terminar: ante un error inesperado se muestra y se
    # espera Enter para que el usuario pueda leerlo.
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        import traceback
        traceback.print_exc()
        if FROZEN:
            try:
                input("\nUnexpected error. Press Enter to close ...")
            except (EOFError, KeyboardInterrupt):
                pass
        sys.exit(1)

if __name__ == "__main__":
    run()
