"""
    BidManMaintenanceToolsV1_4_0

    Reescritura del lector / optimizador de archivos PRN.

    Diferencias principales contra V1_3_3:

    * El PRN se lee línea por línea con open() (sin pandas). Cada línea se guarda tal cual,
      por lo que leer y escribir sin optimizar produce exactamente el mismo archivo.
    * Las columnas se cortan con las posiciones (en caracteres) de los nombres de columna
      en la línea HEADING. El PRN es de ancho fijo.
    * Solo se aplican transformaciones que preservan el comportamiento de la tabla:

        1. Filas R CONSECUTIVAS, idénticas salvo en UNA columna INPUT (ALPHA) que contiene
           valores literales, con la misma salida completa  ->  una sola fila con un OR.
           Se repite columna por columna hasta que no haya más cambios, así que los
           "rectángulos" completos (p. ej. ples x enclosure_type) también se compactan.
        2. PICK ONE: una fila R idéntica a una fila R anterior nunca puede ganar -> se elimina.

      En PICK ALL solo se fusionan filas con valores distintos (así el número de
      resultados no cambia) y no se eliminan duplicados.

    * Después de escribir, el archivo resultante se vuelve a leer y cada tabla se compara
      contra la original con un evaluador Pick (PickEvaluator) usando miles de entradas.

    Tipos de línea dentro de una tabla (primer campo de la línea):

        R  = Rule
        D  = Disabled  (se conserva, nunca coincide)
        -  = Continuation (extiende la regla R anterior; esa regla no se toca)
        C, o línea que empieza con espacio = Comment (se conserva tal cual)

    Las filas D, comentarios y continuaciones actúan como "barrera": nunca se fusionan
    filas que estén separadas por una de ellas.
"""

import re
import random
from collections import Counter, defaultdict

RULE = "R"
DISABLED = "D"
CONTINUATION = "-"
COMMENT = "C"
BLANK = "BLANK"
UNKNOWN = "UNKNOWN"

SENTINEL = "__VALOR_NO_EXISTENTE__"

# ===================================================================================================

class Row:

    def __init__(self, raw, kind, cells=None, lineNumbers=None):

        self.raw = raw
        self.kind = kind
        self.cells = cells
        # Líneas del archivo original que representa esta fila (más de una si es una fusión).
        self.lineNumbers = list(lineNumbers or [])
        # locked = tiene continuaciones o no se pudo leer con certeza -> no se optimiza.
        self.locked = False
        # dirty = la fila cambió y hay que regenerar self.raw al escribir.
        self.dirty = False
        # Filas '-' que extienden esta regla.
        self.continuation = []

# ===================================================================================================

class Table:

    def __init__(self, index, lineNumber, typeLine, headingLine, ioLine, dataTypeLine):

        self.index = index
        self.lineNumber = lineNumber
        self.typeLine = typeLine
        self.headingLine = headingLine
        self.ioLine = ioLine
        self.dataTypeLine = dataTypeLine
        self.typeOfTable = typeLine.partition(":")[2].strip().upper()

        # matches[0] es la palabra "HEADING"; desde "Description" en adelante son columnas.
        matches = list(re.finditer(r"\S+", headingLine))[1:]
        if not matches:
            raise ValueError(f"Línea {lineNumber + 1}: HEADING sin columnas")

        self.columns = [m.group() for m in matches]
        self.starts = [m.start() for m in matches]
        self.io = [self._slice(ioLine, i).upper() for i in range(len(self.columns))]
        self.dataTypes = [self._slice(dataTypeLine, i).upper() for i in range(len(self.columns))]
        self.rows = []
        self.misaligned = 0

    # -----------------------------------------------------------------------------------------------

    @property
    def name(self):
        for row in self.rows:
            if row.kind in (RULE, DISABLED) and row.cells[0]:
                return row.cells[0]
        return ""

    @property
    def inputColumns(self):
        return [i for i, io in enumerate(self.io) if i > 0 and io == "INPUT"]

    @property
    def outputColumns(self):
        return [i for i, io in enumerate(self.io) if io == "OUTPUT"]

    @property
    def ruleRows(self):
        return [row for row in self.rows if row.kind == RULE]

    # -----------------------------------------------------------------------------------------------

    def _slice(self, line, i):

        end = self.starts[i + 1] if i + 1 < len(self.starts) else None
        return line[self.starts[i]:end].strip()

    # -----------------------------------------------------------------------------------------------

    def _isAligned(self, raw):

        # En ancho fijo, el carácter anterior al inicio de cada columna debe ser un espacio.
        # Si no lo es, un valor se desbordó a la columna siguiente y el corte no es confiable.
        return all(len(raw) <= b or raw[b - 1] == " " for b in self.starts)

    # -----------------------------------------------------------------------------------------------

    def _lastRule(self):

        # Una continuación se agrega a la regla R anterior, saltando D y comentarios.
        for row in reversed(self.rows):
            if row.kind == RULE:
                return row
        return None

    # -----------------------------------------------------------------------------------------------

    def addLine(self, raw, lineNumber):

        field = raw[:self.starts[0]].strip()

        if raw.strip() == "":
            kind = BLANK
        elif raw[0] == " ":
            kind = COMMENT
        elif field in (RULE, DISABLED, CONTINUATION):
            kind = field
        elif field == "C":
            kind = COMMENT
        else:
            kind = UNKNOWN

        row = Row(raw, kind, lineNumbers=[lineNumber])

        if kind in (RULE, DISABLED, CONTINUATION):
            row.cells = [self._slice(raw, i) for i in range(len(self.columns))]
            if not self._isAligned(raw):
                row.locked = True
                self.misaligned += 1

        if kind == CONTINUATION:
            rule = self._lastRule()
            if rule is not None:
                rule.locked = True
                rule.continuation.append(row)

        self.rows.append(row)

    # -----------------------------------------------------------------------------------------------

    def widen(self, col, newWidth):

        # Ensancha la columna col insertando espacios al inicio de la columna siguiente en el
        # encabezado y en todas las filas R/D/-. Los comentarios se dejan tal cual.
        if col + 1 >= len(self.starts):
            return

        delta = newWidth - (self.starts[col + 1] - self.starts[col])
        if delta <= 0:
            return

        pos = self.starts[col + 1]

        def shift(line):
            return line[:pos] + " " * delta + line[pos:] if len(line) > pos else line

        self.headingLine = shift(self.headingLine)
        self.ioLine = shift(self.ioLine)
        self.dataTypeLine = shift(self.dataTypeLine)

        for row in self.rows:
            if row.kind in (RULE, DISABLED, CONTINUATION) and not row.dirty:
                row.raw = shift(row.raw)

        for i in range(col + 1, len(self.starts)):
            self.starts[i] += delta

    # -----------------------------------------------------------------------------------------------

    def _renderCells(self, kind, cells):

        line = kind.ljust(self.starts[0])
        for i, cell in enumerate(cells):
            if i + 1 < len(cells):
                line += cell.ljust(self.starts[i + 1] - self.starts[i])
            else:
                line += cell
        return line.rstrip()

    # -----------------------------------------------------------------------------------------------

    def render(self):

        dirty = [row for row in self.rows if row.dirty]
        if not dirty:
            return

        # Cada valor necesita al menos un espacio antes de la columna siguiente.
        for col in range(len(self.columns) - 1):
            needed = max(len(row.cells[col]) + 1 for row in dirty)
            if needed > self.starts[col + 1] - self.starts[col]:
                self.widen(col, needed)

        for row in dirty:
            row.raw = self._renderCells(row.kind, row.cells)
            row.dirty = False

    # -----------------------------------------------------------------------------------------------

    def lines(self):

        return [self.typeLine, self.headingLine, self.ioLine, self.dataTypeLine] + \
               [row.raw for row in self.rows]

# ===================================================================================================

class PrnFile:

    def __init__(self, path=None):

        self.path = path
        self.newline = "\r\n"
        self.endsWithNewline = True
        self.preamble = []      # Líneas antes de la primera tabla (DEFINE, líneas en blanco).
        self.tables = []
        self.listDelimiter = ";"
        self.delimiterChars = ":;"
        self.ors = {}           # nombre -> lista de valores (si se repite, gana la última)
        self.orCount = Counter()
        self.newOrs = []        # [(nombre, valores)] creados por el optimizador
        self.removedOrs = set()

        if path is not None:
            self.read(path)

    # -----------------------------------------------------------------------------------------------

    def read(self, path):

        # latin-1 mapea cada byte a un carácter, así que el ida y vuelta es exacto.
        with open(path, encoding="latin-1", newline="") as fh:
            text = fh.read()

        self.path = path
        self.newline = "\r\n" if "\r\n" in text else "\n"
        self.endsWithNewline = text.endswith(self.newline)

        lines = text.split(self.newline)
        if self.endsWithNewline:
            lines.pop()

        table = None
        i = 0

        while i < len(lines):

            line = lines[i]

            if line.startswith("TABLE TYPE"):

                header = lines[i + 1:i + 4]
                if len(header) < 3 or not header[0].startswith("HEADING") or \
                   not header[1].startswith("I/O") or not header[2].startswith("TYPE"):
                    raise ValueError(f"{path}:{i + 1}: se esperaba HEADING, I/O y TYPE "
                                     f"después de TABLE TYPE")

                table = Table(len(self.tables), i + 1, line, *header)
                self.tables.append(table)
                i += 4
                continue

            if table is None:
                self.preamble.append(line)
            else:
                table.addLine(line, i + 1)

            i += 1

        self._parseDefinitions()

    # -----------------------------------------------------------------------------------------------

    def _parseDefinitions(self):

        for line in self.preamble:

            if line.startswith("DEFINE DELIMITER"):
                chars = line[len("DEFINE DELIMITER"):].strip()
                if chars:
                    self.delimiterChars = chars
                    self.listDelimiter = chars[-1]

            elif line.startswith("DEFINE OR:"):
                # El nombre puede contener ':' (p. ej. "OR:AC_Coil_Voltgs"), por eso solo se
                # corta en el primer '='.
                name, sep, values = line[len("DEFINE OR:"):].partition("=")
                if not sep:
                    continue
                name = name.strip()
                self.ors[name] = [v.strip() for v in values.rstrip().split(self.listDelimiter)]
                self.orCount[name] += 1

    # -----------------------------------------------------------------------------------------------

    def orUsage(self):

        usage = Counter()
        for table in self.tables:
            for row in table.rows:
                if row.cells is None:
                    continue
                for cell in row.cells:
                    name = cell[2:].strip() if cell.startswith("<>") else cell
                    if name in self.ors:
                        usage[name] += 1
        return usage

    # -----------------------------------------------------------------------------------------------

    def write(self, path):

        lines = []
        for line in self.preamble:
            if line.startswith("DEFINE OR:"):
                name = line[len("DEFINE OR:"):].partition("=")[0].strip()
                if name in self.removedOrs:
                    continue
            lines.append(line)

        if self.newOrs:
            position = 0
            for i, line in enumerate(lines):
                if line.startswith("DEFINE"):
                    position = i + 1
            lines[position:position] = [f"DEFINE OR:{name}={self.listDelimiter.join(values)}"
                                        for name, values in self.newOrs]

        for table in self.tables:
            table.render()
            lines.extend(table.lines())

        text = self.newline.join(lines) + (self.newline if self.endsWithNewline else "")

        with open(path, "w", encoding="latin-1", newline="") as fh:
            fh.write(text)

# ===================================================================================================

class PrnOptimizer:

    def __init__(self, prn, skipTables=(), mergeDataTypes=("ALPHA",), optimizePickAll=True,
                 removeDuplicateRules=True, removeUnusedOrs=False, maxOrNameLength=40,
                 searchWindow=400):

        self.prn = prn
        # Distancia máxima (en reglas) para buscar reglas relacionadas no consecutivas.
        self.searchWindow = searchWindow
        self._condCache = {}
        self.skipTables = set(skipTables)
        self.mergeDataTypes = set(t.upper() for t in mergeDataTypes)
        self.optimizePickAll = optimizePickAll
        self.removeDuplicateRules = removeDuplicateRules
        self.removeUnusedOrs = removeUnusedOrs
        self.maxOrNameLength = maxOrNameLength

        # Nombres que un OR nuevo no puede usar: ORs existentes y cualquier valor de celda.
        self._reserved = set(prn.ors)
        for table in prn.tables:
            for row in table.rows:
                if row.cells is not None:
                    self._reserved.update(row.cells)

        # Reutilizar un OR existente si tiene exactamente los mismos valores
        # (solo si su nombre está definido una sola vez).
        self._orByValues = {}
        for name, values in prn.ors.items():
            key = frozenset(values)
            if prn.orCount[name] == 1 and len(values) > 1 and key not in self._orByValues:
                self._orByValues[key] = name

        self._orCounter = 0

    # -----------------------------------------------------------------------------------------------

    def run(self):

        tables = [self._optimizeTable(table) for table in self.prn.tables]

        # Las fusiones van creando ORs intermedios (A;B, luego A;B;C, ...). Solo se
        # conservan los ORs nuevos que quedaron en uso.
        usage = self.prn.orUsage()
        orphans = {name for name, _ in self.prn.newOrs if usage[name] == 0}
        self.prn.newOrs = [(n, v) for n, v in self.prn.newOrs if n not in orphans]
        for name in orphans:
            del self.prn.ors[name]
            del self.prn.orCount[name]

        unused = [name for name in self.prn.ors if usage[name] == 0]
        if self.removeUnusedOrs:
            self.prn.removedOrs.update(unused)

        return {
            "tables": tables,
            "newOrs": list(self.prn.newOrs),
            "unusedOrs": unused,
            "unusedOrsRemoved": self.removeUnusedOrs,
            "singleUseNewOrs": sum(1 for name, _ in self.prn.newOrs if usage[name] == 1),
            "duplicateOrNames": [n for n, c in self.prn.orCount.items() if c > 1],
        }

    # -----------------------------------------------------------------------------------------------

    def _optimizeTable(self, table):

        info = {
            "index": table.index,
            "name": table.name,
            "type": table.typeOfTable,
            "lineNumber": table.lineNumber,
            "rulesBefore": len(table.ruleRows),
            "rulesAfter": len(table.ruleRows),
            "merges": 0,
            "duplicatesRemoved": 0,
            "deadRules": [],
            "skipped": None,
        }

        pickAll = table.typeOfTable == "PICK ALL"

        if table.name in self.skipTables or table.index in self.skipTables:
            info["skipped"] = "en la lista skipTables"
        elif table.typeOfTable not in ("PICK ONE", "PICK ALL"):
            info["skipped"] = f"tipo de tabla desconocido: {table.typeOfTable!r}"
        elif table.misaligned:
            info["skipped"] = f"{table.misaligned} filas no alineadas con HEADING"
        elif pickAll and not self.optimizePickAll:
            info["skipped"] = "PICK ALL excluida"

        if info["skipped"]:
            return info

        columns = [c for c in table.inputColumns if table.dataTypes[c] in self.mergeDataTypes]

        changed = True
        while changed:
            changed = False
            if pickAll:
                for col in columns:
                    changed |= self._mergeColumn(table, col, pickAll, info)
                continue
            if self.removeDuplicateRules:
                changed |= self._removeSubsumed(table, info)
            for col in columns:
                changed |= self._mergeDistant(table, col, info)

        if not pickAll:
            info["deadRules"] = self._findDeadRules(table)

        info["rulesAfter"] = len(table.ruleRows)
        return info

    # -----------------------------------------------------------------------------------------------

    # --- Condiciones como conjuntos ------------------------------------------------------------------
    #
    # Para razonar sobre reglas no consecutivas cada celda INPUT se convierte en:
    #   ("ALL", None)   celda vacía: cualquier valor, incluso sin entrada
    #   ("IN", set)     literal u OR: uno de esos valores (nunca coincide sin entrada)
    #   ("NOT", set)    <>literal o <>OR: cualquier valor fuera del conjunto, o sin entrada
    #   ("TEXT", celda) cualquier otra cosa (operadores, rangos, columnas no ALPHA, ...):
    #                   solo se sabe que es igual a otra celda con el mismo texto.

    def _members(self, value):

        if value in self.prn.ors:
            return frozenset(self.prn.ors[value]) if self.prn.orCount[value] == 1 else None
        return frozenset([value]) if self._isLiteral(value) else None

    # -----------------------------------------------------------------------------------------------

    def _cond(self, table, col, cell):

        key = (table.index, col, cell)
        cond = self._condCache.get(key)
        if cond is None:
            if cell == "":
                cond = ("ALL", None)
            elif table.dataTypes[col] not in self.mergeDataTypes:
                cond = ("TEXT", cell)
            else:
                negated = cell.startswith("<>")
                members = self._members(cell[2:].strip() if negated else cell)
                if members is None:
                    cond = ("TEXT", cell)
                else:
                    cond = ("NOT" if negated else "IN", members)
            self._condCache[key] = cond
        return cond

    def _rowConds(self, table, row):
        return [self._cond(table, c, row.cells[c]) for c in table.inputColumns]

    def _rowOutput(self, table, row):
        return tuple(row.cells[c] for c in table.outputColumns)

    # -----------------------------------------------------------------------------------------------

    @staticmethod
    def _disjoint(a, b):

        # True solo si se puede demostrar que ninguna entrada cumple ambas condiciones.
        for (ka, sa), (kb, sb) in zip(a, b):
            if ka == "IN" and kb == "IN" and not (sa & sb):
                return True
            if ka == "IN" and kb == "NOT" and sa <= sb:
                return True
            if ka == "NOT" and kb == "IN" and sb <= sa:
                return True
        return False

    @staticmethod
    def _subset(a, b):

        # True solo si se puede demostrar que toda entrada que cumple a también cumple b.
        for ca, cb in zip(a, b):
            (ka, sa), (kb, sb) = ca, cb
            if kb == "ALL" or ca == cb:
                continue
            if ka == "IN" and kb == "IN" and sa <= sb:
                continue
            if ka == "IN" and kb == "NOT" and not (sa & sb):
                continue
            if ka == "NOT" and kb == "NOT" and sb <= sa:
                continue
            return False
        return True

    # -----------------------------------------------------------------------------------------------

    def _removeSubsumed(self, table, info):

        """
            PICK ONE. Elimina reglas que se pueden quitar sin cambiar ningún resultado:

            1. Muerta: una regla ANTERIOR con la misma salida contiene todas sus entradas,
               así que esta regla nunca gana.
            2. Redundante: una regla POSTERIOR con la misma salida contiene todas sus
               entradas, y cada regla intermedia tiene la misma salida o no comparte
               ninguna entrada con ella. Al quitarla, sus entradas caen en la posterior.
        """

        rules = table.ruleRows
        conds = [self._rowConds(table, r) for r in rules]
        outs = [self._rowOutput(table, r) for r in rules]
        removed = set()

        byOutput = defaultdict(list)
        for p, rule in enumerate(rules):
            if rule.locked:
                continue
            for q in reversed(byOutput[outs[p]][-self.searchWindow:]):
                if self._subset(conds[p], conds[q]):
                    removed.add(p)
                    break
            else:
                byOutput[outs[p]].append(p)

        if not removed:
            for p, rule in enumerate(rules):
                if rule.locked:
                    continue
                for q in range(p + 1, min(len(rules), p + 1 + self.searchWindow)):
                    if q in removed:
                        continue
                    if rules[q].locked:
                        break
                    if outs[q] == outs[p]:
                        if self._subset(conds[p], conds[q]):
                            removed.add(p)
                            break
                        continue
                    if not self._disjoint(conds[p], conds[q]):
                        break

        if removed:
            gone = {id(rules[p]) for p in removed}
            table.rows = [row for row in table.rows if id(row) not in gone]

        info["duplicatesRemoved"] += len(removed)
        return bool(removed)

    # -----------------------------------------------------------------------------------------------

    def _mergeDistant(self, table, col, info):

        """
            PICK ONE. Como _mergeColumn pero sin exigir que las filas sean consecutivas:
            la regla j se fusiona en la regla anterior i (que difiere solo en col, con la
            misma salida) si cada regla entre ambas tiene la misma salida o no comparte
            ninguna entrada con j. Así, las entradas de j que antes llegaban a j ahora
            se resuelven en i con la misma salida, y nada más cambia.
        """

        rules = table.ruleRows
        position = {id(r): p for p, r in enumerate(rules)}
        conds = [self._rowConds(table, r) for r in rules]
        outs = [self._rowOutput(table, r) for r in rules]
        k = table.inputColumns.index(col)
        removed = set()

        groups = defaultdict(list)
        for p, rule in enumerate(rules):
            if not rule.locked and conds[p][k][0] == "IN":
                groups[tuple(c for i, c in enumerate(rule.cells) if i != col)].append(p)

        for members in groups.values():

            anchor = members[0]

            for p in members[1:]:

                ok = p - anchor <= self.searchWindow and all(
                    q in removed or (not rules[q].locked and
                                     (outs[q] == outs[p] or self._disjoint(conds[q], conds[p])))
                    for q in range(anchor + 1, p))

                if not ok:
                    anchor = p
                    continue

                values = list(dict.fromkeys(self._valuesOf(rules[anchor].cells[col]) +
                                            self._valuesOf(rules[p].cells[col])))
                cell = values[0] if len(values) == 1 else self._orFor(values, table.columns[col])

                rules[anchor].cells[col] = cell
                rules[anchor].lineNumbers += rules[p].lineNumbers
                rules[anchor].dirty = True
                conds[anchor] = self._rowConds(table, rules[anchor])
                removed.add(p)

        if removed:
            gone = {id(rules[p]) for p in removed}
            table.rows = [row for row in table.rows if id(row) not in gone]

        info["merges"] += len(removed)
        return bool(removed)

    # -----------------------------------------------------------------------------------------------

    def _valuesOf(self, cell):
        return list(self.prn.ors[cell]) if cell in self.prn.ors else [cell]

    # -----------------------------------------------------------------------------------------------

    def _findDeadRules(self, table):

        # Reglas con las mismas entradas que una regla anterior pero distinta salida: nunca
        # ganan. No se borran (puede ser un error de autoría); solo se reportan.
        seen = {}
        dead = []
        for row in table.ruleRows:
            if row.locked:
                continue
            key = tuple(row.cells[c] for c in table.inputColumns)
            if key in seen:
                dead.append((row.lineNumbers[0], seen[key]))
            else:
                seen[key] = row.lineNumbers[0]
        return dead

    # -----------------------------------------------------------------------------------------------

    def _isLiteral(self, cell):

        if cell == "" or cell in self.prn.ors:
            return False
        if cell[0] in "<>=[(@~!":
            return False
        if any(ch in cell for ch in self.prn.delimiterChars) or "*" in cell or "?" in cell:
            return False
        return True

    # -----------------------------------------------------------------------------------------------

    def _mergeColumn(self, table, col, pickAll, info):

        # Junta filas R consecutivas que solo difieren en la columna col. Cualquier otra
        # línea (D, comentario, continuación, regla bloqueada) corta el grupo.
        def keyWithout(row):
            return tuple(cell for i, cell in enumerate(row.cells) if i != col)

        newRows = []
        group = []
        merged = 0

        def flush():
            nonlocal merged
            if len(group) >= 2:
                newRows.append(self._mergeGroup(table, group, col))
                merged += 1
            else:
                newRows.extend(group)
            group.clear()

        for row in table.rows:

            if row.kind == RULE and not row.locked and self._isLiteral(row.cells[col]):

                if group:
                    sameRest = keyWithout(group[0]) == keyWithout(row)
                    # En PICK ALL un valor repetido daría dos resultados; no se fusiona.
                    repeated = pickAll and row.cells[col] in {g.cells[col] for g in group}
                    if not sameRest or repeated:
                        flush()

                group.append(row)

            else:
                flush()
                newRows.append(row)

        flush()

        table.rows = newRows
        info["merges"] += merged
        return merged > 0

    # -----------------------------------------------------------------------------------------------

    def _mergeGroup(self, table, group, col):

        values = list(dict.fromkeys(row.cells[col] for row in group))

        cells = list(group[0].cells)
        cells[col] = values[0] if len(values) == 1 else self._orFor(values, table.columns[col])

        row = Row(None, RULE, cells, [n for g in group for n in g.lineNumbers])
        row.dirty = True
        return row

    # -----------------------------------------------------------------------------------------------

    def _orFor(self, values, columnName):

        key = frozenset(values)
        if key in self._orByValues:
            return self._orByValues[key]

        name = self._newOrName(values, columnName)

        self.prn.newOrs.append((name, list(values)))
        self.prn.ors[name] = list(values)
        self.prn.orCount[name] += 1
        self._orByValues[key] = name
        self._reserved.add(name)
        return name

    # -----------------------------------------------------------------------------------------------

    def _newOrName(self, values, columnName):

        tag = re.sub(r"[^A-Za-z0-9_]", "", columnName)[:20] or "col"
        parts = [re.sub(r"[^A-Za-z0-9-]", "", v) for v in values]

        name = f"OR:{tag}_" + "_".join(parts)
        if len(name) > self.maxOrNameLength or not all(parts):
            self._orCounter += 1
            name = f"OR:{tag}_{self._orCounter}"

        base, n = name, 1
        while name in self._reserved:
            n += 1
            name = f"{base}_{n}"

        return name

# ===================================================================================================

class PickEvaluator:

    """
        Evaluador Pick mínimo, usado para comparar una tabla original contra la optimizada.

        Semántica por celda INPUT: vacío = comodín (también coincide sin entrada),
        nombre de OR = pertenencia, <>X = distinto de X (o de cualquier valor del OR X;
        coincide sin entrada), >=, <=, >, <, = y rangos [a,b] numéricos, y cualquier otra
        cosa = igualdad exacta (sensible a mayúsculas).

        Cada columna se indexa como bitsets (enteros de Python), así que evaluar una entrada
        sobre miles de reglas es una sola operación AND por columna.
    """

    RANGE = re.compile(r"^([\[(])\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*([\])])$")

    def __init__(self, table, ors):

        rules = table.ruleRows
        self.pickAll = table.typeOfTable == "PICK ALL"
        self.inputColumns = table.inputColumns
        outputs = table.outputColumns

        # Salida completa: celdas OUTPUT + celdas de las continuaciones.
        self.outputs = [tuple(r.cells[c] for c in outputs) +
                        tuple(tuple(cont.cells) for cont in r.continuation) for r in rules]

        self.ors = {name: set(values) for name, values in ors.items()}
        self.orsByValue = defaultdict(set)
        for name, values in self.ors.items():
            for v in values:
                self.orsByValue[v].add(name)

        self.full = (1 << len(rules)) - 1
        self.index = {c: self._buildIndex(c, rules, table.dataTypes[c]) for c in self.inputColumns}
        self.cache = {}

    # -----------------------------------------------------------------------------------------------

    def _buildIndex(self, col, rules, dataType):

        idx = {"wild": 0, "lit": defaultdict(int), "or": defaultdict(int), "negAll": 0,
               "negLit": defaultdict(int), "negOr": defaultdict(int), "other": [],
               "dataType": dataType}

        for r, rule in enumerate(rules):

            cell = rule.cells[col]
            bit = 1 << r

            if cell == "":
                idx["wild"] |= bit
            elif cell.startswith("<>"):
                target = cell[2:].strip()
                idx["negAll"] |= bit
                if target in self.ors:
                    idx["negOr"][target] |= bit
                else:
                    idx["negLit"][target] |= bit
            elif cell in self.ors:
                idx["or"][cell] |= bit
            elif cell[0] in "<>=[(":
                idx["other"].append((bit, cell))
            else:
                idx["lit"][cell] |= bit

        return idx

    # -----------------------------------------------------------------------------------------------

    def _compare(self, cell, value):

        try:
            number = float(value)
        except ValueError:
            return cell == value

        for op in (">=", "<=", ">", "<", "="):
            if cell.startswith(op):
                try:
                    limit = float(cell[len(op):])
                except ValueError:
                    return False
                return {">=": number >= limit, "<=": number <= limit, ">": number > limit,
                        "<": number < limit, "=": number == limit}[op]

        m = self.RANGE.match(cell)
        if m:
            low, high = float(m.group(2)), float(m.group(3))
            lowOk = number >= low if m.group(1) == "[" else number > low
            highOk = number <= high if m.group(4) == "]" else number < high
            return lowOk and highOk

        return cell == value

    # -----------------------------------------------------------------------------------------------

    def _match(self, col, value):

        key = (col, value)
        if key in self.cache:
            return self.cache[key]

        idx = self.index[col]

        if value is None:
            mask = idx["wild"] | idx["negAll"]
        else:
            names = self.orsByValue.get(value, ())
            mask = idx["wild"] | idx["lit"].get(value, 0)
            excluded = idx["negLit"].get(value, 0)
            for name in names:
                mask |= idx["or"].get(name, 0)
                excluded |= idx["negOr"].get(name, 0)
            mask |= idx["negAll"] & ~excluded
            for bit, cell in idx["other"]:
                if self._compare(cell, value):
                    mask |= bit

        self.cache[key] = mask
        return mask

    # -----------------------------------------------------------------------------------------------

    def evaluate(self, inputs):

        mask = self.full
        for col in self.inputColumns:
            mask &= self._match(col, inputs.get(col))
            if not mask:
                break

        if not self.pickAll:
            return None if not mask else self.outputs[(mask & -mask).bit_length() - 1]

        results = []
        while mask:
            low = mask & -mask
            results.append(self.outputs[low.bit_length() - 1])
            mask ^= low
        return tuple(results)

# ===================================================================================================

def _valuePools(tables, ors):

    pools = defaultdict(set)
    for table in tables:
        for row in table.ruleRows:
            for c in table.inputColumns:
                cell = row.cells[c]
                target = cell[2:].strip() if cell.startswith("<>") else cell
                if target in ors:
                    pools[c].update(ors[target])
                elif target:
                    pools[c].add(target)
                    pools[c].update(re.findall(r"-?\d+(?:\.\d+)?", target))
    return {c: sorted(values) + [SENTINEL] for c, values in pools.items()}

# -----------------------------------------------------------------------------------------------

def _targetedInput(row, columns, pools, ors, rng):

    inputs = {}
    for c in columns:
        cell = row.cells[c]
        pool = pools.get(c, [SENTINEL])
        if cell == "":
            inputs[c] = rng.choice(pool + [None])
        elif cell.startswith("<>"):
            target = cell[2:].strip()
            excluded = ors.get(target, {target})
            value = rng.choice(pool)
            for _ in range(5):
                if value not in excluded:
                    break
                value = rng.choice(pool)
            inputs[c] = value
        elif cell in ors:
            inputs[c] = rng.choice(sorted(ors[cell]))
        elif cell[0] in "<>=[(":
            inputs[c] = rng.choice(pool)
        else:
            inputs[c] = cell
    return inputs

# -----------------------------------------------------------------------------------------------

def verifyTable(original, optimized, originalOrs, optimizedOrs, randomTests=2000, seed=0):

    """
        Compara una tabla original contra la optimizada. Devuelve (número de pruebas,
        lista de discrepancias). Las pruebas incluyen, por cada regla original, entradas
        que la satisfacen; por cada regla fusionada, el valor centinela en la columna
        fusionada (debe caer a la siguiente regla igual que antes); y entradas aleatorias.
    """

    if original.columns != optimized.columns or original.io != optimized.io:
        return 0, [("columnas distintas", original.columns, optimized.columns)]

    before = PickEvaluator(original, originalOrs)
    after = PickEvaluator(optimized, optimizedOrs)

    rng = random.Random(seed)
    columns = original.inputColumns
    orsSets = {name: set(values) for name, values in optimizedOrs.items()}
    pools = _valuePools([original, optimized], orsSets)

    tests = []
    for row in original.ruleRows:
        for _ in range(2):
            tests.append(_targetedInput(row, columns, pools, orsSets, rng))

    for row in optimized.ruleRows:
        if len(row.lineNumbers) > 1:
            base = _targetedInput(row, columns, pools, orsSets, rng)
            for c in columns:
                if row.cells[c] in orsSets:
                    for value in (SENTINEL, None):
                        test = dict(base)
                        test[c] = value
                        tests.append(test)

    for _ in range(randomTests):
        tests.append({c: rng.choice(pools.get(c, [SENTINEL]) + [None]) for c in columns})

    mismatches = []
    for test in tests:
        a, b = before.evaluate(test), after.evaluate(test)
        if a != b:
            mismatches.append(({original.columns[c]: v for c, v in test.items()}, a, b))

    return len(tests), mismatches

# ===================================================================================================

def findInlineLists(prn):

    # Una celda INPUT no puede tener una lista "A;B;C": la lista debe declararse como
    # DEFINE OR y la celda debe usar el nombre del OR. Las celdas OUTPUT sí pueden tener
    # listas (p. ej. "@NEMA - Freedom;Soft Starter" es un valor devuelto, no una condición).
    found = []
    for table in prn.tables:
        for row in table.rows:
            if row.cells is None:
                continue
            for col in table.inputColumns:
                if prn.listDelimiter in row.cells[col]:
                    found.append((table.index, table.name, row.lineNumbers[0],
                                  table.columns[col], row.cells[col]))
    return found

# ===================================================================================================

def optimizePrn(inputPath, outputPath, reportPath=None, verify=True, **options):

    """
        Lee inputPath, optimiza, escribe outputPath, vuelve a leer el archivo escrito y
        verifica cada tabla contra la original. Devuelve (resultado, texto del reporte).
        options se pasa a PrnOptimizer (skipTables, optimizePickAll, removeUnusedOrs, ...).
    """

    prn = PrnFile(inputPath)
    result = PrnOptimizer(prn, **options).run()
    prn.write(outputPath)

    result["inlineLists"] = findInlineLists(PrnFile(outputPath))

    result["verification"] = []
    if verify:
        original = PrnFile(inputPath)
        written = PrnFile(outputPath)
        if len(original.tables) != len(written.tables):
            raise RuntimeError("El archivo escrito no tiene el mismo número de tablas")
        for a, b in zip(original.tables, written.tables):
            tests, mismatches = verifyTable(a, b, original.ors, written.ors)
            result["verification"].append((a.index, tests, mismatches))

    report = formatReport(inputPath, outputPath, result)
    if reportPath:
        with open(reportPath, "w", encoding="utf-8") as fh:
            fh.write(report)

    return result, report

# -----------------------------------------------------------------------------------------------

def formatReport(inputPath, outputPath, result):

    out = [f"Entrada: {inputPath}", f"Salida:  {outputPath}", ""]
    out.append(f"{'#':>3}  {'Tabla':<28} {'Tipo':<9} {'Línea':>6} {'Antes':>7} {'Después':>8} "
               f"{'Fusiones':>8} {'Duplic.':>7}  Nota")

    totalBefore = totalAfter = 0
    for t in result["tables"]:
        totalBefore += t["rulesBefore"]
        totalAfter += t["rulesAfter"]
        note = f"omitida: {t['skipped']}" if t["skipped"] else ""
        if t["deadRules"]:
            note += f"{len(t['deadRules'])} reglas inalcanzables con otra salida (no borradas)"
        out.append(f"{t['index']:>3}  {t['name'][:28]:<28} {t['type']:<9} {t['lineNumber']:>6} "
                   f"{t['rulesBefore']:>7} {t['rulesAfter']:>8} {t['merges']:>8} "
                   f"{t['duplicatesRemoved']:>7}  {note}")

    reduction = 100.0 * (totalBefore - totalAfter) / totalBefore if totalBefore else 0.0
    out.append(f"\nReglas R: {totalBefore} -> {totalAfter}  ({reduction:.1f}% menos)")

    out.append(f"\nORs nuevos: {len(result['newOrs'])} "
               f"({result['singleUseNewOrs']} se usan en una sola regla)")
    for name, values in result["newOrs"]:
        out.append(f"  {name} = {';'.join(values)}")

    action = "eliminados" if result["unusedOrsRemoved"] else "no eliminados"
    out.append(f"\nORs sin uso en este archivo ({action}): {len(result['unusedOrs'])}")
    if result["unusedOrs"]:
        out.append("  " + ", ".join(result["unusedOrs"]))

    if result["duplicateOrNames"]:
        out.append(f"\nAVISO: ORs definidos más de una vez: {', '.join(result['duplicateOrNames'])}")

    inline = result.get("inlineLists", [])
    if inline:
        out.append(f"\nERROR: {len(inline)} celdas INPUT con una lista en vez de un OR "
                   f"(declarar la lista con DEFINE OR y usar su nombre):")
        for index, name, line, column, cell in inline[:50]:
            out.append(f"  tabla {index} ({name}): línea {line}, columna {column}: {cell}")
        if len(inline) > 50:
            out.append(f"  ... y {len(inline) - 50} más")

    dead = [(t, d) for t in result["tables"] for d in t["deadRules"]]
    if dead:
        out.append("\nReglas inalcanzables (mismas entradas que una regla anterior, otra salida):")
        for t, (line, firstLine) in dead[:50]:
            out.append(f"  tabla {t['index']} ({t['name']}): línea {line} nunca gana "
                       f"(la línea {firstLine} coincide primero)")
        if len(dead) > 50:
            out.append(f"  ... y {len(dead) - 50} más")

    if result["verification"]:
        totalTests = sum(tests for _, tests, _ in result["verification"])
        failures = [(i, m) for i, _, m in result["verification"] if m]
        status = "OK" if not failures else "FALLÓ"
        out.append(f"\nVerificación: {status} ({totalTests} pruebas, "
                   f"{sum(len(m) for _, m in failures)} discrepancias)")
        for i, mismatches in failures:
            out.append(f"  tabla {i}: {len(mismatches)} discrepancias, p. ej.:")
            for inputs, a, b in mismatches[:3]:
                out.append(f"    entrada={inputs}\n      antes={a}\n      después={b}")

    return "\n".join(out) + "\n"
