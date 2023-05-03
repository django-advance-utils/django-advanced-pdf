import copy
import re
from io import StringIO, BytesIO
from time import sleep

from lxml import etree
from reportlab.lib.colors import HexColor, black
from reportlab.lib.units import mm
from reportlab.platypus import TableStyle, PageBreak, Spacer, Table

from .enhanced_paragraph.enhanced_paragraph import EnhancedParagraph
from .enhanced_paragraph.style import EnhancedParagraphStyle
from .enhanced_table.data import EnhancedTableData
from .enhanced_table.enhanced_tables import OVERFLOW_ROW, EnhancedTable, HEADER_FOOTER, KEEP_TYPE_END, KEEP_TYPE_START, \
    KEEP_TYPE_MIDDLE, KEEP_TYPE_SPAN, KEEP_TYPE_NA
from .png_images import insert_image, insert_obj
from .svglib.svglib import SvgRenderer
from .utils import DocTemplate, get_page_size_from_string, intcomma_currency, ColumnWidthPercentage
from ..pagers.base import BasePager
from ..pagers.border import BorderPager


class ReportXML(object):
    pager_types = {'borders': BorderPager}
    default_pager = BasePager

    entities = [
        (u'lsquo', u'‘'),
        (u'rsquo', u'’'),
        (u'ldquo', u'“'),
        (u'rdquo', u'”'),
        (u'quot', u'"'),
        (u'frasl', u'/'),
        (u'hellip', u'…'),
        (u'ndash', u'–'),
        (u'mdash', u'—'),
        (u'nbsp', u' '),
        (u'not', u'¬'),
        (u'iexcl', u'¡'),
        (u'cent', u'¢'),
        (u'pound', u'£'),
        (u'euro', u'€'),
        (u'curren', u'¤'),
        (u'yen', u'¥'),
        (u'brvbar', u'¦'),
        (u'sect', u'§'),
        (u'uml', u'¨'),
        (u'die', u'¨'),
        (u'copy', u'©'),
        (u'ordf', u'ª'),
        (u'laquo', u'«'),
        (u'reg', u'®'),
        (u'plusmn', u'±'),
        (u'sup2', u'²'),
        (u'sup3', u'³'),
        (u'frac14', u'¼'),
        (u'frac12', u'½'),
        (u'frac34', u'¾'),
        (u'rsquo', u'’'),
    ]

    def __init__(self, object_lookup=None, pager_kwargs=None, test_mode=False, status_method=None):
        self.styles = {}
        if object_lookup is not None:
            self.object_lookup = object_lookup
        else:
            self.object_lookup = {}
        self.background_image_first = None
        self.background_image_remaining = None
        self.background_image_footer = None

        self.styles = {}
        self.border_left_first = 0
        self.border_right_first = 0
        self.border_top_first = 0
        self.border_bottom_first = 0
        self.border_left_continuation = 0
        self.border_right_continuation = 0
        self.border_top_continuation = 0
        self.border_bottom_continuation = 0
        self.page_style = None
        self.test_mode = test_mode
        self.status_method = status_method

        if pager_kwargs is None:
            self.pager_kwargs = {}
        else:
            self.pager_kwargs = pager_kwargs

    def load_xml_and_make_pdf(self, xml, add_doctype=True, background_image_first=None,
                              background_image_remaining=None, background_image_footer=None):

        self.background_image_first = background_image_first
        self.background_image_remaining = background_image_remaining
        self.background_image_footer = background_image_footer

        self.update_status("Loading")
        parser = etree.XMLParser(remove_blank_text=True, resolve_entities=False)

        if add_doctype:
            xml = self.get_doc_type() + xml
        tree = etree.parse(StringIO(xml), parser)
        root = tree.getroot()
        result = BytesIO()
        self.make_pdf(root, result)
        result.seek(0)
        return result

    def get_object(self, object_id):
        if object_id in self.object_lookup.keys():
            return self.object_lookup[object_id]
        else:
            try:
                object_id = int(object_id)
                if object_id in self.object_lookup.keys():
                    return self.object_lookup[object_id]
            except ValueError:
                pass
                # if 'default' in self.object_lookup.keys():
                #     return self.object_lookup['default']
        return None

    def make_pdf(self, root_element, file_buffer):
        title = root_element.get('title')
        page_size = get_page_size_from_string(root_element.get('page_size', ''),
                                              root_element.get('page_orientation', ''))
        pager = self.setup_pager(page_size=page_size,
                                 root_element=root_element)
        doc = DocTemplate(title,
                          pager,
                          file_buffer,
                          pagesize=page_size)
        story = []
        page_width = (pager.page_width() - pager.pageused.left - pager.pageused.right) / mm
        page_height = (pager.page_height() - pager.pageused.top - pager.page_used_bottom()) / mm
        self.process_xml(root_element=root_element,
                         story=story,
                         page_width=page_width,
                         page_height=page_height,
                         top_border=pager.pageused.top,
                         bottom_border=pager.pageused.bottom)
        doc.build(story, canvasmaker=self.canvasmaker)

    def get_pager(self, *args, **kwargs):
        return self.pager_types.get(self.page_style, self.default_pager)(*args, **kwargs)

    def setup_pager(self, page_size, root_element):
        title = root_element.get('title')
        self.page_style = root_element.get('page_style')

        self.border_left_first = float(root_element.get('border_left_first', 0))
        self.border_right_first = float(root_element.get('border_right_first', 0))
        self.border_top_first = float(root_element.get('border_top_first', 0))
        self.border_bottom_first = float(root_element.get('border_bottom_first', 0))

        self.border_left_continuation = float(root_element.get('border_left_continuation',
                                                               self.border_left_first))
        self.border_right_continuation = float(root_element.get('border_right_continuation',
                                                                self.border_right_first))
        self.border_top_continuation = float(root_element.get('border_top_continuation',
                                                              self.border_top_first))
        self.border_bottom_continuation = float(root_element.get('border_bottom_continuation',
                                                                 self.border_bottom_first))

        for name, value in root_element.attrib.items():
            if name.startswith('pager_'):
                name = name[6:]
                if name not in self.pager_kwargs:
                    self.pager_kwargs[name] = value

        return self.get_pager(heading=title,
                              filename=title,
                              pagesize=page_size,
                              border_left_first=self.border_left_first * mm,
                              border_right_first=self.border_right_first * mm,
                              border_top_first=self.border_top_first * mm,
                              border_bottom_first=self.border_bottom_first * mm,
                              border_left_continuation=self.border_left_continuation * mm,
                              border_right_continuation=self.border_right_continuation * mm,
                              border_top_continuation=self.border_top_continuation * mm,
                              border_bottom_continuation=self.border_bottom_continuation * mm,
                              background_image_first=self.background_image_first,
                              background_image_remaining=self.background_image_remaining,
                              background_image_footer=self.background_image_footer,
                              test_mode=self.test_mode,
                              status_method=self.update_status,
                              **self.pager_kwargs)

    def canvasmaker(self, *args, **kwargs):
        return self.get_pager(*args,
                              footer_field='',
                              border_left_first=self.border_left_first * mm,
                              border_right_first=self.border_right_first * mm,
                              border_top_first=self.border_top_first * mm,
                              border_bottom_first=self.border_bottom_first * mm,
                              border_left_continuation=self.border_left_continuation * mm,
                              border_right_continuation=self.border_right_continuation * mm,
                              border_top_continuation=self.border_top_continuation * mm,
                              border_bottom_continuation=self.border_bottom_continuation * mm,
                              background_image_first=self.background_image_first,
                              background_image_remaining=self.background_image_remaining,
                              background_image_footer=self.background_image_footer,
                              test_mode=self.test_mode,
                              status_method=self.update_status,
                              **self.pager_kwargs,
                              **kwargs)

    def process_xml(self, root_element, story, page_width, page_height, top_border, bottom_border):
        self.styles = {}
        children = root_element.getchildren()

        for child in children:
            if child.tag.lower() == "table":
                table = self.process_table(child,
                                           table_width=page_width,
                                           page_height=page_height,
                                           page_width=page_width,
                                           top_border=top_border,
                                           bottom_border=bottom_border)
                if table is not None:
                    story.append(table)

            elif child.tag.lower() == "style":
                self.process_style_element(child.text)
            elif child.tag.lower() == "p":
                story.append(self.process_paragraph_element(child))
            elif child.tag.lower() == "page_break":
                story.append(PageBreak())
            elif child.tag.lower() == "spacer":
                story.append(self.process_spacer_tag(child))

    def process_style_element(self, style_text):
        """
        This implement the style element just like CSS in html does
        :param style_text:
        """
        for match in re.finditer(r"(\w+)[\s\r\n]*{([:;\w\s\r\n-.,]+)\}", style_text):
            style_name = match.group(1)
            style_css = match.group(2)
            style_css = style_css.strip(" \r\n")
            self.styles[style_name] = style_css

    def process_table(self, table, table_width, page_height=None, page_width=None, top_border=None, bottom_border=None):
        """
        This implements tables using EnhanceTable
        :param page_height:
        :param page_width:
        :param table:
        :param table_width:
        :param top_border:
        :param bottom_border:
        """
        main_data = []
        main_styles = []
        main_span = {}

        headers = []
        footers = []

        headers_index = []
        footers_index = []
        current_header_index = None
        current_footer_index = None

        row_heights = []
        keep_data = []
        other_styles = {}
        held_cells = {}

        self.process_css_for_table(table, main_styles, other_styles)

        if self.get_boolean_value(table.get('hidden')):
            return None

        min_rows_top = int(table.get('min_rows_top', 0))
        min_rows_bottom = int(table.get('min_rows_bottom', 0))

        rows_variables = []
        variables = {}

        row_count = -1
        col_widths = []

        layout_widths = table.get('layout_widths')
        if layout_widths is not None:
            for col_width in layout_widths.split(','):
                col_widths.append(self.set_column_width(col_width))

        pos_x = table.get('pos_x')
        pos_y = table.get('pos_y')

        held_row_span = 1
        hidden_columns = set()

        for element in table:
            if element.tag == 'tr':
                row_count += 1
                max_row_span, overflow_row_count = self.process_tr(tr_element=element,
                                                                   data=main_data,
                                                                   styles=main_styles,
                                                                   other_table_styles=other_styles,
                                                                   row_heights=row_heights,
                                                                   row_count=row_count,
                                                                   span=main_span,
                                                                   rows_variables=rows_variables,
                                                                   variables=variables,
                                                                   col_widths=col_widths,
                                                                   table_width=table_width,
                                                                   hidden_columns=hidden_columns,
                                                                   held_cells=held_cells)

                if max_row_span > held_row_span:
                    held_row_span = max_row_span

                if held_row_span > 1 or min_rows_top > 0:
                    min_rows_top -= 1
                    keep_type = KEEP_TYPE_SPAN
                else:
                    keep_type = KEEP_TYPE_NA
                for _ in range(overflow_row_count + 1):
                    keep_data.append(keep_type)
                    headers_index.append(current_header_index)
                    footers_index.append(current_footer_index)

                held_row_span -= 1
                row_count += overflow_row_count
            elif element.tag == 'keep':
                local_keep_data = []
                keep_type = KEEP_TYPE_START
                for child_element in element:
                    if child_element.tag == 'tr':
                        row_count += 1
                        max_row_span, overflow_row_count = self.process_tr(tr_element=child_element,
                                                                           data=main_data,
                                                                           styles=main_styles,
                                                                           other_table_styles=other_styles,
                                                                           row_heights=row_heights,
                                                                           row_count=row_count,
                                                                           span=main_span,
                                                                           rows_variables=rows_variables,
                                                                           variables=variables,
                                                                           col_widths=col_widths,
                                                                           table_width=table_width,
                                                                           hidden_columns=hidden_columns,
                                                                           held_cells=held_cells)
                        if max_row_span > held_row_span:
                            held_row_span = max_row_span
                        if held_row_span > 1 or min_rows_top > 0:
                            min_rows_top -= 1

                        for index in range(overflow_row_count + 1):
                            headers_index.append(current_header_index)
                            footers_index.append(current_footer_index)
                            local_keep_data.append(keep_type)
                            keep_type = KEEP_TYPE_MIDDLE

                        held_row_span -= 1
                        row_count += overflow_row_count

                if len(local_keep_data) > 0:
                    local_keep_data[-1] = KEEP_TYPE_END
                keep_data += local_keep_data

            elif element.tag == 'no_headers':
                current_header_index = None

            elif element.tag == 'no_footers':
                current_footer_index = None

            elif element.tag in ['header', 'footer']:
                is_header = element.tag == 'header'
                output = element.get('output', "0")
                if is_header and self.get_boolean_value(output):
                    for tr in element:
                        row_count += 1
                        _, overflow_row_count = self.process_tr(tr_element=tr,
                                                                data=main_data,
                                                                styles=main_styles,
                                                                other_table_styles=other_styles,
                                                                row_heights=row_heights,
                                                                row_count=row_count,
                                                                span=main_span,
                                                                rows_variables=rows_variables,
                                                                variables=variables,
                                                                held_cells=held_cells,
                                                                col_widths=col_widths,
                                                                hidden_columns=hidden_columns,
                                                                table_width=table_width)
                header_footer_span = {}
                header_footer_data = []
                header_footer_commands = []
                header_footer_row_height = []
                temp_rows_variables = []

                for row_index, tr in enumerate(element, HEADER_FOOTER):
                    self.process_tr(tr_element=tr,
                                    data=header_footer_data,
                                    styles=header_footer_commands,
                                    other_table_styles=other_styles,
                                    row_heights=header_footer_row_height,
                                    row_count=row_index,
                                    span=header_footer_span,
                                    rows_variables=temp_rows_variables,
                                    variables=variables,
                                    col_widths=col_widths,
                                    table_width=table_width,
                                    default_row_height=35,
                                    is_header_or_footer=True,
                                    hidden_columns=hidden_columns)

                enhanced_table_data = EnhancedTableData(row_data=header_footer_data,
                                                        row_heights=header_footer_row_height,
                                                        commands=header_footer_commands)

                if is_header:
                    current_header_index = len(headers)
                    headers.append(enhanced_table_data)
                else:
                    current_footer_index = len(footers)
                    footers.append(enhanced_table_data)

        length = len(keep_data)
        for x in range(1, min_rows_bottom + 1):
            if length - x < 0:
                break
            keep_data[length - x] = KEEP_TYPE_SPAN

        h_align, v_align = self.get_alignment_details(main_styles)

        new_column_widths = self.process_column_widths(col_widths, table_width)

        if main_data:
            t = EnhancedTable(table_data={'row_data': main_data,
                                          'row_variables': rows_variables,
                                          'keep_with_next': keep_data,
                                          'headers_index': headers_index,
                                          'footers_index': footers_index},
                              row_heights=row_heights,
                              repeat_rows=0,
                              headers=headers,
                              footers=footers,
                              h_align=h_align,
                              v_align=v_align,
                              col_widths=new_column_widths,
                              initial=True)
        else:
            return None

        if pos_y is not None and pos_x is not None and page_height is not None:
            ref_is_top = table.get('pos_y_ref', 'top') == 'top'
            ref_is_right = table.get('pos_x_ref', 'left') == 'right'
            ignore_margin = table.get('ignore_margin', 'no') == 'yes'
            if ref_is_top:
                page_height *= mm
                page_height += top_border + bottom_border
                height = t.get_height()
                new_pos_y = page_height - (float(pos_y) + height)
                if not ignore_margin and top_border is not None:
                    new_pos_y -= float(top_border)
            else:
                new_pos_y = float(pos_y)
                if not ignore_margin and bottom_border is not None:
                    new_pos_y += float(bottom_border)
            t.pos_y = str(new_pos_y)

            if ref_is_right:
                page_width *= mm
                width = t.get_width()
                new_pos_x = page_width - (float(pos_x) + width)
            else:
                new_pos_x = pos_x
            t.pos_x = str(new_pos_x)

        t.setStyle(TableStyle(main_styles))

        return t

    @staticmethod
    def coord(x, y):
        """
        http://stackoverflow.com/questions/4726011/wrap-text-in-a-table-reportlab
        Helper class to help position flowables in Canvas objects
        """
        x, y = x * mm, 222 - y * mm
        return x, y

    def process_tr(self, tr_element, data, styles, other_table_styles,
                   row_heights, row_count, span, rows_variables, variables, col_widths, table_width, hidden_columns,
                   held_cells=None, default_row_height=None, is_header_or_footer=False):

        max_row_span = 0
        if self.get_boolean_value(tr_element.get('hidden')):
            return max_row_span, 0

        row_data = []
        other_styles = {}

        self.process_css_for_table(tr_element, styles, other_styles, start_row=row_count, end_row=row_count)
        offset = 0
        max_row_span = 0

        overflow_rows = []
        overflow_row_count = 0

        row_variables = copy.copy(variables)
        for variables_element in tr_element.iter('variables'):
            for variable in variables_element.attrib:
                value = variables_element.get(variable)
                variables[variable] = value
                row_variables[variable] = value

        for variable_element in tr_element.iter('variable'):
            variable = variable_element.attrib.get('name', '')
            value = variable_element.text
            variables[variable] = value
            row_variables[variable] = value

        for variables_element in tr_element.iter('currency_variables'):
            symbol = variables_element.attrib.get('symbol', '')

            for variable in variables_element.attrib:
                if variable == 'symbol':
                    continue
                value = float(variables_element.get(variable))
                variables[variable] = value
                row_variables[variable] = value

                symbol_name = variable + '__symbol'
                variables[symbol_name] = symbol
                row_variables[symbol_name] = symbol

                currency_variable = variable + '__currency'
                currency_value = symbol + intcomma_currency(value)

                variables[currency_variable] = currency_value
                row_variables[currency_variable] = currency_value

        for variables_element in tr_element.iter('variable_addition'):
            for variable in variables_element.attrib:
                try:
                    if variables.get(variable) is None:
                        variables[variable] = float(variables_element.get(variable))
                    else:
                        variables[variable] = float(variables.get(variable)) + float(variables_element.get(variable))
                except ValueError:
                    pass
                row_variables[variable] = variables.get(variable)
                currency_variable = variable + '__currency'
                if currency_variable in variables:
                    symbol_name = variables[variable + '__symbol']

                    currency_value = symbol_name + intcomma_currency(float(variables.get(variable)) / 100.0)

                    row_variables[currency_variable] = currency_value
                    variables[currency_variable] = currency_value

        rows_variables.append(row_variables)
        col_count = 0
        for index, td_element in enumerate(tr_element, 0):

            if td_element.tag != 'td':
                continue

            name = td_element.get('name')
            if name is not None and name in hidden_columns:
                continue
            if index in hidden_columns:
                continue

            hidden_column = td_element.get('hidden_column')
            col_span = int(td_element.get('colspan', "1"))
            row_span = int(td_element.get('rowspan', "1"))

            if self.get_boolean_value(hidden_column):
                if name is not None:
                    hidden_columns.add(name)
                else:
                    for h_index in range(col_span):
                        hidden_columns.add(index + h_index)
                continue
            if td_element.get('hidden'):
                continue

            if len(col_widths) < col_count + 1:
                col_widths.append(None)

            # check that cell is not marked as a rowspan
            p_offset = span.get('%d-%d' % (row_count, col_count + offset), None)
            while p_offset is not None and p_offset > 0:
                for x in range(0, p_offset):
                    row_data.append('')
                offset += p_offset
                p_offset = span.get('%d-%d' % (row_count, col_count + offset), None)

            if row_span > max_row_span:
                max_row_span = row_span

            # get the styles for td
            self.process_css_for_table(td_element, styles, other_styles,
                                       start_col=col_count + offset, start_row=row_count,
                                       end_col=col_count + offset + col_span - 1, end_row=row_count + row_span - 1)

            if len(td_element) > 0 and td_element[0].tag == 'table':
                new_table_column_widths = self.process_column_widths(col_widths, table_width)
                new_table_column_width = 0
                new_table_column_widths_count = len(new_table_column_widths)
                if index < new_table_column_widths_count:
                    for col_num in range(index, index + col_span):
                        if col_num > new_table_column_widths_count:
                            break
                        try:
                            new_table_column_width += new_table_column_widths[col_num + offset] / mm
                        except IndexError:
                            pass

                else:
                    new_table_column_width = new_table_column_widths[0] / mm
                padding = int(self.get_padding_for_cell(styles,
                                                        start_col=col_count + offset,
                                                        start_row=row_count,
                                                        end_col=-col_count + offset + col_span - 1,
                                                        end_row=-row_count + row_span - 1) / mm)
                display_object = self.process_table(td_element[0], new_table_column_width - padding)
                if display_object is None:
                    display_object = ''
            elif len(td_element) > 0 and td_element[0].tag[-3:] == 'svg':
                display_object = self.svg2rlg_from_node(td_element[0])
            elif len(td_element) > 0 and td_element[0].tag[-3:] == 'png':
                display_object = insert_image(td_element[0])
            elif len(td_element) > 0 and td_element[0].tag[-3:] == 'obj':
                object_id = td_element[0].get('id', "")
                if object_id != "":
                    display_object = self.get_object(object_id)
                else:
                    display_object = insert_obj(td_element[0])
            elif len(td_element) > 0 and td_element[0].tag[-12:] == 'currency_qty':
                variable_name = td_element[0].get('variable')
                qty = int(td_element[0].get('qty'))

                if variable_name is not None:
                    symbol = ''
                    value = variables[variable_name]
                    if symbol == '':
                        symbol = variables.get(variable_name + '__symbol', '')
                else:
                    symbol = td_element[0].get('symbol', '')
                    if symbol == '':
                        symbol_from = td_element[0].get('symbol_from', '')
                        symbol = variables.get(symbol_from + '__symbol', '')
                    value = td_element[0].get('value')

                unit = (float(value) / qty) / 100.0

                display_str = '%s%s' % (symbol, intcomma_currency(unit, show_more_decimal_places=True))

                style = self.process_css_for_table_paragraph_style(styles, row_count, col_count + offset)
                display_object = EnhancedParagraph(display_str, style, css_classes=self.styles)

            elif len(td_element) > 0 and td_element[0].tag[-8:] == 'currency':
                variable_name = td_element[0].get('variable')
                if is_header_or_footer:
                    variable_name = td_element[0].get('variable')
                    if variable_name is not None:
                        display_object = '%%(%s__currency)s' % variable_name
                    else:
                        value = int(td_element[0].get('value'))
                        number_string = "%.2f" % (float(value) / 100.0)
                        display_object = '%s' % (intcomma_currency(number_string))

                else:
                    if variable_name is not None:
                        symbol = ''
                        value = variables.get(variable_name)
                        if symbol == '':
                            symbol = variables.get(variable_name + '__symbol', '')
                    else:
                        symbol = td_element[0].get('symbol', '')
                        value = td_element[0].get('value')

                    add_to_variable_name = td_element[0].get('add_to')

                    if add_to_variable_name is not None:
                        if symbol == '':
                            symbol = variables.get(add_to_variable_name + '__symbol', '')

                        variables[add_to_variable_name] += float(value)
                        row_variables[add_to_variable_name] = variables.get(add_to_variable_name)
                        currency_variable = add_to_variable_name + '__currency'
                        if currency_variable in variables:
                            currency_value = symbol + intcomma_currency(
                                float(variables.get(add_to_variable_name)) / 100.0)

                            row_variables[currency_variable] = currency_value
                            variables[currency_variable] = currency_value
                    if value is not None:
                        number_string = "%.2f" % (float(value) / 100.0)
                        display_object = '%s%s' % (symbol, intcomma_currency(number_string))
                    else:
                        display_object = ''

            elif len(td_element) > 0:
                xml = etree.tostring(td_element, pretty_print=True)

                overflow_gt_height = td_element.get('overflow_gt_height')
                overflow_gt_length = int(td_element.get('overflow_gt_length', 0))
                style = self.process_css_for_table_paragraph_style(styles, row_count, col_count + offset)

                if overflow_gt_height is not None:

                    display_object, overflow_row_count = self.process_overflow_height(
                        td_element=td_element,
                        index=index,
                        overflow_gt_height=overflow_gt_height,
                        xml=xml,
                        style=style,
                        col_widths=col_widths,
                        table_width=table_width,
                        col_span=col_span,
                        styles=styles,
                        offset=offset,
                        col_count=col_count,
                        row_count=row_count,
                        row_span=row_span,
                        row_data=row_data,
                        overflow_rows=overflow_rows,
                        rows_variables=rows_variables,
                        held_cells=held_cells)

                elif overflow_gt_length:
                    out_xml, style, overflow_row_count = self.overflow_cell(td_element=td_element,
                                                                            xml=xml,
                                                                            overflow_gt_length=overflow_gt_length,
                                                                            styles=styles,
                                                                            style=style,
                                                                            offset=offset,
                                                                            col_count=col_count,
                                                                            row_count=row_count,
                                                                            col_span=col_span,
                                                                            row_span=row_span,
                                                                            row_data=row_data,
                                                                            overflow_rows=overflow_rows,
                                                                            rows_variables=rows_variables)
                    display_object = EnhancedParagraph(out_xml, style, css_classes=self.styles)
                else:
                    display_object = EnhancedParagraph(xml, style, css_classes=self.styles)

            else:
                display_object = td_element.text
                if display_object is None:
                    display_object = ''

            hold_cell = td_element.get('hold_cell')
            if hold_cell is not None:
                held_cells[hold_cell] = {'display_object': display_object, 'index': index, 'colspan': col_span}
            row_data.append(display_object)

            width = self.set_column_width(td_element.get('width'))
            if width is not None:
                col_widths[col_count] = width

            if col_span > 1 or row_span > 1:
                for x in range(1, col_span):
                    row_data.append('')
                styles.append(('SPAN',
                               (col_count + offset, row_count),
                               (col_count + offset + col_span - 1, row_count + row_span - 1)))
                for x in range(1, overflow_row_count+1):
                    styles.append(('SPAN',
                                   (col_count + offset, x + row_count),
                                   (col_count + offset + col_span - 1, x + row_count + row_span - 1)))

                if row_span > 1:
                    for r in range(1, row_span):
                        span['%d-%d' % (r + row_count + overflow_row_count, col_count + offset)] = col_span
                offset += col_span - 1
            col_count += 1

        data.append(row_data)

        row_height = self.get_row_height(other_table_styles, other_styles)
        if row_height is None:
            row_height = tr_element.get('row_height', default_row_height)
            if row_height is not None:
                row_height = float(row_height)

        row_heights.append(row_height)

        for overflow_row in overflow_rows:
            data.append(overflow_row)
            row_heights.append(OVERFLOW_ROW)

        return max_row_span, overflow_row_count

    @staticmethod
    def set_column_width(col_width):
        if col_width is not None and col_width != '':
            if col_width[-1] == '%':
                width = ColumnWidthPercentage(float(col_width[:-1]))
            else:
                width = float(col_width)
            return width
        return None

    @staticmethod
    def get_row_height(other_table_styles, other_styles):
        row_height = other_styles.get('ROW_HEIGHT')
        if row_height is None:
            row_height = other_table_styles.get('ROW_HEIGHT')

        if row_height is not None:
            row_height = row_height * mm

        return row_height

    def process_css_for_table(self, tag, styles, other_styles, start_col=0, start_row=0, end_col=-1, end_row=-1,
                              style_tag_name='style', class_tag_name='class'):

        css = self.get_css_from_style_attribute(tag=tag,
                                                style_tag_name=style_tag_name,
                                                class_tag_name=class_tag_name)
        if css == '':
            return

        self.convert_css_to_style(css, styles, other_styles, start_col, start_row, end_col, end_row)

    @staticmethod
    def convert_css_to_style(css, styles, other_styles, start_col=0, start_row=0, end_col=-1, end_row=-1):
        start_tuple = (start_col, start_row)
        end_tuple = (end_col, end_row)
        styles_list = css.split(';')
        for style in styles_list:
            if style == '':
                continue
            style_type, style_detail = style.split(':')
            style_type = style_type.lower().lstrip("\r\n ")

            if style_type in ('inner_grid',
                              'box',
                              'line_above',
                              'line_below',
                              'line_before',
                              'line_after'):
                details = style_detail.split(',')
                if len(details) > 3:

                    styles.append((style_type.replace("_", "").upper(),
                                   (0, int(float(details[2]))), (-1, float(details[3]),
                                                                 float(details[0]), HexColor(details[1]))))
                elif len(details) > 2:
                    styles.append((style_type.replace("_", "").upper(), (0, int(float(details[2]))), end_tuple,
                                   float(details[0]), HexColor(details[1])))

                elif len(details) > 1:
                    styles.append((style_type.replace("_", "").upper(), start_tuple, end_tuple,
                                   float(details[0]), HexColor(details[1])))
                else:
                    styles.append((style_type.replace("_", "").upper(), start_tuple, end_tuple,
                                   float(details[0]), black))
            elif style_type in ('text_color',
                                'background'):
                styles.append((style_type.replace("_", "").upper(), start_tuple, end_tuple, HexColor(style_detail)))
            elif style_type in ('valign',
                                'halign',
                                'align'):
                styles.append((style_type.replace("_", "").upper(), start_tuple, end_tuple, style_detail.upper()))
            elif style_type in ('font',
                                'face',
                                'font_name'):
                styles.append((style_type.replace("_", "").upper(), start_tuple, end_tuple, style_detail))

            elif style_type in ('left_padding',
                                'right_padding',
                                'bottom_padding',
                                'top_padding'):
                styles.append((style_type.replace("_", "").upper(), start_tuple, end_tuple, float(style_detail) * mm))

            elif style_type in ('leading',
                                'font_size',
                                'size'):
                styles.append((style_type.replace("_", "").upper(), start_tuple, end_tuple, int(style_detail)))
            elif style_type == 'row_height':
                other_styles[style_type.upper()] = int(style_detail)

    @staticmethod
    def get_padding_for_cell(styles, start_col=0, start_row=0, end_col=-1, end_row=-1):
        start_tuple = (start_col, start_row)
        padding = 0
        found_padding = False
        for style in styles:

            style_type = style[0]
            if style_type in ('LEFTPADDING',
                              'RIGHTPADDING'):

                if start_tuple == style[1]:  # todo this isn't always going to work if defined on tr or table
                    padding += style[3]
                    found_padding = True
        if found_padding:
            return padding - 1
        return 3

    def get_css_from_style_attribute(self, tag, style_tag_name='style', class_tag_name='class'):

        style_tag = tag.get(style_tag_name)
        class_tag = tag.get(class_tag_name)

        if style_tag is None and class_tag is None:
            return ''
        css = ''
        if class_tag is not None and self.styles.get(class_tag) is not None:
            css = self.styles.get(class_tag)
        if style_tag is not None:
            css += style_tag
        return css

    @staticmethod
    def process_css_for_table_paragraph_style(css, row_count, col_count):
        paragraph_style = EnhancedParagraphStyle('paragraph_style')
        paragraph_style.process_css_for_table_paragraph_style(css, row_count, col_count)
        return paragraph_style

    def process_paragraph_element(self, tag):

        css = self.get_css_from_style_attribute(tag)
        paragraph_style = EnhancedParagraphStyle('paragraph_style')
        paragraph_style.process_raw_css(css)
        xml = etree.tostring(tag)

        enhanced_paragraph = EnhancedParagraph(xml, paragraph_style, css_classes=self.styles)
        return enhanced_paragraph

    @staticmethod
    def get_alignment_details(main_styles):
        h_align = 'LEFT'
        v_align = 'TOP'

        for style in main_styles:
            if style[0].lower() == 'halign':
                h_align = style[3]
            if style[0].lower() == 'valign':
                v_align = style[3]
        return h_align, v_align

    @staticmethod
    def process_column_widths(col_widths, table_width):
        new_col_widths = copy.copy(col_widths)
        undefined_count = 0
        defined_percentage = 0
        defined_space = 0

        for index, x in enumerate(new_col_widths, 0):
            if x is None:
                undefined_count += 1
            elif isinstance(x, ColumnWidthPercentage):
                defined_percentage += x.get_value()
            else:
                defined_space += x
                new_col_widths[index] = x * mm

        if undefined_count == 0 and defined_percentage == 0:
            return new_col_widths

        undefined_percentage = 0
        if undefined_count > 0:
            undefined_percentage = (100 - defined_percentage) / undefined_count

        available_space = table_width - defined_space
        if available_space < 0:
            available_space = 0

        percentage_amount = available_space / 100.0

        for index, x in enumerate(new_col_widths, 0):
            if x is None:
                value = undefined_percentage * percentage_amount
                new_col_widths[index] = value * mm
            elif isinstance(x, ColumnWidthPercentage):
                new_col_widths[index] = (x.get_value() * percentage_amount) * mm

        return new_col_widths

    def process_spacer_tag(self, element):

        css = self.get_css_from_style_attribute(element)
        css = css.replace('\r', '').replace('\n', '')
        height = 10
        styles_list = css.split(';')
        for style in styles_list:
            if style == '':
                continue
            style_type, style_detail = style.split(':')
            style_type = style_type.lower().lstrip("\r\n ")
            if style_type == 'height':
                height = float(style_detail)

        return Spacer(0, height * mm)

    @staticmethod
    def svg2rlg_from_node(node):
        svg_renderer = SvgRenderer(path=None)
        drawing = svg_renderer.render(node)
        return drawing

    @staticmethod
    def split_cell(xml, overflow_length):
        overflow_rows = []
        held_working_tags = []
        raw_parts = None
        offset = xml.find('>'.encode())
        m = re.search("<br\s?/>".encode(), xml[overflow_length + offset:])
        if m:
            pos = m.start() + overflow_length + offset
            span = m.span()
            match_len = span[1] - span[0]
            xml_parts = re.split("<br\s?/>".encode(), xml[pos + match_len:])
            next_xml = ''
            raw_parts = []
            # this makes the xml valid again after it has been split

            for xml_part in [xml[:pos]] + xml_parts:
                working_xml = next_xml.encode() + xml_part
                tags = re.findall(r'<[^<>]*>', working_xml.decode())
                next_xml = ''
                working_tags = []
                for tag in tags:
                    if tag[-2] == '/':
                        continue
                    m = re.search(r'\w+', tag)
                    tag_name = m.group(0)

                    if tag[1] == '/':
                        if len(working_tags) == 0:
                            break
                        elif tag_name == working_tags[-1][0]:
                            working_tags.pop()
                            if tag_name == 'td' and len(working_tags) == 0:
                                break
                    else:
                        working_tags.append((tag_name, tag))
                raw_parts.append(xml_part)

                held_working_tags.append(working_tags)
                for tag in reversed(working_tags):
                    working_xml += ('</' + tag[0] + '>').encode()
                overflow_rows.append(working_xml)
                for tag in working_tags:
                    next_xml += tag[1]

            return overflow_rows[0], overflow_rows[1:], raw_parts, held_working_tags

        return xml, overflow_rows, raw_parts, held_working_tags

    def overflow_cell(self, td_element, xml, overflow_gt_length, styles, style, offset, col_count, row_count, col_span,
                      row_span, row_data, overflow_rows, rows_variables):
        text = re.sub('<.*?>', '', str(xml))
        if len(text) > overflow_gt_length:
            overflow_length = int(td_element.get('overflow_length', 0))
            xml, overflow_rows_xml, _, _ = self.split_cell(xml, overflow_length)

            if overflow_rows_xml:
                self.process_css_for_table(tag=td_element,
                                           styles=styles,
                                           other_styles={},
                                           start_col=col_count + offset,
                                           start_row=row_count,
                                           end_col=col_count + offset + col_span - 1,
                                           end_row=row_count + row_span - 1,
                                           style_tag_name='overflow_top_style',
                                           class_tag_name='overflow_top_class')

                self.process_over_flow_xml(overflow_rows_xml=overflow_rows_xml,
                                           overflow_rows=overflow_rows,
                                           rows_variables=rows_variables,
                                           td_element=td_element,
                                           styles=styles,
                                           row_count=row_count,
                                           col_count=col_count,
                                           row_span=row_span,
                                           col_span=col_span,
                                           row_data=row_data,
                                           offset=offset)

                style = self.process_css_for_table_paragraph_style(styles, row_count, col_count + offset)
        return xml, style, len(overflow_rows)

    def get_doc_type(self):
        entity_string = ''
        for entity in self.entities:
            entity_string += u'<!ENTITY %s \'%s\'>' % (entity[0], entity[1])
        xml = """<!DOCTYPE root SYSTEM "print_engine" [%s]>""" % entity_string
        return xml

    @staticmethod
    def get_overflow_overflow_gt_height(raw_overflow_gt_height, held_cells, widths):
        if raw_overflow_gt_height.startswith('#'):
            held_cell_data = held_cells.get(raw_overflow_gt_height[1:])
            display_object = held_cell_data['display_object']
            index = held_cell_data['index']
            col_span = held_cell_data['colspan']
            avail_width = sum(widths[index:index + col_span])

            if isinstance(display_object, EnhancedParagraph):
                return display_object.calc_text_height(avail_width=avail_width)
            elif isinstance(display_object, Table):
                _, h = display_object.wrap(0, 0)
                return h
            else:
                return 5 * mm
        else:
            return float(raw_overflow_gt_height) * mm

    def process_overflow_height(self, td_element, index, overflow_gt_height, xml, style,
                                col_widths, table_width, col_span,
                                styles, offset, col_count, row_count, row_span, row_data, overflow_rows,
                                rows_variables, held_cells):
        widths = self.process_column_widths(col_widths, table_width)
        overflow_gt_height = self.get_overflow_overflow_gt_height(raw_overflow_gt_height=overflow_gt_height,
                                                                  held_cells=held_cells,
                                                                  widths=widths)

        avail_width = sum(widths[index:index+col_span])
        display_object = EnhancedParagraph(xml, style, css_classes=self.styles)
        height = display_object.calc_text_height(avail_width=avail_width)

        if height <= overflow_gt_height:
            return display_object, 0

        xml, overflow_rows_xml, raw_parts, held_working_tags = self.split_cell(xml=xml, overflow_length=0)

        working_height = 0
        working_xml = b''
        found_break = False
        overflow_row_offset = 0
        for overflow_row_offset, (row_xml, raw_part, working_tags) in\
                enumerate(zip([xml] + overflow_rows_xml, raw_parts, held_working_tags), 1):
            working_xml += raw_part + '<br/>'.encode()
            if raw_part == b'\n':
                row_xml = row_xml.replace(b'\n', b'M')
            p = EnhancedParagraph(row_xml, style, css_classes=self.styles)
            height = p.calc_text_height(avail_width=avail_width)
            working_height += height
            if working_height > overflow_gt_height:
                for tag in reversed(working_tags):
                    working_xml += ('</' + tag[0] + '>').encode()
                    found_break = True
                break
        overflow_len = len(overflow_rows_xml[overflow_row_offset-1:])
        if not found_break or overflow_len == 0:
            return display_object, 0

        display_object = EnhancedParagraph(working_xml, style, css_classes=self.styles)

        self.process_css_for_table(tag=td_element,
                                   styles=styles,
                                   other_styles={},
                                   start_col=col_count + offset,
                                   start_row=row_count,
                                   end_col=col_count + offset + col_span - 1,
                                   end_row=row_count + row_span - 1,
                                   style_tag_name='overflow_top_style',
                                   class_tag_name='overflow_top_class')

        over_flow_len = self.process_over_flow_xml(overflow_rows_xml=overflow_rows_xml[overflow_row_offset - 1:],
                                                   overflow_rows=overflow_rows,
                                                   rows_variables=rows_variables,
                                                   td_element=td_element,
                                                   styles=styles,
                                                   row_count=row_count,
                                                   col_count=col_count,
                                                   row_span=row_span,
                                                   col_span=col_span,
                                                   row_data=row_data,
                                                   offset=offset)
        return display_object, over_flow_len

    def process_over_flow_xml(self, overflow_rows_xml, overflow_rows, rows_variables,
                              td_element, styles, row_count, col_count, row_span, col_span, row_data, offset):

        for overflow_row_offset, row_xml in enumerate(overflow_rows_xml, 1):
            if row_xml == overflow_rows_xml[-1]:
                style_tag_name = 'bottom'
            else:
                style_tag_name = 'middle'

            self.process_css_for_table(tag=td_element,
                                       styles=styles,
                                       other_styles={},
                                       start_col=col_count + offset,
                                       start_row=row_count + overflow_row_offset,
                                       end_col=col_count + offset + col_span - 1,
                                       end_row=row_count + overflow_row_offset + row_span - 1)
            self.process_css_for_table(tag=td_element,
                                       styles=styles,
                                       other_styles={},
                                       start_col=col_count + offset,
                                       start_row=row_count + overflow_row_offset,
                                       end_col=col_count + offset + col_span - 1,
                                       end_row=row_count + overflow_row_offset + row_span - 1,
                                       style_tag_name='overflow_%s_style' % style_tag_name,
                                       class_tag_name='overflow_%s_class' % style_tag_name)
            style = self.process_css_for_table_paragraph_style(
                css=styles,
                row_count=row_count + overflow_row_offset,
                col_count=col_count + offset)
            overflow_object = EnhancedParagraph(row_xml, style, css_classes=self.styles)
            overflow_row = ['' for _ in range(len(row_data))]
            # noinspection PyTypeChecker
            overflow_row.append(overflow_object)
            overflow_rows.append(overflow_row)
            rows_variables.append(rows_variables[-1])

        return len(overflow_rows_xml)

    # noinspection PyMethodMayBeStatic
    def get_boolean_value(self, value):
        return value in ['1', 'True', 'yes']

    def update_status(self, message):
        if self.status_method is not None:
            self.status_method(message)
