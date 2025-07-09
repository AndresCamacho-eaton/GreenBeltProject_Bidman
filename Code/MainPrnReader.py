#import BidManMaintenanceToolsV1.1.0 as BMMT

#import BidManMaintenanceToolsV1_2_0 as BMMT

import BidManMaintenanceToolsV1_2_1 as BMMT
# workingFile = \
# BMMT.PrnDoctor("C:\\Users\\E0803344\\OneDrive - Eaton\\Documents\\JavierCamacho\\" + \
#                "ENCLOSC_PRNS\\PRNS\\inputsproofofconcept.prn")

"""
    TO DO:

    La solución desarrollada para la clase LogicalRules funciona con el archivo de entrada
    inputsproofofconcept pero no con el archivo inputs. [Resuelto]

"""

#print(workingFile.pathAndNameOfTheFile)

testOptimization = \
BMMT.PrnDoctor("..\\ENCLOSC_PRNS\\PRNS\\inputsproofofconcept.prn")
testOptimization.OptimizationOne()
# workingFile.ReadPRN()

#print(workingFile.getDelimiters)
#print(workingFile.logicalRules)

#c = 0
#for lr in workingFile.logicalRules:

#    print(lr.variableName)
#    print(lr.type)
#    print(lr.listOfValues)
#    print("------------------------------")
#    c += 1

    #print(lr.variableName)
    #print(lr.type)
    #print(lr.listOfValues)

#print(c)

#c = 0
#for tbl in workingFile.tables:

#    print(tbl.typeOfTable)
#    print(tbl.columns)
#    print(tbl.typeOfColumn)
#    print(tbl.dataType)
#    print(tbl.name)
    #print(tbl.rows)
    #for r in tbl.rows:
    #    print(r)
    #print("\n")

#    c += 1

#print(c)

#050625

# workingFile.WritePRN("C:\\Users\\E0803344\\OneDrive - Eaton\\Documents\\JavierCamacho\\" + \
#                      "ENCLOSC_PRNS\\PRNS\\inputsproofofconcept_out.prn")