import pandas as pd
import re, json, time
from collections import defaultdict, Counter

"""
    Como primer paso el algoritmo debe ser capaz de detectar subconjuntos de renglones en donde al menos tres columnas tengan
    valores iguales. Los renglones en donde una columna tenga valor null o este vacía se consideran también como valores iguales.
"""
"""
    Javi Git Masterclass 240625
"""

"""
    290425

    Los ORs en su mayoría se quedan iguales, pero hay que detectar los que no se están usando y borrarlos.

    El algoritmo ignorará los renglones que comiencen con la palabra reservada DEFINE.

    Cuando se detecte las palabras TABLE TYPE: PICK ONE o PICK ALL, estamos frente a una tabla.

    Dentro del cuerpo de una tabla, la primer columna contendrá las letras D, R o C, que indican el tipo de renglón.
    D = Disabled, R = Rule, C = Comment.

    Los Disabled los ignoramos, y nos concentramos en optimizar los renglones que comienzan con R.

    La segunda columna, típicamente contiene el nombre de la tabla debajo de el nombre de columna description

    Dentro de una tabla las columnas están separadas por n espacios en blanco, donde n está determinado por el valor más largo de columna

    Los primeros cuatro renglones de toda tabla contienen la misma estructura, a saber:

    1. El tipo de tabla
    2. El nombre de las columnas, en donde el nombre de la primer columna corresponde al nombre de la tabla
    3. Indicador del tipo de columna. Las columnas pueden ser solo de dos tipos: input y output.
    4. Tipo de dato esperado en la columna. ALPHA, NUM, FLOAT, REAl, RANGE, etc.

    080525

    Hay una tabla que se llama Global ORs.


"""

class LogicalRules:

    def __init__(self):

        self._variableName = None
        self._type = None
        self._listOfValues = []
        
    @property
    def variableName(self):
        return self._variableName
        
    @property
    def type(self):
        return self._type
    
    @property
    def listOfValues(self):
        return self._listOfValues
    
    @variableName.setter
    def variableName(self, variableName):
        self._variableName = variableName
        
    @type.setter
    def type(self, type):
        self._type = type
    
    @listOfValues.setter
    def listOfValues(self, listOfValues):
        self._listOfValues = listOfValues

    # -----------------------------------------------------------------------------------------------

    def Tokenizer(self, string, delimiter):
        
        tokens = []
            
        while(string.find(delimiter)!=-1):
            
            string = string.partition(delimiter)
                            
            tokens.append(string[0])
            
            string = string[2]
        
        tokens.append(string)
        
        return tokens

    # -----------------------------------------------------------------------------------------------

    def RemoveTrash(self, strToBeCleaned, trash):

        return re.sub(trash, '', strToBeCleaned)
    
    # -----------------------------------------------------------------------------------------------

    def ReadLogicalRules(self, row, delimeters):
                
        rowValues = row.values
        strRow = ""

        for rowValue in rowValues:
            strRow += str(rowValue)

        tokens = self.Tokenizer(strRow, delimeters[0])
        self.type = tokens[0][6:]

        if len(tokens) > 2:
                    
            tokens[1] = tokens[1] + tokens[2]
            tokens.pop(2)

        tokens = self.Tokenizer(tokens[1], "=")
        self.variableName = tokens[0]

        tokens = self.Tokenizer(tokens[1], delimeters[1])

        lastElement = tokens[len(tokens)-1]
        lastElement = self.RemoveTrash(lastElement, 'nan')
        tokens[len(tokens)-1] = lastElement
                
        self.listOfValues = tokens

        return self        
    
# ===================================================================================================
    
class Table:

    def __init__(self):
        self._rawHeading = ""
        self._rawIO = ""
        self._rawType = ""
        self._name = None
        self._typeOfTable = None
        self._typeOfColumn = None
        self._dataType = None
        self._columnWidths = []
        self._columns = []
        self._rows = []
        self._table = None
        # FIX: stores the character start position of the first data column (Description).
        # Derived from the HEADING line. Standard PRN format is 8 ("R       "), but we
        # derive it from the actual file so files with non-standard padding still work.
        self._descriptionStart = 8

    @property
    def name(self):
        return self._name
    
    @property
    def typeOfTable(self):
        return self._typeOfTable

    @property
    def typeOfColumn(self):
        return self._typeOfColumn

    @property
    def dataType(self):
        return self._dataType            

    @property
    def columnWidths(self):
        return self._columnWidths

    @property
    def columns(self):
        return self._columns
    
    @property
    def rows(self):
        return self._rows  

    @property
    def table(self):
        return self._table  

    @name.setter
    def name(self, name):
        self._name = name

    @typeOfTable.setter
    def typeOfTable(self, typeOfTable):
        self._typeOfTable = typeOfTable

    @typeOfColumn.setter
    def typeOfColumn(self, typeOfColumn):
        self._typeOfColumn = typeOfColumn

    @dataType.setter
    def dataType(self, dataType):
        self._dataType = dataType                        

    @columnWidths.setter
    def columnWidths(self, columnWidths):
        self._columnWidths = columnWidths

    @columns.setter
    def columns(self, columns):
        self._columns = columns

    @rows.setter
    def rows(self, rows):
        self._rows = rows

    @table.setter
    def table(self, table):
        self._table = table

    # -----------------------------------------------------------------------------------------------

    def Tokenizer(self, string, delimiter):
        
        tokens = []
            
        while(string.find(delimiter)!=-1):
            
            string = string.partition(delimiter)
                            
            tokens.append(string[0])

            if len(string[0]) >= 1:
                tokens.append(string[1])
            
            string = string[2]
        
        tokens.append(string)
        
        return tokens

    # -----------------------------------------------------------------------------------------------

    def RemoveTrash(self, strToBeCleaned, trash):

        return re.sub(trash, '', strToBeCleaned)
    
    # -----------------------------------------------------------------------------------------------

    def ReadTable(self, row, delimeters, keyword):

        rowValues = row.values
        strRow = ""

        for rowValue in rowValues:
            strRow += str(rowValue)

        strRow = self.RemoveTrash(strRow, 'nan')

        if keyword == "TABLE TYPE":

            tokens = self.Tokenizer(strRow, delimeters[0])
            self.typeOfTable = tokens[2].lstrip()

        elif keyword == "HEADING":

            # --- FIX 140825 -----------------------------------------------------------------------
            # Previous approach: tokenize on single spaces and count blank tokens to infer widths.
            # Problem: consecutive-space runs are compressed differently by Tokenizer, making the
            # blank-count unreliable — especially in files with variable padding.
            #
            # New approach: use the CHARACTER POSITIONS of each column name in the raw HEADING
            # string. Since PRN is a fixed-width format, those positions are the exact byte offsets
            # where each column's data starts in every rule row.
            # --------------------------------------------------------------------------------------

            raw_heading = ""
            for value in rowValues:
                if pd.isna(value):
                    continue
                raw_heading += value
            self._rawHeading = raw_heading

            # Find all non-whitespace words and their start positions in the HEADING line.
            #   col_matches[0] = "HEADING"       ← row-type label, skip
            #   col_matches[1] = "Description"   ← marks where data starts in rule rows
            #   col_matches[2+] = business columns
            col_matches = list(re.finditer(r'\S+', raw_heading))

            if len(col_matches) > 1:
                self._descriptionStart = col_matches[1].start()

            # Width of column i = start_position(i+1) - start_position(i).
            # No entry for the last column; BuildTable catches the IndexError and slices to end.
            self._columnWidths = [
                col_matches[i + 1].start() - col_matches[i].start()
                for i in range(1, len(col_matches) - 1)
            ]

            # Column names from "Description" onwards (index 1).
            self._columns = [m.group() for m in col_matches[1:]]

        elif keyword == "I/O":
            raw_io = ""
            typesOfColumn = ""

            for value in rowValues:
                raw_io += str(value)
                if pd.isna(value):
                    continue
                typesOfColumn = value

            self._rawIO = self.RemoveTrash(raw_io, 'nan')
            typesOfColumn = self.Tokenizer(typesOfColumn, ' ')

            cleanedTypesOfColumn = []
            for c in typesOfColumn:
                if c != '' and c != ' ':
                    cleanedTypesOfColumn.append(c)

            self.typeOfColumn = cleanedTypesOfColumn[1:]
        
        elif keyword == "TYPE":
            raw_type = ""
            dataTypes = ""
            
            for value in rowValues:
                raw_type += str(value)
                if pd.isna(value):
                    continue
                dataTypes = value

            self._rawType = self.RemoveTrash(raw_type, 'nan')
            dataTypes = self.Tokenizer(dataTypes, ' ')

            cleanedDataTypes = []
            for c in dataTypes:
                if c != '' and c != ' ':
                    cleanedDataTypes.append(c)

            self.dataType = cleanedDataTypes[1:]

        elif keyword == "R" or keyword == "D" or keyword == "C":

            """
            180525
            
            + El último elemento de la lista de tokens contendrá el valor de la columna output y será tokeniz-
              ado utilizando el delimitador ; para obtener la lista de valores permitidos para la columna.

            """

            """
            050625 / FIX

            Previous approach: tokenize strRow, flatten all characters into a list, then slice
            by character position. Problem: Table.Tokenizer compresses consecutive spaces (when
            the left side of a split is empty, the space delimiter is NOT appended), so the
            flattened array is shorter than the original string — position-based slicing breaks.

            New approach: store the RAW string. BuildTable slices it directly using the character
            positions derived from the HEADING line. Tokenization is only used here to extract
            the table name (copyOfRules[2]).

            """

            rules = self.Tokenizer(strRow, " ")
            copyOfRules = [item for item in rules if item != '']

            try:
                self.name = copyOfRules[2].lstrip()
            except:
                self.name = "COULDNOTFINDTABLENAME"

            # Store the raw string for position-based slicing in BuildTable.
            self.rows.append(strRow)
     
    # -----------------------------------------------------------------------------------------------

    def WriteTable(self, fileHandler):
        fileHandler.write(f"TABLE TYPE: {self.typeOfTable}\n")
        fileHandler.write(self._rawHeading + "\n")
        fileHandler.write(self._rawIO + "\n")
        fileHandler.write(self._rawType + "\n")
        # Write the table type

        # # FIX: self.columns already starts with "Description".
        # # Old code had "HEADING Description " + " ".join(self.columns) which wrote Description twice.
        # fileHandler.write("HEADING " + " ".join(self.columns) + "\n")

        # # Write the type of columns
        # fileHandler.write("I/O: " + " ".join(self.typeOfColumn) + "\n")

        # # Write the data types
        # fileHandler.write("TYPE  " + " ".join(self.dataType) + "\n")

        # FIX: rows are now raw strings — write them directly.
        for row in self.rows:
            fileHandler.write(row + "\n")

    # -----------------------------------------------------------------------------------------------

    def BuildTable(self):

        # FIX 1: This method was accidentally placed OUTSIDE the Table class. An un-indented
        # separator comment between WriteTable and BuildTable broke the class indentation.
        # It is now correctly indented as a method of Table.
        #
        # FIX 2: Rewritten to slice the RAW row string by character positions derived from
        # the HEADING line, instead of flattening tokenized characters (which compressed
        # consecutive spaces and produced wrong column values).

        columns = ["HEADING"] + self.columns

        seen = {}
        deduped = []
        for c in columns:
            if c in seen:
                seen[c] += 1
                deduped.append(f"{c}_{seen[c]}")
            else:
                seen[c] = 0
                deduped.append(c)
        columns = deduped

        self._table = pd.DataFrame(columns=columns)

        for idxr, raw_row in enumerate(self.rows):

            # HEADING column: row-type indicator (R/D/C) lives in the first
            # self._descriptionStart characters ("R       " = 8 chars in standard PRN).
            self._table.loc[idxr, "HEADING"] = raw_row[0:self._descriptionStart].rstrip()

            start = self._descriptionStart

            for idxc, c in enumerate(self.columns):

                try:

                    end = start + self._columnWidths[idxc]
                    self._table.loc[idxr, c] = raw_row[start:end]
                    start = end

                except IndexError:

                    # Last column has no width entry → slice to end of line.
                    self._table.loc[idxr, c] = raw_row[start:]
                    break

        # --- for idxr, raw_row in enumerate(self.rows): --------------------------------------------

# ===================================================================================================

class PrnDoctor:

    def __init__(self, file):

        self._pathAndNameOfTheFile = file
        self._fileHandler = pd.read_fwf(file, header=None, widths=[500]*10)
        self._delimiters = None

        # FIX: dropna(how='all') only removes rows where every cell is NaN.
        # Legacy PRN files insert blank lines that read_fwf parses as rows of
        # whitespace-only strings (e.g. "   "), not NaN — dropna leaves them in.
        # We add an explicit whitespace-only row filter after dropna.
        self._fileHandler = self._fileHandler.dropna(how='all')
        self._fileHandler = self._fileHandler[
            ~self._fileHandler.apply(
                lambda row: all(
                    pd.isna(v) or (isinstance(v, str) and v.strip() == '')
                    for v in row
                ),
                axis=1
            )
        ]
        self._fileHandler = self._fileHandler.reset_index(drop=True)
        self._logicalRules = []
        self._tables = []

    # --- def __init__(self, file): ----------------------------------------------------------------


    """
    
        @property
        
        * The @property decorator is used to define a method as a property. This allows 
          you to access the method like an attribute, without needing to call it as a method.
          
        * It is a way to encapsulate the access to an attribute, providing a getter method that 
          can include additional logic if needed.

        def pathAndNameOfTheFile(self):
        
        * This line defines a method named pathAndNameOfTheFile within a class. The self parameter 
          refers to the instance of the class.

        * By using the @property decorator, this method will be treated as a property, meaning you 
          can access it like an attribute.
        
        return self._pathAndNameOfTheFile

        * This line returns the value of the private attribute _pathAndNameOfTheFile.
        
        * The underscore (_) prefix is a common convenience in Python to indicate that the attribute 
          is intended to be private and should not be accessed directly from outside the class.
    
    """

    @property
    def pathAndNameOfTheFile(self):
        return self._pathAndNameOfTheFile
    
    @property
    def fileHandler(self):
        return self._fileHandler
    
    @property
    def getDelimiters(self):

        firstRow = self._fileHandler.iloc[0]
        
        for column in self._fileHandler.columns:

            if pd.isna(firstRow[column]):
                continue

            if "DELIMITER" in firstRow[column]:

                # FIX: strip trailing whitespace before taking the last 2 characters.
                # Without rstrip(), a line ending in spaces (e.g. "DEFINE DELIMITER:;  ")
                # would yield "  " instead of ":;", breaking all downstream tokenization.
                line = firstRow[column].rstrip()
                self._delimiters = line[len(line) - 2:]

        return self._delimiters

    @property
    def logicalRules(self):
        return self._logicalRules
    
    @logicalRules.setter
    def logicalRules(self, rule):
        self._logicalRules.append(rule)

    @property
    def tables(self):
        return self._tables
    
    @tables.setter
    def tables(self, table):
        self._tables.append(table)

    # -----------------------------------------------------------------------------------------------

    def Tokenizer(self, string, delimiter):
        
        tokens = []
            
        while(string.find(delimiter)!=-1):
            
            string = string.partition(delimiter)
                            
            tokens.append(string[0])
            
            string = string[2]
        
        tokens.append(string)
        
        return tokens
    
    # --- def Tokenizer(string,delimiter): ----------------------------------------------------------

    def RemoveTrash(self, strToBeCleaned, trash):

        return re.sub(trash, '', strToBeCleaned)
    
    # --- def RemoveTrash(self, strToBeCleaned, trash): ---------------------------------------------

    def ReadPRN(self):
    
        for index, row in self._fileHandler.iterrows():

            # FIX: old guard was `pd.isna(row.iloc[0]) or index == 0`.
            #
            # Problem 1 – whitespace rows: the __init__ filter handles these, but we keep
            # the isna check as a safety net for any that slip through.
            #
            # Problem 2 – `index == 0`: this unconditionally skipped the first row, relying
            # on DEFINE DELIMITER always being at index 0. With blank lines at the top of the
            # file, the delimiter row shifts to index 1, 2, … and was no longer skipped —
            # so it entered ReadLogicalRules with delimiters=None and crashed on None[0].
            # We now skip it explicitly by content, not by position.

            first_val = row.iloc[0]

            if pd.isna(first_val) or (isinstance(first_val, str) and first_val.strip() == ''):
                continue

            # DEFINE DELIMITER is consumed by getDelimiters; skip it in the main loop.
            if first_val.startswith("DEFINE DELIMITER"):
                continue

            # --- blank / delimiter row handled above ----------------------------------------------
            
            # We check for the occurrence of the keyword DEFINE in the first column of the n-th row.
            # All rows that start with DEFINE will be stored and handled by the instance of the
            # class LogicalRules.
            if first_val.startswith("DEFINE"):

                logRls = LogicalRules()
                delimeters = self.getDelimiters
                logRls.ReadLogicalRules(row, delimeters)
                self.logicalRules = logRls
                continue
            
            # --- if row.iloc[0].startswith("DEFINE") ----------------------------------------------            
            
            # We check for the occurrence of the keyword TABLE in the first column of the n-th row.
            # All rows that start with TABLE will be stored and handled by the instance of the
            # class Tables.            
            if first_val.startswith("TABLE"):

                tbl = Table()
                delimeters = self.getDelimiters
                # first_val[:10] -> "TABLE TYPE"
                tbl.ReadTable(row, delimeters, first_val[:10])
                self.tables = tbl
            
            # --- if row.iloc[0].startswith("TABLE"): ----------------------------------------------  

            if first_val.startswith("HEADING"):
                # first_val[:7] -> "HEADING"
                tbl.ReadTable(row, delimeters, first_val[:7])

            # --- if row.iloc[0].startswith("HEADING"): --------------------------------------------  

            if first_val.startswith("I/O"):
                # first_val[:3] -> "I/O"
                tbl.ReadTable(row, delimeters, first_val[:3])

            # --- if row.iloc[0].startswith("I/O"): ------------------------------------------------

            if first_val.startswith("TYPE"):
                # first_val[:4] -> "TYPE"
                tbl.ReadTable(row, delimeters, first_val[:4])

            # --- if row.iloc[0].startswith("TYPE"): -----------------------------------------------

            if first_val.startswith("R") or first_val.startswith("D") or \
               first_val.startswith("C"):
                # first_val[0] -> "R", "D", or "C"
                tbl.ReadTable(row, delimeters, first_val[0])

            # --- if row.iloc[0].startswith("R/D/C"): ------------------------------------------------

    # --- def read(self): ---------------------------------------------------------------------------

    def OptimizationOne(self):
        """
        Optimizes tables by reducing duplicate rows while preserving original order.
        - Works on grouped logic (construct column).
        - Replaces block of rows with one reduced row at the original start index.
        - Keeps HEADING, Description, and last column unchanged.
        - Generates OR mappings for differing values.
        Returns:
            reduced_tables: dict {table_name: optimized DataFrame}
            global_or_mapping: dict {table_name: {OR_name: [values]}}
        """
        reduced_tables = {}
        global_or_mapping = {}

        for index, item in enumerate(self.tables):
            item.BuildTable()
            table = item.table
            tableName = item.name
            columns = list(table.columns)

            if tableName not in columns:
                continue

            # Identify columns to ignore
            ignore_cols = {'HEADING', 'Description', columns[-1]}
            compare_cols = [col for col in columns if col not in ignore_cols]

            # Find duplicates
            duplicated_rows = table[table.duplicated(subset=tableName, keep=False)]
            grouped = duplicated_rows.groupby(tableName)

            # Work on a copy to preserve order
            optimized_table = table.copy()
            or_mapping = {}

            for _, group in grouped:
                # Filter out Disabled rows
                group = group[group['HEADING'].str.strip() != 'D']
                if group.empty:
                    continue

                start_idx = group.index.min()
                base_row = group.iloc[0].copy()

                for col_index, col in enumerate(compare_cols):
                    # unique_vals = group[col].dropna().unique()
                    # print(len(unique_vals))
                    col_data = group[col]

                    if isinstance(col_data, pd.DataFrame):
                        col_data = col_data.iloc[:, 0]

                    col_data = col_data.replace('', pd.NA)
                    unique_vals = col_data.dropna().unique()

                    if len(unique_vals) > 1:
                        or_name = f"{col}OrValues{col_index}"
                        base_row[col] = or_name
                        or_mapping[or_name] = list(unique_vals)
                    else:
                        base_row[col] = unique_vals[0] if len(unique_vals) > 0 else ''

                optimized_table.drop(index=group.index, inplace=True)
                before = optimized_table.loc[:start_idx - 1]
                after = optimized_table.loc[start_idx:]
                optimized_table = pd.concat([before, pd.DataFrame([base_row]), after])

            optimized_table.reset_index(drop=True, inplace=True)
            item.table = optimized_table
            item.rows = []
            for _, df_row in optimized_table.iterrows():
                raw = str(df_row['HEADING']).ljust(item._descriptionStart)
                for col_idx, col in enumerate(item.columns):
                    val = '' if pd.isna(df_row[col]) else str(df_row[col])
                    try:
                        raw += val.ljust(item._columnWidths[col_idx])
                    except IndexError:
                        raw += val
                item.rows.append(raw)
            reduced_tables[item.name] = optimized_table
            global_or_mapping[item.name] = or_mapping

            # print('================================ BEFORE ================================')
            # print(table)
            # print('================================ AFTER ================================')
            # print(optimized_table)
        return reduced_tables, global_or_mapping

    def EqualTokensDetector(self):

        print("\n")
        print(f"Type of Column: {self.tables[0].typeOfColumn}")
        print(f"Columns: {self.tables[0].columns}")
        print("\n")

        print("----------------")
        print(len(self.tables[0].typeOfColumn))
        print("----------------")

        # FIX: rows are now raw strings. Slice by _descriptionStart and _columnWidths.
        tbl = self.tables[0]
        for raw_row in tbl.rows:
            start = tbl._descriptionStart
            parts = [raw_row[0:start].rstrip()]
            for w in tbl._columnWidths:
                parts.append(raw_row[start:start + w])
                start += w
            parts.append(raw_row[start:])  # last column
            print(parts)

    def WritePRN(self, fileName):

        with open(fileName, 'w') as file:

            # Write the delimiters
            file.write(f"DEFINE DELIMITER{self._delimiters}\n")

            # Write the logical rules
            for rule in self.logicalRules:
                file.write(f"DEFINE OR:{rule.variableName}={';'.join(rule.listOfValues)}\n")

            # Write the tables
            for table in self.tables:
                table.WriteTable(file)


# ===================================================================================================