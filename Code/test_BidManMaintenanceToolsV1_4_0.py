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
REAL_PRODUCT = os.path.join(PRNS, "REALPRODUCT")

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

    def optimizeWithGlobals(self, text, globalsText):
        with open(self.path("GLOBALS.PRN"), "w", encoding="latin-1", newline="") as fh:
            fh.write(globalsText)
        return self.optimize(text, globalsPath=self.path("GLOBALS.PRN"))

    def test_global_or_is_not_treated_as_a_literal(self):
        # Global Y = Y;YN. Fusionar "Y" con "N" como literales perdería YN.
        result, prn = self.optimizeWithGlobals(makeTable([
            ("R", "F1", "Y", "", "A"),
            ("R", "F1", "N", "", "A"),
        ]), "DEFINE DELIMITER:;\r\nDEFINE OR:Y=Y;YN\r\n")
        name = self.rules(prn)[0][1]
        self.assertEqual(set(prn.ors[name]), {"Y", "YN", "N"})
        self.assertTrue(result["verification"])

    def test_global_ors_are_not_written_and_names_do_not_collide(self):
        result, prn = self.optimizeWithGlobals(makeTable([
            ("R", "F1", "2", "", "A"),
            ("R", "F1", "3", "", "A"),
        ]), "DEFINE DELIMITER:;\r\nDEFINE OR:OR:poles_2_3=7;8\r\n")
        self.assertEqual(self.rules(prn), [["F1", "OR:poles_2_3_2", "", "A"]])
        self.assertNotIn("OR:poles_2_3", prn.ors)
        self.assertNotIn("OR:poles_2_3", result["unusedOrs"])

    def test_global_or_with_same_values_is_reused(self):
        result, prn = self.optimizeWithGlobals(makeTable([
            ("R", "F1", "2", "", "A"),
            ("R", "F1", "3", "", "A"),
        ]), "DEFINE DELIMITER:;\r\nDEFINE OR:Two3=2;3\r\n")
        self.assertEqual(self.rules(prn), [["F1", "Two3", "", "A"]])
        self.assertEqual(result["newOrs"], [])

    def test_local_or_wins_over_global_with_same_name(self):
        result, prn = self.optimizeWithGlobals(makeTable([("R", "F1", "X", "", "A")]),
                                               "DEFINE DELIMITER:;\r\nDEFINE OR:OR:Existing=Q\r\n")
        self.assertEqual(prn.ors["OR:Existing"], ["X", "Y"])
        self.assertEqual(result["shadowedGlobalOrs"], ["OR:Existing"])

    def test_skip_tables(self):
        result, prn = self.optimize(makeTable([
            ("R", "F1", "2", "", "A"),
            ("R", "F1", "3", "", "A"),
        ]), skipTables=["tbl"])
        self.assertEqual(len(prn.tables[0].ruleRows), 2)
        self.assertIsNotNone(result["tables"][0]["skipped"])

    def test_large_merges_are_split_in_blocks(self):
        rows = [("R", "F1", str(p), "", "A") for p in range(1, 6)]
        result, prn = self.optimize(makeTable(rows), maxOrValues=2)
        self.assertEqual(len(prn.tables[0].ruleRows), 3)
        self.assertTrue(all(len(v) <= 2 for _, v in result["newOrs"]))

    def test_large_merges_are_split_in_blocks_pick_all(self):
        rows = [("R", "F1", str(p), "", "A") for p in range(1, 6)]
        _, prn = self.optimize(makeTable(rows, tableType="PICK ALL"), maxOrValues=2)
        self.assertEqual(len(prn.tables[0].ruleRows), 3)

# ===================================================================================================

def prnText(defines, rows):
    # PRN con las líneas DEFINE OR dadas y la tabla de prueba de makeTable.
    head = "DEFINE DELIMITER:;\r\n" + "".join(f"DEFINE OR:{d}\r\n" for d in defines)
    return head + makeTable(rows)[len(HEADER):]

class TestConsolidation(PrnTestCase):

    def project(self, files, globalsDefines, selected=None, **options):
        paths = {}
        for name, text in list(files.items()) + [("GLOBALS.PRN", prnText(globalsDefines, []))]:
            paths[name] = self.path(name)
            with open(paths[name], "w", encoding="latin-1", newline="") as fh:
                fh.write(text)
        out = self.path("out")
        os.makedirs(out)
        chosen = [paths[n] for n in (selected or files)]
        project = BMMT.optimizeProject(chosen, out, globalsPath=paths["GLOBALS.PRN"],
                                       projectPaths=[paths[n] for n in files], **options)
        for path in chosen:
            result = project["files"][path]
            self.assertNotIn("error", result)
            for _, _, mismatches in result["verification"]:
                self.assertEqual(mismatches, [])
        written = {n: BMMT.PrnFile(os.path.join(out, n)) for n in (selected or files)}
        globalsOut = BMMT.PrnFile(project["globalsOut"] or paths["GLOBALS.PRN"])
        return project, written, globalsOut, {n: project["files"][paths[n]] for n in written}

    def test_local_copy_of_a_global_or_is_removed(self):
        _, written, _, results = self.project(
            {"a.prn": prnText(["G1=A;B"], [("R", "G1", "1", "", "X")])}, ["G1=A;B"])
        self.assertNotIn("G1", written["a.prn"].ors)
        self.assertEqual(self.rules(written["a.prn"]), [["G1", "1", "", "X"]])
        self.assertEqual(results["a.prn"]["consolidation"]["sameAsGlobal"], ["G1"])

    def test_local_or_with_global_values_uses_the_global_name(self):
        _, written, _, results = self.project(
            {"a.prn": prnText(["Loc=B;A"], [("R", "Loc", "1", "", "X"),
                                            ("R", "<>Loc", "2", "", "Y")])}, ["G1=A;B"])
        self.assertNotIn("Loc", written["a.prn"].ors)
        self.assertEqual(self.rules(written["a.prn"]), [["G1", "1", "", "X"],
                                                        ["<>G1", "2", "", "Y"]])
        self.assertEqual(results["a.prn"]["consolidation"]["renamedToGlobal"], [("Loc", "G1")])

    def test_or_repeated_in_two_files_moves_to_globals(self):
        project, written, globalsOut, _ = self.project({
            "a.prn": prnText(["Rep=P;Q"], [("R", "Rep", "1", "", "X")]),
            "b.prn": prnText(["Rep=P;Q"], [("R", "Rep", "2", "", "Y")]),
        }, ["G1=A;B"])
        self.assertEqual(globalsOut.ors["Rep"], ["P", "Q"])
        self.assertEqual(project["newGlobals"], [("Rep", ["P", "Q"])])
        for name in ("a.prn", "b.prn"):
            self.assertNotIn("Rep", written[name].ors)
        self.assertEqual(globalsOut.ors["G1"], ["A", "B"])

    def test_repeated_or_counts_files_that_are_not_selected(self):
        project, written, globalsOut, _ = self.project({
            "a.prn": prnText(["Rep=P;Q"], [("R", "Rep", "1", "", "X")]),
            "b.prn": prnText(["Rep=P;Q"], [("R", "Rep", "2", "", "Y")]),
        }, ["G1=A;B"], selected=["a.prn"])
        self.assertIn("Rep", globalsOut.ors)
        self.assertNotIn("Rep", written["a.prn"].ors)

    def test_global_takes_the_hand_written_name_over_an_optimizer_name(self):
        # b.prn genera OR:poles_1_2 al fusionar; a.prn ya tenía "Hand" con esos valores.
        project, written, globalsOut, _ = self.project({
            "a.prn": prnText(["Hand=1;2"], [("R", "F9", "Hand", "", "X")]),
            "b.prn": prnText([], [("R", "F1", "1", "", "A"), ("R", "F1", "2", "", "A")]),
            "c.prn": prnText([], [("R", "F1", "1", "", "A"), ("R", "F1", "2", "", "A")]),
        }, ["G1=A;B"])
        self.assertEqual(project["newGlobals"], [("Hand", ["1", "2"])])
        self.assertEqual(self.rules(written["b.prn"]), [["F1", "Hand", "", "A"]])
        self.assertNotIn("OR:poles_1_2", written["b.prn"].ors)

    def test_or_in_only_one_file_stays_local(self):
        project, written, _, _ = self.project(
            {"a.prn": prnText(["Solo=P;Q"], [("R", "Solo", "1", "", "X")])}, ["G1=A;B"])
        self.assertEqual(project["newGlobals"], [])
        self.assertIsNone(project["globalsOut"])
        self.assertEqual(written["a.prn"].ors["Solo"], ["P", "Q"])

    def test_new_global_never_takes_a_name_used_as_literal_elsewhere(self):
        # En c.prn "Rep" es un literal; si "Rep" fuera global, c.prn cambiaría.
        project, written, globalsOut, _ = self.project({
            "a.prn": prnText(["Rep=P;Q"], [("R", "Rep", "1", "", "X")]),
            "b.prn": prnText(["Rep=P;Q"], [("R", "Rep", "2", "", "Y")]),
            "c.prn": prnText([], [("R", "Rep", "3", "", "Z")]),
        }, ["G1=A;B"], selected=["a.prn", "b.prn"])
        self.assertNotIn("Rep", globalsOut.ors)
        [(name, values)] = project["newGlobals"]
        self.assertEqual(values, ["P", "Q"])
        self.assertEqual(self.rules(written["a.prn"]), [[name, "1", "", "X"]])

    def test_same_name_different_values_is_left_alone(self):
        _, written, globalsOut, results = self.project(
            {"a.prn": prnText(["G1=A;C"], [("R", "G1", "1", "", "X")])}, ["G1=A;B"])
        self.assertEqual(written["a.prn"].ors["G1"], ["A", "C"])
        self.assertEqual(globalsOut.ors["G1"], ["A", "B"])
        self.assertEqual(results["a.prn"]["consolidation"]["conflictWithGlobal"], ["G1"])

    def test_exact_duplicate_line_in_a_file_is_removed(self):
        _, written, _, _ = self.project(
            {"a.prn": prnText(["Solo=P;Q", "Solo=P;Q"], [("R", "Solo", "1", "", "X")])},
            ["G1=A;B"])
        self.assertEqual(written["a.prn"].orCount["Solo"], 1)

    def test_or_used_in_output_column_is_not_renamed(self):
        _, written, _, results = self.project(
            {"a.prn": prnText(["Loc=A;B"], [("R", "Loc", "1", "", "Loc")])}, ["G1=A;B"])
        self.assertEqual(written["a.prn"].ors["Loc"], ["A", "B"])
        self.assertEqual(results["a.prn"]["consolidation"]["kept"], ["Loc"])

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

    def test_real_product_files_round_trip_byte_for_byte(self):
        files = sorted(f for f in glob.glob(os.path.join(REAL_PRODUCT, "*"))
                       if f.lower().endswith(".prn"))
        if not files:
            self.skipTest(f"no hay PRNs en {REAL_PRODUCT}")
        for source in files:
            with self.subTest(file=os.path.basename(source)):
                target = self.path("rt.prn")
                BMMT.PrnFile(source).write(target)
                with open(source, "rb") as a, open(target, "rb") as b:
                    self.assertEqual(a.read(), b.read())

# ===================================================================================================

class TestMenu(unittest.TestCase):

    def test_parse_selection(self):
        import OptimizePrnMenu as menu
        self.assertEqual(menu.parseSelection("all", 3), [0, 1, 2])
        self.assertEqual(menu.parseSelection("1,3", 5), [0, 2])
        self.assertEqual(menu.parseSelection("2-4, 1", 5), [1, 2, 3, 0])
        self.assertEqual(menu.parseSelection("3,3", 5), [2])
        self.assertIsNone(menu.parseSelection("0", 5))
        self.assertIsNone(menu.parseSelection("6", 5))
        self.assertIsNone(menu.parseSelection("x", 5))
        self.assertIsNone(menu.parseSelection("", 5))

# ===================================================================================================

if __name__ == "__main__":
    unittest.main()
