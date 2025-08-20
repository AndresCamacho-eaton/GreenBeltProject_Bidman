import BidManMaintenanceToolsV1_3_3 as BMMT

workingFile = \
BMMT.PrnDoctor("C:\\Users\\E0803344\\OneDrive - Eaton\\Documents\\JavierCamacho\\" + \
               "ENCLOSC_PRNS\\PRNS\\inputs.prn")

workingFile.ReadPRN()

for tbl in workingFile.tables:

    # --- 140825 -------------------------------------------------------------------------
    
    # Tables must first be populated line by line while reading the PRN file. Therefore,
    # the DataFrame representation of the table should be created only after the table
    # has been fully populated.

    tbl.BuildTable()
    
    # ------------------------------------------------------------------------------------

    print(f"Type of table: {tbl.typeOfTable}")
    print(f"Columns: {tbl.columns}")
    print(f"Type of column: {tbl.typeOfColumn}")
    print(f"Data type: {tbl.dataType}")
    print(f"Name: {tbl.name}")
   
   
    print(f"Table as a DataFrame:\n{tbl.table}\n")

    #print("----------------------")

    # Get a list representation of the column with the output of the table.
    #nameOfTheOutputColumn = tbl.columns[len(tbl.columns) - 1]
    #print(f"Output column name: {nameOfTheOutputColumn}")
    #print(tbl.table[nameOfTheOutputColumn].tolist())

    #print("----------------------")


#050625

#workingFile.WritePRN("C:\\Users\\E0803344\\OneDrive - Eaton\\Documents\\JavierCamacho\\" + \
#                     "ENCLOSC_PRNS\\PRNS\\inputsproofofconcept_out_150725.prn")