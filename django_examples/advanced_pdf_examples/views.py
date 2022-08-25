from ajax_helpers.mixins import AjaxHelpers
from django.views.generic import TemplateView
from django_menus.menu import MenuMixin, MenuItem


class MainMenu(AjaxHelpers, MenuMixin):
    def setup_menu(self):
        # noinspection PyUnresolvedReferences
        self.add_menu('main_menu').add_items(
            ('advanced_pdf_examples:index', 'Home'),
            MenuItem(url='admin:index',
                     menu_display='Admin',
                     visible=self.request.user.is_superuser),

        )


class ExampleIndex(MainMenu, TemplateView):
    template_name = 'advanced_pdf_examples/index.html'
