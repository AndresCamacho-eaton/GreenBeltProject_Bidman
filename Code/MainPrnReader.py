#import BidManMaintenanceToolsV1.1.0 as BMMT
#import BidManMaintenanceToolsV1_2_0 as BMMT
#import BidManMaintenanceToolsV1_2_1 as BMMT
#import BidManMaintenanceToolsV1_3_1 as BMMT
#import BidManMaintenanceToolsV1_3_2 as BMMT

import BidManMaintenanceToolsV1_3_3 as BMMT

#workingFile = \
#BMMT.PrnDoctor("C:\\Users\\E0803344\\OneDrive - Eaton\\Documents\\JavierCamacho\\" + \
#               "ENCLOSC_PRNS\\PRNS\\inputsproofofconcept.prn")


workingFile = \
BMMT.PrnDoctor("C:\\Users\\E0803344\\OneDrive - Eaton\\Documents\\JavierCamacho\\" + \
               "ENCLOSC_PRNS\\PRNS\\inputsproofofconcept3.prn")

"""
    TODO

    La solución desarrollada para la clase LogicalRules funciona con el archivo de entrada
    inputsproofofconcept pero no con el archivo inputs. [Resuelto]

"""

#print(workingFile.pathAndNameOfTheFile)

testOptimization = \
BMMT.PrnDoctor("..\\ENCLOSC_PRNS\\PRNS\\inputsproofofconcept.prn")
testOptimization.OptimizationOne()
# workingFile.ReadPRN()

#workingFile.EqualTokensDetector()

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
for tbl in workingFile.tables:

    tbl.BuildTable()

    print(f"Type of table: {tbl.typeOfTable}")
    print(f"Columns: {tbl.columns}")
    print(f"Type of column: {tbl.typeOfColumn}")
    print(f"Data type: {tbl.dataType}")
    print(f"Name: {tbl.name}")
   
    print()
   
    #print("Rows:")
    #for r in tbl.rows:
    #    print(r)
   
    print()

    print(f"Table as a DataFrame:\n{tbl.table}\n")

    print()

    print(f"Columns: {tbl.columns}")
    print(f"Columns: {tbl.table.columns}")

    print("----------------------")

    print(tbl.table.loc[5,'disconnect'])


#050625

#workingFile.WritePRN("C:\\Users\\E0803344\\OneDrive - Eaton\\Documents\\JavierCamacho\\" + \
#                     "ENCLOSC_PRNS\\PRNS\\inputsproofofconcept_out_150725.prn")
