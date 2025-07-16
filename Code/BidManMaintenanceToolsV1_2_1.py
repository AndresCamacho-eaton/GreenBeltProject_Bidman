
import pandas as pd
import re

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
                
        # We need the string representation of the n-th row. With row.values we get a list
        # where each element represents the value of a column.
        rowValues = row.values
        strRow = ""

        # We then form the string representation by concatenating each element of the list.
        for rowValue in rowValues:
            strRow += str(rowValue)

        # We invoke the Tokenizer method using the character ':' as the delimiter. This produces
        # a list where the 0th element is formed by the keyword DEFINE, a whitespace character
        # , and the keyword OR. Given that this part of the structure of the prn file format
        # is constant, we can get rid of the keyword DEFINE and the whitespace character by
        # slicing the content of the 0th element as shown here.                
        tokens = self.Tokenizer(strRow, delimeters[0])
        self.type = tokens[0][6:]

        # We then invoke the Tokenizer method using the character '=' as the delimiter. This
        # will give us the name of the variable in the first position of the resulting list.
        # 130525
        # ['DEFINEOR', 'Poles', '2-3=2 Pole;3 Pole']
        # There are some cases where the variable names is split into two elements, so we need
        # to concatenate them before the next tokenization step.
        if len(tokens) > 2:
                    
            tokens[1] = tokens[1] + tokens[2]
            tokens.pop(2)

        tokens = self.Tokenizer(tokens[1], "=")
        self.variableName = tokens[0]

        # To get the list of values that the variable can take, we need to perform a series
        # of steps: 1) invoke the Tokenizer method using the ';' as the delimiter; 2) obtain
        # the last element of the list of values allowed for the variable; 3) remove the 
        # undesired content in the string that represents the last value of the list; 4)
        # substitute the last element of the list with the one that has been cleaned up;
        # and 5) assign the new list of values to the corresponding attribute of the
        # LogicalRules instance.
        tokens = self.Tokenizer(tokens[1], delimeters[1])

        lastElement = tokens[len(tokens)-1]
        lastElement = self.RemoveTrash(lastElement, 'nan')
        tokens[len(tokens)-1] = lastElement
                
        self.listOfValues = tokens

        return self        
    
# ===================================================================================================
    
class Table:

    def __init__(self):

        self._name = None
        self._typeOfTable = None
        self._typeOfColumn = None
        self._dataType = None
        self._columns = []
        self._rows = []
        
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
    def columns(self):
        return self._columns
    
    @property
    def rows(self):
        return self._rows    
    
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

    @columns.setter
    def columns(self, columns):
        self._columns = columns

    @rows.setter
    def rows(self, rows):
        self._rows = rows

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

    def ReadTable(self, row, delimeters, keyword):

        # We need the string representation of the n-th row. With row.values we get a list
        # where each element represents the value of a column.
        rowValues = row.values
        strRow = ""

        # We then form the string representation by concatenating each element of the list.
        for rowValue in rowValues:
            strRow += str(rowValue)

        strRow = self.RemoveTrash(strRow, 'nan')

        if keyword == "TABLE TYPE":

            # We invoke the Tokenizer method using the character ':' as the delimiter. This produces
            # a list where the 0th element is formed by the words TABLE TYPE and the 1st element contains
            # the value of the table type.
            tokens = self.Tokenizer(strRow, delimeters[0])

            self.typeOfTable = tokens[1].lstrip()

        elif keyword == "HEADING":

            columns = ""
            
            for value in rowValues:
                
                if pd.isna(value):
                    continue

                columns = value
            
            # --- for value in rowValues: -------------------------------------------------------------------

            columns = self.Tokenizer(columns, ' ')

            self.columns = columns[2:]
        
        elif keyword == "I/O":

            typesOfColumn = ""
            
            for value in rowValues:
                
                if pd.isna(value):
                    continue

                typesOfColumn = value
            
            # --- for value in rowValues: -------------------------------------------------------------------

            typesOfColumn = self.Tokenizer(typesOfColumn, ' ')

            self.typeOfColumn = typesOfColumn[2:]
        
        elif keyword == "TYPE":

            dataTypes = ""
            
            for value in rowValues:
                
                if pd.isna(value):
                    continue

                dataTypes = value
            
            # --- for value in rowValues: -------------------------------------------------------------------

            dataTypes = self.Tokenizer(dataTypes, ' ')

            self.dataType = dataTypes[2:]

        elif keyword == "R" or keyword == "D" or keyword == "C":

            """
            180525
            
            + El último elemento de la lista de tokens contendrá el valor de la columna output y será tokeniz-
              ado utilizando el delimitador ; para obtener la lista de valores permitidos para la columna.

            """

            """
            050625

            + No encontramos una manera universal de realizar la tokenización, así que optamos por utilizar un
              sólo espacio en blanco. Esta decisión implica renunciar a la idea de asignar el valor correspond-
              iente a cada columna. La hipótesis es que no necesitamos ese nivel de precisión para operar los
              algoritmos de optimización que representan el núcleo de la herramienta.

            """
            rules = self.Tokenizer(strRow, " ")

            copyOfRules = rules.copy()
            copyOfRules = [item for item in copyOfRules if item != '']
    
            self.name = copyOfRules[1].lstrip()

            self.rows.append(rules)
     
    # -----------------------------------------------------------------------------------------------

    def WriteTable(self, fileHandler):
            
        # Write the table type
        fileHandler.write(f"TABLE TYPE: {self.typeOfTable}\n")

        # Write the columns
        fileHandler.write("HEADING Description " + " ".join(self.columns) + "\n")

        # Write the type of columns
        fileHandler.write("I/O: " + " ".join(self.typeOfColumn) + "\n")

        # Write the data types
        fileHandler.write("TYPE  " + " ".join(self.dataType) + "\n")

        # Write the rows
        for row in self.rows:
            fileHandler.write(" ".join(row) + "\n")

# ===================================================================================================

class PrnDoctor:

    def __init__(self, file):

        self._pathAndNameOfTheFile = file
        self._fileHandler = pd.read_fwf(file, header=None, widths=[500]*10)
        self._delimiters = None
        self._fileHandler = self._fileHandler.dropna(how='all')
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
        
        * The underscore (_) prefix is a common convention in Python to indicate that the attribute 
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

                offset = len(firstRow[column])
                self._delimiters = firstRow[column][offset-2:]

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

            # If the row is empty or if it is the first row, we skip it.
            if pd.isna(row.iloc[0]) or index == 0:
                continue
            
            # We check for the occurrence of the keyword DEFINE in the first column of the n-th row.
            # All rows that start with DEFINE will be stored and handled by the instance of the
            # class LogicalRules.
            if row.iloc[0].startswith("DEFINE"):

                # We create an instance of the LogicalRules for each iteration of the for loop.        
                logRls = LogicalRules()

                delimeters = self.getDelimiters

                logRls.ReadLogicalRules(row, delimeters)

                # We then append the LogicalRules instance to the list of logical rules.
                self.logicalRules = logRls

                continue
            
            # --- if row.iloc[0].startswith("DEFINE") ----------------------------------------------            
            
            # We check for the occurrence of the keyword TABLE in the first column of the n-th row.
            # All rows that start with TABLE will be stored and handled by the instance of the
            # class Tables.            
            if row.iloc[0].startswith("TABLE"):

                # We create an instance of the Table object for each iteration of the for loop.        
                tbl = Table()

                delimeters = self.getDelimiters

                # row.iloc[0][:10] -> "TABLE TYPE"
                tbl.ReadTable(row, delimeters, row.iloc[0][:10])

                # We then append the Table instance to the list of Tables.
                self.tables = tbl
            
            # --- if row.iloc[0].startswith("TABLE"): ----------------------------------------------  

            if row.iloc[0].startswith("HEADING"):

                # row.iloc[0][:7] -> "HEADING"
                tbl.ReadTable(row, delimeters, row.iloc[0][:7])

            # --- if row.iloc[0].startswith("HEADING"): --------------------------------------------  

            if row.iloc[0].startswith("I/O"):

                # row.iloc[0][:3] -> "I/O"
                tbl.ReadTable(row, delimeters, row.iloc[0][:3])

            # --- if row.iloc[0].startswith("I/O"): ------------------------------------------------

            if row.iloc[0].startswith("TYPE"):

                # row.iloc[0][:4] -> "TYPE"
                tbl.ReadTable(row, delimeters, row.iloc[0][:4])

            # --- if row.iloc[0].startswith("TYPE"): -----------------------------------------------

            if row.iloc[0].startswith("R") or row.iloc[0].startswith("D") or row.iloc[0].\
               startswith("C"):

                # row.iloc[0][0] -> "R, C, D"
                tbl.ReadTable(row, delimeters, row.iloc[0][0])

            # --- if row.iloc[0].startswith("TYPE"): ------------------------------------------------

    # --- def read(self): ---------------------------------------------------------------------------

    def OptimizationOne(self):

        """
            This method is intended to optimize the logical rules and tables.
            The optimization process will be implemented in future versions.
        """

        def read_table():
            f = int(input('Ingrese el número de filas: '))
            c = int(input('Ingrese el número de columnas: '))

            tabla = []
            tipoColumna = []
            tipoDato = []

            for j in range(c):
                if j == c - 1:
                    tipoColumna.append('output')
                else:
                    tipoColumna.append('input')
                tipoDato.append(input(f'Ingrese el tipo de dato de la columna {j + 1} (ALPHA/NUM/FLOAT): '))

            for i in range(f):
                row = []
                for j in range(c):
                    value = input(f'Ingrese el valor de la fila {i + 1}, columna {j + 1}: ')
                    row.append(value)
                tabla.append(row)

            return tabla, tipoColumna, tipoDato, f, c

        def detectar_patrones(tabla, tipoColumna, f, c):
            outputCol = c - 1
            print('Filas a optimizar encontradas')
            for i in range(f):
                totalCoincidencias = 1
                for j in range(f):
                    if i != j:
                        igualesInputs = True
                        for x in range(c - 1):
                            if tipoColumna[x] == 'input':
                                if tabla[i][x] != tabla[j][x]:
                                    igualesInputs = False
                                    break
                        if igualesInputs:
                            totalCoincidencias += 1

                if totalCoincidencias >= 2:
                    valorOutput = tabla[i][outputCol]
                    esValido = True
                    for j in range(f):
                        if i != j:
                            igualesInputs = True
                            for x in range(c - 1):
                                if tipoColumna[x] == 'input':
                                    if tabla[i][x] != tabla[j][x]:
                                        igualesInputs = False
                                        break
                            if igualesInputs:
                                if tabla[j][outputCol] != valorOutput:
                                    esValido = False
                                    break
                    if esValido:
                        print(' '.join(tabla[i]))

        def detectar_patrones_v2(tabla, tipoColumna, f, c):

            pass

        def main():
            tabla, tipoColumna, tipoDato, f, c = read_table()
            detectar_patrones(tabla, tipoColumna, f, c)

        main()
        # pass

    def EqualTokensDetector(self):

        #print(self.tables)

        # Imprimiendo los atributos del objeto Table.

        """
            self._name = None
            self._typeOfTable = None
            self._typeOfColumn = None
            self._dataType = None
            self._columns = []
            self._rows = []
        """

        #print(f"Name: {self.tables[0].name}")
        #print(f"Type of Table: {self.tables[0].typeOfTable}")
        print("\n")
        print(f"Type of Column: {self.tables[0].typeOfColumn}")
        print(f"Columns: {self.tables[0].columns}")
        print("\n")
        #print(f"Data Type: {self.tables[0].dataType}")
        #print(f"Columns: {self.tables[0].columns}")
        #print(self.tables[0].rows)

        print("----------------")
        print(len(self.tables[0].typeOfColumn))
        print("----------------")

        for row in self.tables[0].rows:
            if len(row) >= len(self.tables[0].typeOfColumn):
                row[len(self.tables[0].typeOfColumn)] = 'FOUND_POSITION'
                print(row)
                
                #print(len(row))
                #print(row)
                #print("***")
                #print(row[len(self.tables[0].typeOfColumn)-3])
                #print(row[len(self.tables[0].typeOfColumn)-2])
                #print(row[len(self.tables[0].typeOfColumn)-1])



    

        #print("\n")

        #print(f"Name: {self.tables[1].name}")
        #print(f"Type of Table: {self.tables[1].typeOfTable}")
        #print(f"Type of Column: {self.tables[1].typeOfColumn}")
        #print(f"Data Type: {self.tables[1].dataType}")
        #print(f"Columns: {self.tables[1].columns}")
        #print(self.tables[1].rows)

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

