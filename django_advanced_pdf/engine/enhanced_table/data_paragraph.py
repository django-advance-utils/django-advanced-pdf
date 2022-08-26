from reportlab.platypus import Paragraph


class DataParagraph(Paragraph, object):
    """
    Helper class for use in EnhancedTable footer/header row data to allow styles to be applied after variable
    substitution.
    When encountered in a footer or header, the row's data variables are merged into the text and the whole thing then
    converted into a Paragraph, using the styles supplied.
    An optional step after data merging is to run postprocess_fn on the resulting text. This allows for e.g. limited
    reformatting or stripping of characters
    """

    def __init__(self, text, style, postprocess_fn=None):
        """
        @type text: str
        @param text: The text (optionally a fornmat string) for the cell paragraph
        @param style: the cell style to apply to the enclosing paragraph
        @type postprocess_fn: callable
        @param postprocess_fn: An optional function to call after variable values have been substituted into the text
        """
        self.text = text
        self.style = style
        self.postprocess_fn = postprocess_fn

    def merge_variables(self, variables=None):
        if variables:
            new_text = self.text % variables
        else:
            new_text = self.text
        if callable(self.postprocess_fn):
            return self.postprocess_fn(new_text, self.style)
        else:
            return Paragraph(new_text, self.style)
