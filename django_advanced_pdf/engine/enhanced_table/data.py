from django_advanced_pdf.engine.utils import DecimalText


class EnhancedTableData(object):
    """
    A helper class for passing data to the EnhancedTable class.
    """

    def __init__(self, row_data=None, cell_styles=None, row_heights=None, row_styles=None):
        """
        Class Constructor.

        @type   row_data : list of lists
        @param  row_data : A list of table row data
        @type   cell_styles : list
        @param  cell_styles : a list of cell_styles for use with the row_data
        @type   row_heights : list
        @param  row_heights : a list of row heights as expected by ReportLab Table
        @type   row_styles : list of tuples
        @param  row_styles : a list of row styles (Reportlab Table commands)
        """
        self.row_data = []
        self.row_variables = []
        self.row_properties = []
        self.row_styles = []
        self.cell_styles = []
        self.row_heights = []
        if row_data and isinstance(row_data, list):
            self.row_data = row_data
        if cell_styles and isinstance(cell_styles, list):
            self.cell_styles = cell_styles
        if row_heights and isinstance(row_heights, list):
            self.row_heights = row_heights
        if row_styles and isinstance(row_styles, list):
            self.row_styles = row_styles

    def reset(self):
        self.row_data = []
        self.row_variables = []
        self.row_properties = []
        self.row_styles = []
        self.cell_styles = []
        self.row_heights = []

    def append_row_data(self, data, used_columns_fn, variables=None, datafn=None, properties=None):

        """
        Append a row of data to the table. This method scans for data cells which
        are instances of L{DecimalText} and sets appropriate table styles. An optional
        function can be passed to further process the data, typically to wrap it with
        wrapper class.

        @type   data    : list
        @param  data    : Columns
        @type   datafn  : Function
        @param  datafn  : Optional function to further process data
        """

        data = used_columns_fn(data)
        for colno, cell in enumerate(data):
            if isinstance(cell, DecimalText):
                self.append_computed_row_style('ALIGN', colno, 'DECIMAL')
                self.append_computed_row_style('FONTNAME', colno, cell.font_name())
                self.append_computed_row_style('FONTSIZE', colno, cell.font_size())
                self.append_computed_row_style('RIGHTPADDING', colno, cell.right_padding())
                self.append_computed_row_style('LEADING', colno, cell.leading())

        if variables is not None:
            self.row_variables.append(variables)
        else:
            self.row_variables.append({})

        if properties is not None:
            self.row_properties.append(properties)
        else:
            self.row_properties.append({})

        if datafn is not None:
            data = datafn(data)
        self.row_data.append(data)

    def append_row_style(self, style):
        self.row_styles.append(style)

    def append_computed_row_style(self, style, whence, *extra):

        """
        Convenience method to append a table style, covering most use cases and automating
        line ranges. The style will apply to the current line only (ie the last row in row_data, except for I{NOSPLIT}
        which applies to this and the next line.

        @type   style   : str
        @param  style   : Style ('SPAN', 'BoX', ...)
        @type   whence  : I{None}, integer or tuple/list
        @param  whence  : I{None} => all columns, integer => single column, list/tuple => column range
        @type   extra   : Mixed
        @param  extra   : Additional style settings (colors, line widths, ...)
        """

        if whence is None:
            whence = (0, -1)
        elif not (isinstance(whence, list) or isinstance(whence, tuple)):
            whence = (whence, whence)
        elif len(whence) == 1:
            whence *= 2
        line1 = len(self.row_data)
        if style == 'NOSPLIT':
            if len(extra) > 0:
                line2 = line1 + extra[0]
                extra = extra[1:]
            else:
                line2 = line1 + 1
        else:
            line2 = line1

        self.row_styles.append((style, (whence[0], line1), (whence[1], line2)) + extra)
