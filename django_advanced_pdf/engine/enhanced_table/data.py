class EnhancedTableData(object):
    """
    A helper class for passing data to the EnhancedTable class.
    """

    def __init__(self, row_data=None, commands=None, row_heights=None):
        """
        Class Constructor.

        @type   row_data : list of lists
        @param  row_data : A list of table row data
        @type   commands : list
        @param  commands : a list of command / styles for use with the row_data
        @type   row_heights : list
        @param  row_heights : a list of row heights as expected by ReportLab Table
        """
        self.row_data = []
        self.row_variables = []
        self.row_properties = []
        self.commands = []
        self.row_heights = []
        if row_data and isinstance(row_data, list):
            self.row_data = row_data
        if commands and isinstance(commands, list):
            self.commands = commands
        if row_heights and isinstance(row_heights, list):
            self.row_heights = row_heights
        self.row_length = len(self.row_data)
        self.rows_height = sum(self.row_heights)

    def reset(self):
        self.row_data = []
        self.row_variables = []
        self.row_properties = []
        self.commands = []
        self.row_length = 0
        self.rows_height = 0
