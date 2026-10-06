"""
    Pruebas de BidManMaintenanceToolsV1_4_0.

    Ejecutar desde la carpeta Code:  python -m unittest test_BidManMaintenanceToolsV1_4_0 -v
"""

import contextlib
import glob
import io
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
        # Los PRN de prueba (datos de producto) no están en el repositorio; solo en local.
        files = sorted(glob.glob(os.path.join(PRNS, "INPUTS*")))
        if not files:
            self.skipTest(f"no hay PRNs INPUTS* en {PRNS}")
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

    def test_skip_tables_ignores_case(self):
        result, prn = self.optimize(makeTable([
            ("R", "F1", "2", "", "A"),
            ("R", "F1", "3", "", "A"),
        ]), skipTables=["TBL"])
        self.assertEqual(len(prn.tables[0].ruleRows), 2)
        self.assertEqual(result["tables"][0]["skipped"], "tabla excluida")

    def test_output_values_keep_their_exact_text(self):
        # Listas de ATTR_PICK y "@" (valor por defecto) en OUTPUT no se tocan al fusionar.
        result, prn = self.optimize(makeTable([
            ("R", "F1", "2", "", "@A;B"),
            ("R", "F2", "2", "", "@A;B"),
            ("R", "F3", "2", "", "C;@D"),
        ]))
        self.assertEqual([r[-1] for r in self.rules(prn)], ["@A;B", "C;@D"])
        self.assertEqual(result["changedOutputs"], [])
        self.assertEqual(result["inlineLists"], [])

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
        # En c.prn "Rep" es un literal; si "Rep" fuera global, c.prn cambiaría. No se inventa
        # otro nombre: los ORs se quedan locales.
        project, written, globalsOut, results = self.project({
            "a.prn": prnText(["Rep=P;Q"], [("R", "Rep", "1", "", "X")]),
            "b.prn": prnText(["Rep=P;Q"], [("R", "Rep", "2", "", "Y")]),
            "c.prn": prnText([], [("R", "Rep", "3", "", "Z")]),
        }, ["G1=A;B"], selected=["a.prn", "b.prn"])
        self.assertNotIn("Rep", globalsOut.ors)
        self.assertEqual(project["newGlobals"], [])
        self.assertEqual(written["a.prn"].ors["Rep"], ["P", "Q"])
        self.assertEqual(self.rules(written["a.prn"]), [["Rep", "1", "", "X"]])
        self.assertEqual(results["a.prn"]["consolidation"]["notGlobal"], ["Rep"])

    def test_optimizer_made_ors_do_not_move_to_globals(self):
        # b.prn y c.prn generan el mismo OR al fusionar, sin nombre escrito por una persona.
        project, written, _, _ = self.project({
            "b.prn": prnText([], [("R", "F1", "1", "", "A"), ("R", "F1", "2", "", "A")]),
            "c.prn": prnText([], [("R", "F1", "1", "", "A"), ("R", "F1", "2", "", "A")]),
        }, ["G1=A;B"])
        self.assertEqual(project["newGlobals"], [])
        for name in ("b.prn", "c.prn"):
            [rule] = self.rules(written[name])
            self.assertEqual(written[name].ors[rule[1]], ["1", "2"])

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

    def test_output_cell_with_an_or_name_is_a_literal_and_is_not_renamed(self):
        # Un OUTPUT nunca usa un OR: "Loc" ahí es un valor devuelto. Se renombra solo el INPUT.
        _, written, _, results = self.project(
            {"a.prn": prnText(["Loc=A;B"], [("R", "Loc", "1", "", "Loc")])}, ["G1=A;B"])
        self.assertNotIn("Loc", written["a.prn"].ors)
        self.assertEqual(self.rules(written["a.prn"]), [["G1", "1", "", "Loc"]])
        self.assertEqual(results["a.prn"]["consolidation"]["renamedToGlobal"], [("Loc", "G1")])
        self.assertEqual(results["a.prn"]["changedOutputs"], [])

    def test_excluded_table_is_never_renamed(self):
        # "Loc" tiene los valores de G1, pero la tabla está excluida: no se toca y Loc queda local.
        text = prnText(["Loc=B;A"], [("R", "Loc", "1", "", "X")])
        _, written, _, results = self.project({"a.prn": text}, ["G1=A;B"], skipTables=["TBL"])
        self.assertEqual(self.rules(written["a.prn"]), [["Loc", "1", "", "X"]])
        self.assertEqual(written["a.prn"].ors["Loc"], ["B", "A"])
        self.assertEqual(results["a.prn"]["consolidation"]["kept"], ["Loc"])

    def test_table_progress_is_reported_for_every_table(self):
        calls = []
        self.project({"a.prn": prnText([], [("R", "F1", "1", "", "X")])}, ["G1=A;B"],
                     tableProgress=lambda *args: calls.append(args))
        self.assertEqual(calls, [("optimize", 1, 1, "tbl"), ("verify", 1, 1, "tbl")])

    def test_or_name_as_output_literal_elsewhere_does_not_block_a_global(self):
        project, written, globalsOut, _ = self.project({
            "a.prn": prnText(["Rep=P;Q"], [("R", "Rep", "1", "", "X")]),
            "b.prn": prnText(["Rep=P;Q"], [("R", "Rep", "2", "", "Y")]),
            "c.prn": prnText([], [("R", "F1", "3", "", "Rep")]),
        }, ["G1=A;B"], selected=["a.prn", "b.prn"])
        self.assertEqual(project["newGlobals"], [("Rep", ["P", "Q"])])
        self.assertNotIn("Rep", written["a.prn"].ors)

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

    def test_changed_output_value_is_detected(self):
        original = self.load("a.prn", makeTable([("R", "F1", "2", "", "@A;B")]))
        changed = self.load("b.prn", makeTable([("R", "F1", "2", "", "A;B")]))
        self.assertEqual(BMMT.changedOutputs(original.tables[0], original.tables[0]), [])
        self.assertEqual(BMMT.changedOutputs(original.tables[0], changed.tables[0]),
                         [(7, "R", ("A;B",))])

    def test_copied_file_is_checked_against_the_new_globals(self):
        # "Rep" es un literal en c.prn; si GLOBALS.PRN nuevo lo definiera como OR, c.prn cambiaría.
        c = self.path("c.prn")
        self.load("c.prn", prnText([], [("R", "Rep", "1", "", "X"), ("R", "", "", "", "Z")]))
        self.load("old.PRN", prnText(["G1=A;B"], []))
        self.load("same.PRN", prnText(["G1=A;B", "Other=P;Q"], []))
        self.load("bad.PRN", prnText(["G1=A;B", "Rep=P;Q"], []))
        _, mismatches = BMMT.verifyWithNewGlobals(c, self.path("old.PRN"), self.path("same.PRN"))
        self.assertEqual(mismatches, [])
        _, mismatches = BMMT.verifyWithNewGlobals(c, self.path("old.PRN"), self.path("bad.PRN"))
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
        files = sorted(glob.glob(os.path.join(PRNS, "INPUTS*")))
        if not files:
            self.skipTest(f"no hay PRNs INPUTS* en {PRNS}")
        for source in files:
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

    def test_default_excluded_files_ignore_case(self):
        import OptimizePrnMenu as menu
        with tempfile.TemporaryDirectory() as folder:
            for name in ("a.prn", "pluginframework.PRN", "ReEval.prn", "GLOBALS.PRN"):
                with open(os.path.join(folder, name), "w") as fh:
                    fh.write("")
            original, menu.ask = menu.ask, lambda prompt, default="": "all"
            try:
                # chooseFiles imprime la lista de archivos; no debe ensuciar la salida de las pruebas.
                with contextlib.redirect_stdout(io.StringIO()):
                    files, _, project, skipped = menu.chooseFiles(folder)
            finally:
                menu.ask = original
            self.assertEqual([os.path.basename(f) for f in files], ["a.prn"])
            self.assertEqual(skipped, ["pluginframework.PRN", "ReEval.prn"])
            # Siguen en el proyecto para que los ORs globales nuevos no los afecten.
            self.assertEqual(len(project), 3)

    def test_unoptimized_files_and_pik_are_copied_unchanged(self):
        import OptimizePrnMenu as menu
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as out:
            texts = {"a.prn": makeTable([("R", "F1", "2", "", "A")]),
                     "b.PRN": makeTable([("R", "F2", "2", "", "B")]),
                     "c.prn": makeTable([("R", "F3", "2", "", "C")]),
                     "ENCLOSC.PIK": "pik data\r\n",
                     "Translations.XML": "<xml/>\r\n",
                     "notes.txt": "not copied\r\n"}
            for name, text in texts.items():
                with open(os.path.join(folder, name), "w", encoding="latin-1", newline="") as fh:
                    fh.write(text)
            paths = [os.path.join(folder, n) for n in ("a.prn", "b.PRN", "c.prn")]
            # a.prn se optimizó bien, c.prn falló, b.PRN no se eligió.
            with contextlib.redirect_stdout(io.StringIO()):
                copied = menu.copyUnoptimized(folder, out, paths, [paths[0], paths[2]], [paths[2]],
                                              None, None)
            self.assertEqual(copied, [("b.PRN", None), ("c.prn", None), ("ENCLOSC.PIK", None),
                                      ("Translations.XML", None)])
            for name, _ in copied:
                with open(os.path.join(folder, name), "rb") as a, \
                     open(os.path.join(out, name), "rb") as b:
                    self.assertEqual(a.read(), b.read())
            self.assertFalse(os.path.exists(os.path.join(out, "a.prn")))
            self.assertFalse(os.path.exists(os.path.join(out, "notes.txt")))

    def test_original_globals_is_copied_when_no_new_one_was_written(self):
        import OptimizePrnMenu as menu
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as out:
            globalsPath = os.path.join(folder, "GLOBALS.PRN")
            with open(globalsPath, "w", encoding="latin-1", newline="") as fh:
                fh.write(prnText(["G1=A;B"], []))
            with contextlib.redirect_stdout(io.StringIO()):
                copied = menu.copyUnoptimized(folder, out, [], [], [], globalsPath, None)
            self.assertEqual(copied, [("GLOBALS.PRN", None)])
            with open(globalsPath, "rb") as a, open(os.path.join(out, "GLOBALS.PRN"), "rb") as b:
                self.assertEqual(a.read(), b.read())

            # Con un GLOBALS.PRN nuevo en la salida, el original no lo reemplaza.
            newGlobals = os.path.join(out, "GLOBALS.PRN")
            with open(newGlobals, "w", encoding="latin-1", newline="") as fh:
                fh.write(prnText(["G1=A;B", "New=P;Q"], []))
            with contextlib.redirect_stdout(io.StringIO()):
                copied = menu.copyUnoptimized(folder, out, [], [], [], globalsPath, newGlobals)
            self.assertEqual(copied, [])
            self.assertIn("New", BMMT.PrnFile(newGlobals).ors)

    def test_welcome_art_is_colored_ascii(self):
        import re
        import OptimizePrnMenu as menu
        lines = menu.welcomeLines("\n>_< ==\nab\n", "\nggg ww\n", color=True)
        green, white = "\033[38;2;61;245;140m", "\033[38;2;238;242;245m"
        self.assertEqual(lines, [green + ">_<" + "\033[0m " + white + "==\033[0m",
                                 "ab    "])
        # Sin color: el mismo dibujo en texto plano, todas las líneas del mismo ancho.
        self.assertEqual(menu.welcomeLines("\n>_< ==\nab\n", "", color=False), [">_< ==", "ab    "])

        # El dibujo real: solo ASCII, y cada carácter visible tiene color en COLORS.
        from welcome_art import ART, COLORS
        art, colors = ART.strip("\n").split("\n"), COLORS.strip("\n").split("\n")
        self.assertEqual(len(art), len(colors))
        self.assertTrue(ART.isascii())
        for line, mask in zip(art, colors):
            for x, ch in enumerate(line):
                if ch != " ":
                    self.assertIn(mask[x:x + 1], menu.ART_COLORS, f"sin color: {line!r} col {x}")
        plain = [re.sub("\033\\[[0-9;]*m", "", l) for l in menu.welcomeLines(ART, COLORS)]
        self.assertEqual(plain, menu.welcomeLines(ART, COLORS, color=False))

    def test_live_line_rewrites_in_place_and_clears(self):
        import OptimizePrnMenu as menu
        live = menu.LiveLine()
        live.enabled = True
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            live.show("working on table LongName 1/2")
            live.show("working on table T 2/2")
            live.clear()
        text = buffer.getvalue()
        self.assertNotIn("\n", text)
        self.assertTrue(text.endswith("\r"))
        # La segunda línea, más corta, tapa con espacios lo que quedaba de la primera.
        second = text.split("\r")[2]
        self.assertTrue(second.endswith(" " * (len("working on table LongName 1/2") -
                                               len("working on table T 2/2"))))

# ===================================================================================================

if __name__ == "__main__":
    unittest.main()
