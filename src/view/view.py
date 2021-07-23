import datetime
import os
import time
from pathlib import Path
from typing import Dict
from typing import List
from typing import Set

from kivy import Logger
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.clock import mainthread
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.properties import BooleanProperty
from kivy.properties import ColorProperty
from kivy.properties import ObjectProperty
from kivy.properties import StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.recycleview import RecycleView
from kivy.uix.scrollview import ScrollView
from kivy.uix.stacklayout import StackLayout
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.dialog import MDDialog
from kivymd.uix.list import MDList
from kivymd.uix.list import TwoLineAvatarListItem
# noinspection PyProtectedMember
from kivymd.uix.snackbar import BaseSnackbar
from kivymd.uix.textfield import MDTextField
from KivyOnTop import register_topmost

from src import __RESOURCE__
from src import model
from src import output
from src.base import loggers
from src.model import db
from src.model import SessionManager
from src.model import stacks
from src.model.config import Build
from src.model.config import Model
from src.output import Output
from src.view.palette import *

__all__ = [
    'View',
]

log = loggers.Logger('View', Logger)


class SourceLogo(FloatLayout):
    pass


class SourceLogoRemovable(SourceLogo):
    pass


class FoodQTYField(MDTextField):
    app: 'View' = ObjectProperty(None)
    root: 'FoodCard' = ObjectProperty(None)

    def __init__(self, **kwargs) -> None:
        self.was_focused = False
        super().__init__(**kwargs)

    def on_kv_post(self, base_widget):
        self.halign = 'center'
        self._msg_lbl.font_size = '14sp'

    def on_text_validate(self) -> None:
        if not self.text:
            self.text = str(self.root.food.num_servings)

        else:
            try:
                qty = float(self.text)
                if qty <= 0.:
                    raise ValueError

            except ValueError:
                self.app.start_snack_bar(f'`{self.text}` is not a valid QTY')
                self.text = str(self.root.food.num_servings)

            else:
                self.root.food.num_servings = qty
                self.text = str(qty)

        super().on_text_validate()

    def on_focus(self, _arg, is_focused: bool) -> None:
        if self.was_focused ^ is_focused:
            if self.was_focused:
                self.text = str(self.root.food.num_servings)

            if is_focused:
                mainthread(self.select_all)()

            else:
                mainthread(self.cancel_selection)()

            self.was_focused = is_focused

        super().on_focus(_arg, is_focused)


class FoodCard(FloatLayout):
    food: db.Food = ObjectProperty(None)
    app: 'View' = ObjectProperty(None)


class CustomSnackBar(BaseSnackbar):
    text = StringProperty(None)
    icon = StringProperty(None)

    def dismiss_now(self, *_args):
        if self.snackbar_animation_dir == "Top":
            anim = Animation(y=(Window.height + self.height), d=0.2)
        elif self.snackbar_animation_dir == "Left":
            anim = Animation(x=-self.width, d=0.2)
        elif self.snackbar_animation_dir == "Right":
            anim = Animation(x=Window.width, d=0.2)
        else:
            anim = Animation(y=-self.height, d=0.2)

        anim.bind(on_complete=lambda *args: Window.parent.remove_widget(self))
        anim.start(self)
        self.dispatch("on_dismiss")


class CheckMark(BoxLayout):
    pass


class RegionChip(ButtonBehavior, BoxLayout):
    app: 'View'
    selected = BooleanProperty(False)
    selected_color = ColorProperty([0, 0, 0, 0])
    default_color = ColorProperty([0, 0, 0, 0])
    region_name = StringProperty('region_name')
    check_box_div: MDBoxLayout = ObjectProperty(None)
    color = ColorProperty([0, 0, 0, 0])

    animation: Animation
    check_mark: CheckMark

    def on_kv_post(self, base_widget):
        self.check_mark = CheckMark()
        self.animation = Animation(color=self.selected_color, d=0.3)

        @mainthread
        def callback(*_) -> None:
            self.app.root.search_bar.clear_field(False)

        self.animation.bind(on_complete=callback)

    def on_press(self) -> None:
        self.selected = not self.selected
        _regions = self.app.selected_regions

        if self.selected:
            _to_color = self.selected_color
            _regions.add(self.region_name)
            self.app.region_selected = True
            self.check_box_div.add_widget(self.check_mark)

        else:
            _to_color = self.default_color
            self.check_box_div.remove_widget(self.check_mark)
            _regions.remove(self.region_name)
            if not self.app.selected_regions:
                self.app.region_selected = False

        # noinspection PyProtectedMember
        self.animation._animated_properties['color'] = _to_color
        self.animation.start(self)


class UpdateStackContent(BoxLayout):
    pass


class SelectStackOption(TwoLineAvatarListItem):
    pass


class SelectStackContent(BoxLayout):
    container: MDList = ObjectProperty(None)


class SelectStackDialog(MDDialog):
    pass


class UpdateStackDialog(MDDialog):
    pass


class SearchBar(MDTextField):
    @mainthread
    def clear_field(self, do_clear_text: bool = True) -> None:
        if do_clear_text:
            self.text = ''
        self.focus = True


class RootWidget(BoxLayout):
    regions_chips: StackLayout = ObjectProperty(None)
    search_bar: SearchBar = ObjectProperty(None)
    search_results: RecycleView = ObjectProperty(None)
    stack_scroll_view: ScrollView = ObjectProperty(None)
    stack_box_layout: BoxLayout = ObjectProperty(None)

    @mainthread
    def focus_search(self, do_clear_text: bool = True) -> None:
        if do_clear_text:
            self._search_bar.text = ''
        self._search_bar.focus = True


class View(MDApp):
    TITLE = 'Sam'
    model: Model
    root: RootWidget
    build_obj: Build
    session_manager: SessionManager
    stack_session_manager: SessionManager
    regions_d: Dict[str, db.Region]
    update_stack_dialog: UpdateStackDialog = None
    select_stack_dialog: SelectStackDialog = None
    select_stack_content: SelectStackContent

    region_selected = BooleanProperty(False)
    stack_present = BooleanProperty(False)

    def search_term_change(self, term: str) -> None:
        stripped, results = term.strip(), []
        for term in term.split():
            if len(term) > 3:
                with self.session_manager() as session:
                    results = [dict(food=f) for f in db.Food.search(session, stripped)]
                    break

        self.root.search_results.data = results

    def search_term_enter(self) -> None:
        if not self.root.search_results.data:
            self.root.search_bar.clear_field(False)

        if len(self.root.search_results.data) == 1:
            self.add_food(self.root.search_results.data[0]['food'])

    def __init__(self, **kwargs) -> None:
        kwargs['title'] = type(self).TITLE

        self.stack: Dict[str, FoodCard] = dict()
        self.selected_regions: Set[str] = set()
        self.dat_dir = Path(os.path.expanduser('~/Desktop/Sam'))
        self.load_from_options: Dict[str, SelectStackOption] = {}
        self.saved_stacks: Dict[str, stacks.Stack] = {}

        super().__init__(**kwargs)

    def on_start(self, *args) -> None:
        log.info(f'on_start called {time.perf_counter()}')
        register_topmost(Window, type(self).TITLE)

        with log.timer('Config read on startup'):
            self.model = Model(**__RESOURCE__.cfg('app.yml', parse=True))
            self.build_obj = Build(**__RESOURCE__.cfg('build.yml', parse=True))

            self.session_manager = model.Database(
                db.Schema, f'sqlite:///{__RESOURCE__.db(self.model.CONNECTION_STRING_SUFFIX)}'
            ).connect(log.spawn('Database'))

            with self.session_manager() as session:
                self.regions_d: Dict[str, db.Region] = db.Region.all(session)
                [self.root.regions_chips.add_widget(
                    RegionChip(region_name=region)
                ) for region in sorted(self.regions_d.keys(), reverse=True)]

            os.makedirs(self.dat_dir, exist_ok=True)
            self.stack_session_manager = model.Database(
                stacks.Schema, f'sqlite:///{self.dat_dir / "Preferences" / "saved-stacks.db"}'
            ).connect(log.spawn('StacksDB'))

            with self.stack_session_manager() as stack_session:
                results = stack_session.query(stacks.Stack) \
                    .order_by(stacks.Stack.name) \
                    .all()

            self.saved_stacks = {r.name: r for r in results}
            self.load_from_options = {name: SelectStackOption(
                text=name, secondary_text=stack.created_at.strftime('%m/%d/%Y')
            ) for name, stack in self.saved_stacks.items()}

        try:
            # noinspection PyUnresolvedReferences
            import pyi_splash

        except ImportError:
            pass

        else:
            pyi_splash.close()

        self.root.search_bar.clear_field()

    def build(self):
        self.theme_cls.colors = THEME
        self.theme_cls.primary_palette = PRIMARY_PALETTE
        self.theme_cls.accent_palette = 'Orange'
        return Builder.load_file(__RESOURCE__.cfg('view.kv'))

    @staticmethod
    @mainthread
    def start_snack_bar(text: str, icon: str = "information-outline") -> None:
        CustomSnackBar(text=text, icon=icon).open()

    def add_food(self, value: db.Food = None, multiple_values: List[db.Food] = None) -> None:
        is_tail_recursion = multiple_values is not None
        if is_tail_recursion and value is not None:
            raise TypeError

        food = value if value is not None else multiple_values.pop()

        if food.food_id in self.stack:
            scroll_to_widget = self.stack[food.food_id]
            if not is_tail_recursion:
                self.start_snack_bar(f'Food ID {food.food_id} is already in the stack')

        else:
            food_card = FoodCard(food=food)
            self.stack[food.food_id] = food_card
            self.root.stack_box_layout.add_widget(food_card)
            scroll_to_widget = food_card

        if scroll_to_widget:
            @mainthread
            def scroll_to_widget_callback(widget):
                if self.root.stack_box_layout.height > self.root.stack_scroll_view.height:
                    self.root.stack_scroll_view.scroll_to(widget)

            scroll_to_widget_callback(scroll_to_widget)

        if is_tail_recursion and multiple_values:
            def callback(*_) -> None:
                self.add_food(multiple_values=multiple_values)

            Clock.schedule_once(callback, .1)

        self.root.search_bar.clear_field()
        self.stack_present = bool(self.stack)

    @mainthread
    def recalculate_scroll_view(self) -> None:
        if self.root.stack_box_layout.height < self.root.stack_scroll_view.height:
            self.root.stack_scroll_view.scroll_y = 1.

    @mainthread
    def remove_from_stack(self, *food_cards: FoodCard) -> None:
        for food_card in food_cards:
            food_id = food_card.food.food_id
            del self.stack[food_id]

            self.root.stack_box_layout.remove_widget(food_card)
            log.info(f'Removed food `{food_id}` from stack')

        self.root.search_bar.clear_field(False)
        self.recalculate_scroll_view()
        self.stack_present = bool(self.stack)

    def clear_food_cards(self) -> None:
        log.info('clear_food_cards button pressed')
        self.remove_from_stack(*self.stack.values())

        def callback(*_) -> None:
            self.root.search_bar.clear_field()

        Clock.schedule_once(callback, .1)

    def open_select_stack_dialog(self) -> None:
        log.info('load_stack button pressed')

        if not self.saved_stacks:
            return self.start_snack_bar('No stacks have been saved so far.')

        if not self.select_stack_dialog:
            self.select_stack_content = SelectStackContent()
            self.select_stack_dialog = SelectStackDialog(
                content_cls=self.select_stack_content,
                on_dismiss=self.root.search_bar.clear_field,
            )

        self.select_stack_content.container.clear_widgets()
        for _, option in self.load_from_options.items():
            self.select_stack_content.container.add_widget(option)

        self.select_stack_dialog.open()

    def open_update_stack_dialog(self) -> None:
        if not self.update_stack_dialog:
            content = UpdateStackContent()

            @mainthread
            def callback(*_) -> None:
                content.input_field.focus = True

            self.update_stack_dialog = UpdateStackDialog(
                content_cls=content, on_open=callback,
                on_dismiss=self.root.search_bar.clear_field,
            )

        self.update_stack_dialog.content_cls.input_field.text = ''
        self.update_stack_dialog.open()

    def select_stack(self, stack_name: str) -> None:
        self.select_stack_dialog.dismiss()
        items = self.saved_stacks[stack_name].foods

        with self.session_manager() as session:
            # noinspection PyUnresolvedReferences
            foods: List[db.Food] = session.query(db.Food) \
                .filter(db.Food.food_id.in_(items.keys())) \
                .all()

        for food in foods:
            food.num_servings = items[food.food_id]

        _foods = {food.food_id: food for food in foods}
        foods = [_foods[k] for k in items.keys()]
        foods.reverse()
        self.add_food(multiple_values=foods)

        log.info(f'selected stack `{stack_name}`')

    def delete_stack(self, stack_name: str) -> None:
        with self.stack_session_manager() as session:
            session.query(stacks.Stack) \
                .filter_by(id=self.saved_stacks.pop(stack_name).id) \
                .delete()

        self.select_stack_content.container.remove_widget(self.load_from_options.pop(stack_name))
        if not self.load_from_options:
            self.select_stack_dialog.dismiss()

        log.info(f'deleted stack `{stack_name}`')

    def update_stack(self, stack_name: str) -> None:
        self.update_stack_dialog.dismiss()
        if stack_name in self.saved_stacks:
            self.delete_stack(stack_name)

        with self.stack_session_manager() as session:
            self.saved_stacks[stack_name] = session.make(stacks.Stack(name=stack_name, foods={
                card.food.food_id: float(card.food.num_servings) for card in self.stack.values()
            }))

            self.load_from_options[stack_name] = SelectStackOption(
                text=stack_name, secondary_text=self.saved_stacks[stack_name].created_at.strftime('%m/%d/%Y')
            )

        log.info(f'updated stack `{stack_name}`')
        self.start_snack_bar(f'stack saved as `{stack_name}`')

    def begin_analysis(self) -> None:
        with self.session_manager() as session:
            bound_foods = db.get_from_ids(session, [card.food for card in self.stack.values()])
            bound_regions = db.get_from_ids(session, list([self.regions_d[r] for r in self.selected_regions]))
            nutrients = db.Nutrient.as_list(session)

        for bound_food in bound_foods:
            bound_food.num_servings = self.stack[bound_food.food_id].food.num_servings

        output.write_spreadsheet(
            Output(nutrients, bound_regions, bound_foods),
            self.dat_dir / 'Results',
            f'Sam-{datetime.datetime.now().strftime("%Y%m%d-%H%M%S")}',
            self.build_obj.app_version,
        )

        self.close_app()

    @mainthread
    def close_app(self) -> None:
        self.get_running_app().stop()


if __name__ == '__main__':
    View().run()
