from reportlab import rl_config
from reportlab.lib.rl_accel import fp_str
from reportlab.lib.utils import annotateException, flatten
from reportlab.platypus.flowables import Flowable
from reportlab.platypus.flowables import PageBreak
from reportlab.platypus.para import handleSpecialCharacters
from reportlab.platypus.paragraph import Paragraph
from reportlab.platypus.tables import Table, _calc_pc, spanFixDim, CellStyle
from six import string_types

from django_advanced_pdf.engine.enhanced_table.data_paragraph import DataParagraph
from django_advanced_pdf.engine.utils import DecimalText

OVERFLOW_ROW = -9999
UNDEFINED_ROW = -8888


# noinspection PyPep8Naming
class EnhancedTable(Table):
    """
    An enhanced version of Reportlab's Table class.
    Key differences are the ability to supply details for continuation header/footer which get used when a
    table splits across page boundaries.
    Data rows can be supplied with corresponding properties which indicate if a particular row is a header, total data
    or blank row. This information is used to help fine-tune where a table can be split should the need arise.
    """

    def __init__(self, table_data, header=None, footer=None, min_rows_after_header=1, min_rows_before_total=1,
                 col_widths=None, row_heights=None, style=None,
                 repeat_rows=0, repeat_cols=0, split_by_row=1, empty_table_action=None, ident=None,
                 h_align=None, v_align=None, normalized_data=0, cell_styles=None,
                 _calc_row_splits=True, initial=False, pos_x=None, pos_y=None):
        """
        Class Constructor.

        Custom parameters
        =================
        @type   table_data : dict
        @param  table_data : dictionary of row data (key='row_data'), variables ('variables') and
                             properties ('properties') for each row of this table (keys are 'row_data', 'variables'
                             and 'properties' respectively). Each contains a list of data, one entry per row.
                             Variables contains the substitution values for continuation headers and footers.
                             Properties are used primarily to indicate whether a row is a header, total, data or blank.
        @type   header : django_advanced_pdf.engine.enhanced_table.data.EnhancedTableData
        @param  header : row data and styles for a continuation header, if required
        @type   footer : django_advanced_pdf.engine.enhanced_table.data.EnhancedTableData
        @param  footer : row data and styles for a continuation footer, if required
        @type   min_rows_after_header : int
        @param  min_rows_after_header : The number of rows to mark as non-splittable after any row marked with a
                                        property of 'HEADER'
        @type   min_rows_before_total : int
        @param  min_rows_before_total : The number of rows to mark as non-splittable immediately prior to any row
                                        marked with a property of 'TOTAL'
        @type   _calc_row_splits      : bool
        @param  _calc_row_splits      : private parameter used to control the calculation of nosplit commands

        Parameters inherited from Reportlab's reportlab.platypus.tables.Table class
        =================
        @type   col_widths : list
        @param  col_widths : a list of column widths as expected by ReportLab Table
        @type   row_heights : list
        @param  row_heights : a list of row heights as expected by ReportLab Table
        @type   style : list
        @param  style : a list of row styles (commands) as expected by ReportLab Table
        @type   repeat_rows : int
        @param  repeat_rows : The number of initial rows to repeat on subsequent pages if a table is split vertically
        @type   repeat_cols : int
        @param  repeat_cols : NOT SUPPORTED (ReportLab functionailty)
        @type   h_align     : str
        @param  h_align     : horizontal alignment as expected by ReportLab Table
        @type   v_align     : str
        @param  v_align     : vertical alignment as expected by ReportLab Table
        @type   normalized_data     : int
        @param  normalized_data     : Flag to indictae whether teh table data passed in is already normalised or not
        @type   cell_styles : list
        @param  style : a list of cell styles (commands) as expected by ReportLab Table
        @rtype  : EnhancedTable
        @return : An Enhanced Table object, based on ReportLab Table
        """

        self.initial = initial
        self.header = header
        self.footer = footer
        self.data = table_data.get('row_data', [])
        self.variables = table_data.get('row_variables', [{} for x in range(len(self.data))])
        self.properties = table_data.get('row_properties', [{} for x in range(len(self.data))])
        self.keep_with_next = table_data.get('keep_with_next', [False for x in range(len(self.data))])

        self.min_rows_after_header = min_rows_after_header
        self.min_rows_before_total = min_rows_before_total
        self.pos_x = pos_x
        self.pos_y = pos_y

        no_split_cmds = self._calc_nosplit_positions(_calc_row_splits)

        if no_split_cmds:
            if style:
                style += no_split_cmds
            else:
                style = no_split_cmds

        Table.__init__(self,
                       data=self.data,
                       colWidths=col_widths,
                       rowHeights=row_heights,
                       style=style,
                       repeatRows=repeat_rows,
                       repeatCols=repeat_cols,
                       splitByRow=split_by_row,
                       emptyTableAction=empty_table_action,
                       ident=ident,
                       hAlign=h_align,
                       vAlign=v_align,
                       normalizedData=normalized_data,
                       cellStyles=cell_styles)

    def _getFirstPossibleSplitRowPosition(self, availHeight):
        # Note - this is actually looking for the BEST available split position, which is not necessarily the first.
        impossible = {}
        if self._spanCmds:
            self._getRowImpossible(impossible, self._rowSpanCells, self._spanRanges)
        if self._nosplitCmds:
            self._getRowImpossible(impossible, self._rowNoSplitCells, self._nosplitRanges)

        h = 0
        n = 1

        footer_height = 0
        if self.footer is not None:
            footer_height = sum(self.footer.row_heights)

        number_of_header = 0
        if self.header is not None:
            number_of_header = len(self.header.row_heights)

        split_at = 0  # from this point of view 0 is the first position where the table may *always* be split
        for i, rh in enumerate(self._rowHeights):
            keep_with_next = self.keep_with_next[i]
            if h + rh > availHeight - footer_height:
                break
            if (self.initial or i > number_of_header) and n not in impossible and not keep_with_next == 1:
                split_at = n
            h = h + rh
            n += 1

        return split_at

    @staticmethod
    def merge_variables_into_data(data, variables):
        """
        This takes a list of table data and combines it with its associated variables (if supplied)
        This allows us to substitute variables into rows to create header/footer rows for use when splitting tables.
        """

        output = []
        for row in data:
            row_data = []
            for col in row:
                if isinstance(col, DataParagraph):
                    row_data.append(col.merge_variables(variables))
                elif isinstance(col, Paragraph):
                    row_data.append(col)
                    # row_data.append(col.merge_variables(variables))
                elif isinstance(col, DecimalText):
                    row_data.append(col.merge_variables(variables))
                else:
                    if col != '':
                        try:
                            value = ""
                            col = col.decode('utf-8')
                            col = handleSpecialCharacters(None, col)
                            col = ''.join(col).encode('utf-8', 'ignore')
                            for c in col:
                                value += c
                            col = value
                        except Exception:
                            pass
                    if col and variables:
                        try:
                            row_data.append(col % variables)
                        except TypeError:
                            # This is a Decimal Text, text needs to be removed, updated and reinserted
                            text = col.m_text
                            updated_text = text % variables
                            col.m_text = updated_text
                            row_data.append(col)
                    else:
                        row_data.append(col)
            output.append(row_data)

        return output

    def _cr_1_1_enhanced(self, n, repeat_rows, header_rows, cmds):
        # Modified version of Table._cr_1_1
        for c in cmds:
            c = tuple(c)
            (sc, sr), (ec, er) = c[1:3]
            if sr in ('splitfirst', 'splitlast'):
                self._addCommand(c)
            else:
                # if sr >= 0 and sr >= repeat_rows and sr < n and er >= 0 and er < n:
                if 0 <= sr < n and sr >= repeat_rows and 0 <= er < n:
                    # Ignore commands which are before the split_point (n) and start after repeat_rows
                    continue
                if repeat_rows <= sr < n:
                    sr = repeat_rows + header_rows
                elif sr >= repeat_rows and sr >= n:
                    sr = sr + repeat_rows + header_rows - n
                if repeat_rows <= er < n:
                    er = repeat_rows + header_rows
                elif er >= repeat_rows and er >= n:
                    er = er + repeat_rows + header_rows - n
                self._addCommand((c[0],) + ((sc, sr), (ec, er)) + c[3:])

    def _add_offset_commands(self, n, cmds):
        for c in cmds:
            c = tuple(c)
            (sc, sr), (ec, er) = c[1:3]
            sr += n
            er += n
            self._addCommand((c[0],) + ((sc, sr), (ec, er)) + c[3:])

    def _splitRows(self, availHeight, doInRowSplit=0):

        n = self._getFirstPossibleSplitRowPosition(availHeight)
        if n <= self.repeatRows:
            return []
        lim = len(self._rowHeights)
        if n == lim:  # No splitting required
            return [self]

        r0_end = n

        # Check to see if the row we are splitting on is of type 'BLANK'.
        # If it is then we can actually ignore it - i.e. end the first split section (RO) one row earlier.
        # This will probably have adverse side effects if the row had commands associated with it

        insert_pagebreak = False
        try:
            if n > 0 and self.properties[n - 1]['row_type'].upper() == 'BLANK':
                insert_pagebreak = True  # Otherwise reportlab can squeeze in more stuff afterwards, which is bad
                r0_end = n - 1
        except KeyError:  # row_type not specified
            pass

        repeat_rows = self.repeatRows
        repeat_cols = self.repeatCols
        split_by_row = self.splitByRow
        data = self._cellvalues

        # we're going to split into two superRows
        ident = self.ident

        footer_row_data = []
        footer_row_heights = []
        footer_row_styles = []
        footer_cell_styles = []
        footer_row_variables = []
        footer_row_properties = []
        footer_keep_with_next = []

        if self.footer is not None:
            try:
                footer_row_data = self.merge_variables_into_data(self.footer.row_data, self.variables[r0_end - 1])
            except (IndexError, KeyError):
                footer_row_data = self.footer.row_data
            footer_row_heights = self.footer.row_heights
            footer_row_styles = self.footer.row_styles
            footer_cell_styles = self.footer.cell_styles
            footer_row_variables = [{} for _ in footer_row_data]
            footer_keep_with_next = [False for _ in footer_row_data]
            footer_row_properties = [{'row_type': 'HEADING', 'SPLITTABLE': False} for _ in footer_row_data]
            footer_row_data = self.normalizeData(footer_row_data)

        r0_table_data = {
            'row_data': data[:r0_end] + footer_row_data,
            'row_variables': self.variables[:r0_end] + footer_row_variables,
            'row_properties': self.properties[:r0_end] + footer_row_properties,
            'keep_with_next': self.keep_with_next[:r0_end] + footer_keep_with_next,

        }

        r0 = EnhancedTable(r0_table_data,
                           col_widths=self._colWidths,
                           row_heights=self._argH[:r0_end] + footer_row_heights,
                           cell_styles=self._cellStyles[:r0_end] + footer_cell_styles,
                           repeat_rows=repeat_rows, repeat_cols=repeat_cols,
                           split_by_row=split_by_row, normalized_data=1,
                           ident=ident,
                           min_rows_after_header=self.min_rows_after_header,
                           min_rows_before_total=self.min_rows_before_total,
                           _calc_row_splits=False)

        # copy the commands

        A = []
        # hack up the line commands
        for op, (sc, sr), (ec, er), weight, color, cap, dash, join, count, space in self._linecmds:

            if isinstance(sr, string_types) and sr.startswith('split'):
                A.append((op, (sc, sr), (ec, sr), weight, color, cap, dash, join, count, space))
                if sr == 'splitlast':
                    sr = er = n - 1
                elif sr == 'splitfirst':
                    sr = n
                    er = n

            if sc < 0:
                sc = sc + self._ncols
            if ec < 0:
                ec = ec + self._ncols
            if sr < 0:
                sr = sr + self._nrows
            if er < 0:
                er = er + self._nrows

            if op in ('BOX', 'OUTLINE', 'GRID'):
                if sr < n <= er:
                    # we have to split the BOX
                    A.append(('LINEABOVE', (sc, sr), (ec, sr), weight, color, cap, dash, join, count, space))
                    A.append(('LINEBEFORE', (sc, sr), (sc, er), weight, color, cap, dash, join, count, space))
                    A.append(('LINEAFTER', (ec, sr), (ec, er), weight, color, cap, dash, join, count, space))
                    A.append(('LINEBELOW', (sc, er), (ec, er), weight, color, cap, dash, join, count, space))
                    if op == 'GRID':
                        A.append(('LINEBELOW', (sc, n - 1), (ec, n - 1), weight, color, cap, dash, join, count, space))
                        A.append(('LINEABOVE', (sc, n), (ec, n), weight, color, cap, dash, join, count, space))
                        A.append(('INNERGRID', (sc, sr), (ec, er), weight, color, cap, dash, join, count, space))
                else:
                    A.append((op, (sc, sr), (ec, er), weight, color, cap, dash, join, count, space))
            elif op in ('INNERGRID', 'LINEABOVE'):
                if sr < n <= er:
                    A.append(('LINEBELOW', (sc, n - 1), (ec, n - 1), weight, color, cap, dash, join, count, space))
                    A.append(('LINEABOVE', (sc, n), (ec, n), weight, color, cap, dash, join, count, space))
                A.append((op, (sc, sr), (ec, er), weight, color, cap, dash, join, count, space))
            elif op == 'LINEBELOW':
                if sr < n and er >= (n - 1):
                    A.append(('LINEABOVE', (sc, n), (ec, n), weight, color, cap, dash, join, count, space))
                A.append((op, (sc, sr), (ec, er), weight, color))
            elif op == 'LINEABOVE':
                if sr <= n <= er:
                    A.append(('LINEBELOW', (sc, n - 1), (ec, n - 1), weight, color, cap, dash, join, count, space))
                A.append((op, (sc, sr), (ec, er), weight, color, cap, dash, join, count, space))
            else:
                A.append((op, (sc, sr), (ec, er), weight, color, cap, dash, join, count, space))

        # The following add back all the row commands (munged above) for the first n rows
        r0._cr_0(n, A, self._nrows)
        r0._cr_0(n, self._bkgrndcmds, self._nrows)
        r0._cr_0(n, self._spanCmds, self._nrows)
        r0._cr_0(n, self._nosplitCmds, self._nrows)

        # Now we need to add any footer styles back on to the end (with all their cell ranges shifted)
        r0._add_offset_commands(n, footer_row_styles)

        header_row_data = []
        header_row_heights = []
        header_row_styles = []
        header_cell_styles = []
        header_row_variables = []
        header_row_properties = []
        header_keep_with_next = []
        if self.header is not None:
            try:
                header_row_data = self.merge_variables_into_data(self.header.row_data, self.variables[n - 1])
            except (IndexError, KeyError):
                # If there are no variables supplied (i.e. its a static header)
                header_row_data = self.header.row_data
            header_row_heights = self.header.row_heights
            header_row_styles = self.header.row_styles
            header_cell_styles = self.header.cell_styles
            header_row_variables = [{} for _ in header_row_data]
            header_keep_with_next = [False for _ in header_row_data]
            header_row_properties = [{'row_type': 'HEADING', 'SPLITTABLE': False} for _ in header_row_data]
            header_row_data = self.normalizeData(header_row_data)

        # Construct the R1 row data, heights and cell styles.
        # NB. this should work even if repeatRows is 0 (resulting in empty lists, which collapse to nothing)

        r1_table_data = {
            'row_data': data[:repeat_rows] + header_row_data + data[n:],
            'row_variables': [{} for _ in range(0, len(data[:repeat_rows]))] +
                             header_row_variables + self.variables[n:],
            'row_properties': [{} for _ in range(0, len(data[:repeat_rows]))] +
                              header_row_properties + self.properties[n:],
            'keep_with_next': [{} for _ in range(0, len(data[:repeat_rows]))] +
                              header_keep_with_next + self.keep_with_next[n:],
        }

        r1_row_heights = self._argH[:repeat_rows] + header_row_heights + self._argH[n:]
        r1_cell_styles = self._merge_cell_styles(first=self._cellStyles[:repeat_rows],
                                                 headers=header_cell_styles,
                                                 last=self._cellStyles[n:])
        r1 = EnhancedTable(r1_table_data,
                           col_widths=self._colWidths,
                           row_heights=r1_row_heights,
                           repeat_rows=repeat_rows, repeat_cols=repeat_cols,
                           split_by_row=split_by_row, normalized_data=1,
                           cell_styles=r1_cell_styles,
                           ident=ident,
                           header=self.header,
                           footer=self.footer,
                           min_rows_after_header=self.min_rows_after_header,
                           min_rows_before_total=self.min_rows_before_total,
                           _calc_row_splits=False)

        # Need to account for any header rows added when we call the following otherwise the row
        # styles will get out of step

        header_rows = len(header_row_data)
        if repeat_rows > 0 or header_rows > 0:
            # the method _cr_1_1_enhaced moves all table row commands (styles) down by adjusting their ranges
            # It leaves styles affecting rows 0 - repeat_rows
            r1._cr_1_1_enhanced(n, repeat_rows, header_rows, A)
            r1._cr_1_1_enhanced(n, repeat_rows, header_rows, self._bkgrndcmds)
            r1._cr_1_1_enhanced(n, repeat_rows, header_rows, self._spanCmds)
            r1._cr_1_1_enhanced(n, repeat_rows, header_rows, self._nosplitCmds)
        else:
            # the method _cr_1_0 moves all line commands down up by n rows
            r1._cr_1_0(n - header_rows, A)
            r1._cr_1_0(n - header_rows, self._bkgrndcmds)
            r1._cr_1_0(n - header_rows, self._spanCmds)
            r1._cr_1_0(n - header_rows, self._nosplitCmds)

        # Now we need to add back in the styles for the header rows (leaving their start/end positions as-is).
        if header_rows:
            r1._add_offset_commands(repeat_rows, header_row_styles)

        r0.hAlign = r1.hAlign = self.hAlign
        r0.vAlign = r1.vAlign = self.vAlign
        self.onSplit(r0)
        self.onSplit(r1)

        if insert_pagebreak:
            return [r0, PageBreak(), r1]
        else:
            return [r0, r1]

    def _merge_cell_styles(self, first, headers, last):
        if len(headers) == 0:
            return first + last

        if len(first) > 0:
            col_len = len(first[0])
        elif len(last) > 0:
            col_len = len(last[0])
        else:
            col_len = 0

        headers_mod = []
        for row in headers:
            header_col_len = len(row)
            if header_col_len != col_len:
                for x in range(header_col_len, col_len):
                    row.append(CellStyle('header_footer'))

            headers_mod.append(row)

        return first + headers_mod + last

    def _calc_nosplit_positions(self, _calc_row_splits):
        no_split_cmds = []
        if _calc_row_splits is True:
            # Calculate which rows are splittable based on row types as (possibly) supplied in properties
            # Add appropriate NOSPLIT commands for each one

            num_rows = len(self.data)
            for i in range(num_rows):
                row_type = self.properties[i].get('row_type', 'data').upper()
                if self.properties[i].get('nosplit', False):
                    no_split_cmds.append(('NOSPLIT', (0, i), (-1, i + 1),))
                elif row_type == 'BLANK':
                    # Don't allow the table to split just before a blank row since this means that you get a blank
                    # as the first row of the next page which a) looks dodgy and b) is hard to remove in code
                    # since all the other row styles would need adjusting. Blank lines appearing as the last row are ok
                    # as they will be removed and replaced with PageBreak objects in _splitRows
                    no_split_cmds.append(('NOSPLIT', (0, i - 1), (-1, i)))
                elif row_type in ('HEADER', 'HEADING'):
                    no_split_cmds.append(('NOSPLIT', (0, i), (-1, i + self.min_rows_after_header)))
                elif row_type == 'TOTAL':
                    no_split_cmds.append(('NOSPLIT', (-1, i - self.min_rows_before_total), (0, i)))

        return no_split_cmds

    def drawOn(self, canvas, x, y, _sW=0):
        if self.pos_x is not None and self.pos_y is not None:
            x = float(self.pos_x)
            y = float(self.pos_y)

        return super(EnhancedTable, self).drawOn(canvas, x, y, _sW)

    def wrap(self, availWidth, availHeight):
        self._calc(availWidth, availHeight)
        self.availWidth = availWidth
        if self.pos_x is not None and self.pos_y is not None:
            self._height = 0
            self.availWidth = availWidth - float(self.pos_x)

        return self._width, self._height

    def calc_height_of_table(self, availHeight, availWidth, H=None, W=None):
        H = self._argH
        if not W:
            W = _calc_pc(self._argW, availWidth)  # widths array

        hmax = lim = len(H)
        longTable = self._longTableOptimize

        if None in H or OVERFLOW_ROW in H or UNDEFINED_ROW in H:
            canv = getattr(self, 'canv', None)
            saved = None
            # get a handy list of any cells which span rows. should be ignored for sizing
            if self._spanCmds:
                rowSpanCells = self._rowSpanCells
                colSpanCells = self._colSpanCells
                spanRanges = self._spanRanges
                colpositions = self._colpositions
            else:
                rowSpanCells = colSpanCells = ()
                spanRanges = {}
            if canv:
                saved = canv._fontname, canv._fontsize, canv._leading
            H0 = H
            H = H[:]  # make a copy as we'll change it
            self._rowHeights = H
            spanCons = {}
            FUZZ = rl_config._FUZZ

            find_types = []
            if None in H:
                find_types.append(None)
            if OVERFLOW_ROW in H:
                find_types.append(OVERFLOW_ROW)
            if UNDEFINED_ROW in H:
                find_types.append(UNDEFINED_ROW)

            while None in H or OVERFLOW_ROW in H or UNDEFINED_ROW in H:
                i = None
                next_find_type = None
                for find_type in find_types:
                    if find_type in H:
                        find_type_index = H.index(find_type)
                        if i is None or find_type_index < i:
                            i = find_type_index
                            next_find_type = find_type

                V = self._cellvalues[i]  # values for row i
                S = self._cellStyles[i]  # styles for row i
                h = 0
                j = 0

                for j, (v, s, w) in enumerate(list(zip(V, S, W))):  # value, style, width (lengths must match)
                    ji = j, i
                    if next_find_type == OVERFLOW_ROW:
                        s.leading = 1
                    span = spanRanges.get(ji, None)
                    if ji in rowSpanCells and not span:
                        continue  # don't count it, it's either occluded or unreliable
                    else:
                        if isinstance(v, (tuple, list, Flowable)):
                            if isinstance(v, Flowable):
                                v = (v,)
                            else:
                                v = flatten(v)
                            v = V[j] = self._cellListProcess(v, w, None)
                            if w is None and not self._canGetWidth(v):
                                raise ValueError("Flowable %s in cell(%d,%d) can't have auto width in\n%s" % (
                                    v[0].identity(30), i, j, self.identity(30)))
                            if canv:
                                canv._fontname, canv._fontsize, canv._leading = s.fontname, s.fontsize, s.leading or 1.2 * s.fontsize
                            if ji in colSpanCells:
                                if not span:
                                    continue
                                w = max(colpositions[span[2] + 1] - colpositions[span[0]], w)
                            dW, t = self._listCellGeom(v, w or self._listValueWidth(v), s)
                            if canv:
                                canv._fontname, canv._fontsize, canv._leading = saved
                            dW = dW + s.leftPadding + s.rightPadding
                            if not rl_config.allowTableBoundsErrors and dW > w:
                                from reportlab.platypus.doctemplate import LayoutError
                                raise LayoutError(
                                    "Flowable %s (%sx%s points) too wide for cell(%d,%d) (%sx* points) in\n%s" % (
                                        v[0].identity(30), fp_str(dW), fp_str(t), i, j, fp_str(w), self.identity(30)))
                        else:
                            v = (v is not None and str(v) or '').split("\n")
                            t = (s.leading or 1.2 * s.fontsize) * len(v)
                        t += s.bottomPadding + s.topPadding
                        if span:
                            r0 = span[1]
                            r1 = span[3]
                            if r0 != r1:
                                x = r0, r1
                                spanCons[x] = max(spanCons.get(x, t), t)
                                t = 0
                    if t > h:
                        h = t  # record a new maximum
                H[i] = h
                # we can stop if we have filled up all available room
                if longTable:
                    hmax = i + 1  # we computed H[i] so known len == i+1
                    height = int(sum(H[:hmax]) + 0.5)
                    i_avail_height = int(availHeight + 0.5)
                    if height > i_avail_height:
                        # we can terminate if all spans are complete in H[:hmax]
                        if spanCons:
                            msr = max(x[1] for x in spanCons.keys())  # RS=[endrowspan,.....]
                            if hmax > msr:
                                while None in H:
                                    next_none = H.index(None)
                                    H[next_none] = UNDEFINED_ROW
                                break
            if UNDEFINED_ROW not in H and OVERFLOW_ROW not in H:
                hmax = lim

            if spanCons:
                try:
                    spanFixDim(H0, H, spanCons)
                except:
                    annotateException(
                        '\nspanning problem in %s hmax=%s lim=%s avail=%s x %s\nH0=%r H=%r\nspanCons=%r' % (
                            self.identity(), hmax, lim, availWidth, availHeight, H0, H, spanCons))

        # iterate backwards through the heights to get rowpositions in reversed order
        self._rowpositions = j = []
        height = c = 0

        for i in range(hmax - 1, -1, -1):
            j.append(height)
            y = H[i] - c
            t = height + y
            c = (t - height) - y
            height = t
        j.append(height)
        j.reverse()  # reverse the reversed list of row positions
        return height, hmax

    def _calc_height(self, availHeight, availWidth, H=None, W=None):
        height, height_max = self.calc_height_of_table(availHeight, availWidth, H, W)
        self._height = height
        self._hmax = height_max

    def get_height(self):
        height, _ = self.calc_height_of_table(10000, 10000)
        return height

    def get_width(self):
        self._calc_width(10000)
        return self._width

    def spanFixDim(self, V0, V, spanCons, lim=None, FUZZ=rl_config._FUZZ):
        """
        Assigned the row height to row span fields. Report lab version equalised the spacing across all
        reports. We changed this to only do it on the last row of the col span
        :param V0:
        :param V:
        :param spanCons:
        :param lim:
        :param FUZZ:
        :return:
        """

        # assign required space to variable rows equally to existing calculated values
        M = {}
        if not lim:
            lim = len(V0)  # in longtables the row calcs may be truncated

        # we assign the largest spaces first hoping to get a smaller result
        for v, (x0, x1) in reversed(sorted(((iv, ik) for ik, iv in spanCons.items()))):
            if x0 >= lim:
                continue
            x1 += 1
            t = sum([V[x] + M.get(x, 0) for x in range(x0, x1-1)])

            if t >= v - FUZZ:
                continue  # already good enough

            X = [x for x in range(x0, x1) if V0[x] is None]  # variable candidates
            if not X:
                continue  # something wrong here mate

            M[X[-1]] = v - t

        for x, v in M.items():
            V[x] = v
