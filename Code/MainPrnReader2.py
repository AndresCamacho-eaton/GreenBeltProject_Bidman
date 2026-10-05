import os
import sys

import BidManMaintenanceToolsV1_4_0 as BMMT

# Muestra la estructura de cada tabla de un PRN (sin optimizar nada).
#   python MainPrnReader2.py [archivo.prn]

HERE = os.path.dirname(os.path.abspath(__file__))
path = sys.argv[1] if len(sys.argv) > 1 else \
    os.path.join(HERE, "..", "ENCLOSC_PRNS", "PRNS", "INPUTSProofOfConcept.PRN")

workingFile = BMMT.PrnFile(path)

print(f"ORs: {len(workingFile.ors)}")

for tbl in workingFile.tables:

    kinds = {}
    for row in tbl.rows:
        kinds[row.kind] = kinds.get(row.kind, 0) + 1

    print(f"[{tbl.index}] {tbl.name}  ({tbl.typeOfTable}, línea {tbl.lineNumber})")
    print(f"    Columns:   {tbl.columns}")
    print(f"    I/O:       {tbl.io}")
    print(f"    Data type: {tbl.dataTypes}")
    print(f"    Rows:      {kinds}")
