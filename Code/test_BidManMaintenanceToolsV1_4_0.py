"""
    Pruebas de BidManMaintenanceToolsV1_4_0.

    Ejecutar desde la carpeta Code:  python -m unittest test_BidManMaintenanceToolsV1_4_0 -v
"""

import glob
import os
import tempfile
import unittest

import BidManMaintenanceToolsV1_4_0 as BMMT

HERE = os.path.dirname(os.path.abspath(__file__))
PRNS = os.path.join(HERE, "..", "ENCLOSC_PRNS", "PRNS")

HEADER = (
    "DEFINE DELIMITER:;\r\n"
    "DEFINE OR:OR:Existing=X;Y\r\n"
)

# ===================================================================================================

def makeTable(rows, tableType="PICK ONE"):

    # Tabla de prueba: frame | poles | encl (INPUT) | price (OUTPUT)
    lines = [
        f"TABLE TYPE: {tableType}",
        "HEADING Description frame poles encl price",
        "I/O                 INPUT INPUT INPUT OUTPUT",
        "TYPE                ALPHA ALPHA ALPHA ALPHA",
    ]
    for kind, frame, poles, encl, price in rows:
        lines.append(f"{kind:<8}{'tbl':<12}{frame:<6}{poles:<6}{encl:<6}{price}".rstrip())
    return HEADER + "\r\n".join(lines) + "\r\n"

# ===================================================================================================

class PrnTestCase(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.dir.cleanup()

    def path(self, name):
        return os.path.join(self.dir.name, name)

    def optimize(self, text, **options):
        source = self.path("in.prn")
        with open(source, "w", encoding="latin-1", newline="") as fh:
            fh.write(text)
        result, report = BMMT.optimizePrn(source, self.path("out.prn"), **options)
        for _, tests, mismatches in result["verification"]:
            self.assertEqual(mismatches, [], report)
        return result, BMMT.PrnFile(self.path("out.prn"))

    def rules(self, prn, table=0):
        return [row.cells[1:] for row in prn.tables[table].ruleRows]

# ===================================================================================================

class TestRoundTrip(PrnTestCase):

    def test_real_files_round_trip_byte_for_byte(self):
        files = sorted(glob.glob(os.path.join(PRNS, "INPUTS*")))
        self.assertTrue(files)
        for source in files:
            with self.subTest(file=os.path.basename(source)):
                target = self.path("rt.prn")
                BMMT.PrnFile(source).write(target)
                with open(source, "rb") as a, open(target, "rb") as b:
                    self.assertEqual(a.read(), b.read())

    def test_or_name_with_colon_is_preserved(self):
        source = self.path("in.prn")
        with open(source, "w", encoding="latin-1", newline="") as fh:
            fh.write(makeTable([("R", "F1", "2", "", "1")]))
        prn = BMMT.PrnFile(source)
        self.assertEqual(prn.ors["OR:Existing"], ["X", "Y"])

    def test_line_kinds(self):
        text = makeTable([("R", "F1", "2", "", "1"), ("D", "F1", "3", "", "1"),
                          ("-", "", "", "", "extra")])
        text += "        a comment\r\n"
        source = self.path("in.prn")
        with open(source, "w", encoding="latin-1", newline="") as fh:
            fh.write(text)
        rows = BMMT.PrnFile(source).tables[0].rows
        self.assertEqual([r.kind for r in rows], ["R", "D", "-", "C"])
        self.assertTrue(rows[0].locked)

# ===================================================================================================

class TestOptimization(PrnTestCase):

    def test_adjacent_rows_differing_in_one_column_become_an_or(self):
        _, prn = self.optimize(makeTable([
            ("R", "F1", "9", "N1", "B3"),
            ("R", "F1", "10", "N1", "B3"),
            ("R", "F1", "12", "N1", "B3"),
            ("R", "F1", "2", "N1", "B5"),
        ]))
        self.assertEqual(self.rules(prn), [["F1", "OR:poles_9_10_12", "N1", "B3"],
                                           ["F1", "2", "N1", "B5"]])
        self.assertEqual(prn.ors["OR:poles_9_10_12"], ["9", "10", "12"])

    def test_merged_input_cells_use_an_or_name_not_a_list(self):
        result, prn = self.optimize(makeTable([
            ("R", "CPX", "9", "N1", "B3"),
            ("R", "HCX", "9", "N1", "B3"),
        ]))
        self.assertEqual(self.rules(prn), [["OR:frame_CPX_HCX", "9", "N1", "B3"]])
        self.assertEqual(prn.ors["OR:frame_CPX_HCX"], ["CPX", "HCX"])
        self.assertEqual(result["inlineLists"], [])

    def test_inline_list_in_input_cell_is_reported(self):
        result, _ = self.optimize(makeTable([
            ("R", "CPX;HC", "9", "N1", "A;B"),
        ]))
        # Solo la celda INPUT; la lista en la columna OUTPUT (price) es válida.
        self.assertEqual([(line, col, cell) for _, _, line, col, cell in result["inlineLists"]],
                         [(7, "frame", "CPX;HC")])

    def test_full_rectangle_merges_in_two_columns(self):
        _, prn = self.optimize(makeTable([
            ("R", "F1", "9", "N1", "B3"),
            ("R", "F1", "10", "N1", "B3"),
            ("R", "F1", "9", "N3", "B3"),
            ("R", "F1", "10", "N3", "B3"),
        ]))
        self.assertEqual(self.rules(prn), [["F1", "OR:poles_9_10", "OR:encl_N1_N3", "B3"]])

    def test_cartesian_trap_is_not_merged(self):
        _, prn = self.optimize(makeTable([
            ("R", "F1", "2", "", "A"),
            ("R", "F2", "3", "", "A"),
        ]))
        self.assertEqual(len(prn.tables[0].ruleRows), 2)

    def test_rows_separated_by_another_rule_are_not_merged(self):
        _, prn = self.optimize(makeTable([
            ("R", "F1", "2", "", "A"),
            ("R", "F1", "3", "L", "B"),
            ("R", "F1", "3", "", "A"),
        ]))
        self.assertEqual(len(prn.tables[0].ruleRows), 3)

    def test_blank_wildcard_is_not_mixed_with_a_value(self):
        _, prn = self.optimize(makeTable([
            ("R", "F1", "2", "", "A"),
            ("R", "F1", "", "", "B"),
            ("R", "", "2", "", "A"),
        ]))
        self.assertEqual(len(prn.tables[0].ruleRows), 3)

    def test_rule_covered_by_a_later_rule_with_same_output_is_removed(self):
        # La fila F1 está contenida en la fila con frame vacío y misma salida; la fila
        # intermedia (F2) no comparte entradas con F1.
        _, prn = self.optimize(makeTable([
            ("R", "F1", "2", "", "A"),
            ("R", "F2", "2", "", "B"),
            ("R", "", "2", "", "A"),
        ]))
        self.assertEqual(self.rules(prn), [["F2", "2", "", "B"], ["", "2", "", "A"]])

    def test_rule_covered_by_an_earlier_rule_with_same_output_is_removed(self):
        _, prn = self.optimize(makeTable([
            ("R", "F1", "", "", "A"),
            ("R", "F2", "", "", "B"),
            ("R", "F1", "2", "", "A"),
        ]))
        self.assertEqual(self.rules(prn), [["F1", "", "", "A"], ["F2", "", "", "B"]])

    def test_non_adjacent_rows_merge_when_rows_between_are_disjoint(self):
        _, prn = self.optimize(makeTable([
            ("R", "F1", "2", "", "A"),
            ("R", "F2", "5", "", "B"),
            ("R", "F1", "3", "", "A"),
        ]))
        self.assertEqual(self.rules(prn), [["F1", "OR:poles_2_3", "", "A"], ["F2", "5", "", "B"]])

    def test_rows_differing_in_two_columns_with_a_conflict_are_not_merged(self):
        # Mismo caso que contactor_starter_type (IEC - XT / NON-Metallic): fusionarlas
        # en una fila robaría entradas de la regla intermedia con otra salida.
        _, prn = self.optimize(makeTable([
            ("R", "XT", "CMC", "CAN", "A"),
            ("R", "XT", "None", "CAN", "B"),
            ("R", "XT", "<>None", "CAN", "C"),
            ("R", "NM", "", "CAN", "A"),
        ]))
        self.assertEqual(len(prn.tables[0].ruleRows), 4)

    def test_disabled_row_is_kept(self):
        _, prn = self.optimize(makeTable([
            ("R", "F1", "2", "", "A"),
            ("D", "F1", "4", "", "A"),
            ("R", "F1", "3", "", "A"),
        ]))
        kinds = [r.kind for r in prn.tables[0].rows]
        self.assertEqual(kinds, ["R", "D"])
        self.assertEqual(self.rules(prn), [["F1", "OR:poles_2_3", "", "A"]])

    def test_intermediate_ors_are_not_written(self):
        result, prn = self.optimize(makeTable([
            ("R", "F1", "2", "", "A"),
            ("R", "F2", "9", "", "B"),
            ("R", "F1", "3", "", "A"),
            ("R", "F2", "8", "", "C"),
            ("R", "F1", "4", "", "A"),
        ]))
        self.assertEqual([n for n, _ in result["newOrs"]], ["OR:poles_2_3_4"])

    def test_rule_with_continuation_is_not_touched(self):
        _, prn = self.optimize(makeTable([
            ("R", "F1", "2", "", "A"),
            ("R", "F1", "3", "", "A"),
            ("-", "", "", "", "more"),
        ]))
        self.assertEqual(len(prn.tables[0].ruleRows), 2)

    def test_pick_one_duplicate_rule_is_removed(self):
        result, prn = self.optimize(makeTable([
            ("R", "F1", "2", "", "A"),
            ("R", "F2", "", "", "B"),
            ("R", "F1", "2", "", "A"),
        ]))
        self.assertEqual(len(prn.tables[0].ruleRows), 2)
        self.assertEqual(result["tables"][0]["duplicatesRemoved"], 1)

    def test_pick_all_duplicates_are_kept(self):
        _, prn = self.optimize(makeTable([
            ("R", "F1", "2", "", "A"),
            ("R", "F1", "2", "", "A"),
        ], tableType="PICK ALL"))
        self.assertEqual(len(prn.tables[0].ruleRows), 2)

    def test_pick_all_distinct_values_are_merged(self):
        _, prn = self.optimize(makeTable([
            ("R", "F1", "2", "", "A"),
            ("R", "F1", "3", "", "A"),
        ], tableType="PICK ALL"))
        self.assertEqual(self.rules(prn), [["F1", "OR:poles_2_3", "", "A"]])

    def test_existing_or_with_same_values_is_reused(self):
        result, prn = self.optimize(makeTable([
            ("R", "F1", "X", "", "A"),
            ("R", "F1", "Y", "", "A"),
        ]))
        self.assertEqual(self.rules(prn), [["F1", "OR:Existing", "", "A"]])
        self.assertEqual(result["newOrs"], [])

    def test_columns_are_widened_when_or_name_does_not_fit(self):
        _, prn = self.optimize(makeTable([
            ("R", "F1", "2", "N1", "A"),
            ("R", "F1", "3", "N1", "A"),
            ("R", "F2", "4", "N3", "B"),
        ]))
        table = prn.tables[0]
        self.assertEqual(table.misaligned, 0)
        self.assertEqual(self.rules(prn), [["F1", "OR:poles_2_3", "N1", "A"],
                                           ["F2", "4", "N3", "B"]])

    def test_skip_tables(self):
        result, prn = self.optimize(makeTable([
            ("R", "F1", "2", "", "A"),
            ("R", "F1", "3", "", "A"),
        ]), skipTables=["tbl"])
        self.assertEqual(len(prn.tables[0].ruleRows), 2)
        self.assertIsNotNone(result["tables"][0]["skipped"])

# ===================================================================================================

class TestVerifier(PrnTestCase):

    def load(self, name, text):
        with open(self.path(name), "w", encoding="latin-1", newline="") as fh:
            fh.write(text)
        return BMMT.PrnFile(self.path(name))

    def test_verifier_detects_cartesian_merge(self):
        original = self.load("a.prn", makeTable([
            ("R", "F1", "2", "", "A"),
            ("R", "F2", "3", "", "A"),
            ("R", "", "", "", "Z"),
        ]))
        bad = self.load("b.prn", HEADER.replace("X;Y", "X;Y\r\nDEFINE OR:OR:f=F1;F2\r\n"
                                                "DEFINE OR:OR:p=2;3") + makeTable([
            ("R", "OR:f", "OR:p", "", "A"),
            ("R", "", "", "", "Z"),
        ])[len(HEADER):])
        _, mismatches = BMMT.verifyTable(original.tables[0], bad.tables[0], original.ors, bad.ors)
        self.assertTrue(mismatches)

    def test_verifier_detects_priority_change(self):
        original = self.load("a.prn", makeTable([
            ("R", "F1", "2", "", "A"),
            ("R", "F1", "", "", "B"),
        ]))
        swapped = self.load("b.prn", makeTable([
            ("R", "F1", "", "", "B"),
            ("R", "F1", "2", "", "A"),
        ]))
        _, mismatches = BMMT.verifyTable(original.tables[0], swapped.tables[0],
                                         original.ors, swapped.ors)
        self.assertTrue(mismatches)

# ===================================================================================================

class TestRealFiles(PrnTestCase):

    def test_real_files_optimize_without_behavior_change(self):
        for source in sorted(glob.glob(os.path.join(PRNS, "INPUTS*"))):
            with self.subTest(file=os.path.basename(source)):
                result, report = BMMT.optimizePrn(source, self.path("out.prn"))
                for index, tests, mismatches in result["verification"]:
                    self.assertEqual(mismatches, [], report)

# ===================================================================================================

if __name__ == "__main__":
    unittest.main()
