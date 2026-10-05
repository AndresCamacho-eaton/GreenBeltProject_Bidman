#import BidManMaintenanceToolsV1_3_1 as BMMT
#import BidManMaintenanceToolsV1_3_2 as BMMT
#import BidManMaintenanceToolsV1_3_3 as BMMT

import os
import sys

import BidManMaintenanceToolsV1_4_0 as BMMT

"""
    Uso:
        python MainPrnReader.py                         (usa los archivos por defecto de abajo)
        python MainPrnReader.py entrada.prn salida.prn

    Escribe el PRN optimizado, un reporte <salida>.report.txt, y verifica cada tabla
    contra la original. No modifica el archivo de entrada.
"""

HERE = os.path.dirname(os.path.abspath(__file__))
PRNS = os.path.join(HERE, "..", "ENCLOSC_PRNS", "PRNS")

inputPath = sys.argv[1] if len(sys.argv) > 1 else os.path.join(PRNS, "INPUTSProofOfConcept.prn")
outputPath = sys.argv[2] if len(sys.argv) > 2 else os.path.join(PRNS, "optimized_output3.prn")

print('Reading, optimizing and verifying PRN file . . .')

result, report = BMMT.optimizePrn(
    inputPath,
    outputPath,
    reportPath=outputPath + ".report.txt",
    skipTables=[],              # nombres (Description) o índices de tablas a no tocar
    optimizePickAll=True,       # en PICK ALL solo se fusionan valores distintos
    removeDuplicateRules=True,  # PICK ONE: borra reglas idénticas a una regla anterior
    removeUnusedOrs=False,      # pendiente confirmar si los ORs se usan desde otros archivos
)

print(report)

failed = [index for index, _, mismatches in result["verification"] if mismatches]
if failed:
    print(f'VERIFICATION FAILED in tables {failed}. Do not use {outputPath}.')
    sys.exit(1)

if result["inlineLists"]:
    print(f'{len(result["inlineLists"])} INPUT cells have a value;value list instead of an OR. '
          f'Do not use {outputPath}.')
    sys.exit(1)

print('Done!')
