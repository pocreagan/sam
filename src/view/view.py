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
from kivy.input import MotionEvent
from kivy.lang import Builder
from kivy.properties import BooleanProperty
from kivy.properties import ColorProperty
from kivy.properties import ObjectProperty
from kivy.properties import StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.recycleview import RecycleView
from kivy.uix.scrollview import ScrollView
from kivy.uix.stacklayout import StackLayout
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
# noinspection PyProtectedMember
from kivymd.uix.dialog import MDDialog
from kivymd.uix.list import ILeftBodyTouch
from kivymd.uix.list import MDList
from kivymd.uix.list import TwoLineAvatarListItem
from kivymd.uix.snackbar import BaseSnackbar
from kivymd.uix.textfield import MDTextField
from KivyOnTop import register_topmost

from src import __RESOURCE__
from src import model
from src.base import loggers
from src.controller import spreadsheet_out
from src.model import db
from src.model import SessionManager
from src.model import stacks
from src.model.config import Build
from src.model.config import Model
from src.view.palette import *

__all__ = [
    'View',
]

log = loggers.Logger('View', Logger)


class RemoveFoodButton(Image):
    parent: FloatLayout = ObjectProperty(None)

    def on_touch_down(self, touch: MotionEvent) -> bool:
        if self.collide_point(*touch.pos):
            self.parent.parent.root.kill()

        return super().on_touch_down(touch)


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
            self.text = str(self.root.validated_qty)

        else:
            try:
                qty = float(self.text)
                if qty <= 0.:
                    raise ValueError

            except ValueError:
                self.app.start_snack_bar(f'`{self.text}` is not a valid QTY')
                self.text = str(self.root.validated_qty)

            else:
                self.root.validated_qty = qty
                self.text = str(qty)

        super().on_text_validate()

    def on_focus(self, _arg, is_focused: bool) -> None:
        if self.was_focused ^ is_focused:
            if self.was_focused:
                self.text = str(self.root.validated_qty)

            if is_focused:
                mainthread(self.select_all)()

            else:
                mainthread(self.cancel_selection)()

            self.was_focused = is_focused

        super().on_focus(_arg, is_focused)


class FoodCard(FloatLayout):
    food: db.Food = ObjectProperty(None)
    app: 'View' = ObjectProperty(None)
    qty_field: FoodQTYField = ObjectProperty(None)

    def __init__(self, **kwargs) -> None:
        self.validated_qty = float(kwargs.pop('validated_qty')) if 'validated_qty' in kwargs else 1.0
        super().__init__(**kwargs)

    @mainthread
    def kill(self, *_) -> None:
        self.clear_widgets()
        self.app.remove_from_stack(self)


class CustomSnackBar(BaseSnackbar):
    text = StringProperty(None)
    icon = StringProperty(None)


class CheckMark(BoxLayout):
    pass


class RegionChip(ButtonBehavior, BoxLayout):
    parent: 'RegionsChips'
    selected = BooleanProperty(False)
    selected_color = ColorProperty([0, 0, 0, 0])
    default_color = ColorProperty([0, 0, 0, 0])
    region_name = StringProperty('region_name')
    check_box_div: MDBoxLayout = ObjectProperty(None)
    label: Label = ObjectProperty(None)
    color = ColorProperty([0, 0, 0, 0])

    animation: Animation
    check_mark: CheckMark

    def on_kv_post(self, base_widget):
        self.check_mark = CheckMark()
        self.animation = Animation(color=self.selected_color, d=0.3)

        @mainthread
        def callback(*_) -> None:
            self.parent.app.root.search_bar.clear_field(False)

        self.animation.bind(on_complete=callback)

    def on_press(self) -> None:
        self.selected = not self.selected
        _regions = self.parent.app.selected_regions

        if self.selected:
            # noinspection PyProtectedMember
            self.animation._animated_properties['color'] = self.selected_color
            _regions.add(self.region_name)
            self.parent.app.region_selected = True
            self.check_box_div.add_widget(self.check_mark)

        else:
            # noinspection PyProtectedMember
            self.animation._animated_properties['color'] = self.default_color
            self.check_box_div.remove_widget(self.check_mark)
            _regions.remove(self.region_name)
            if not self.parent.app.selected_regions:
                self.parent.app.region_selected = False

        self.animation.start(self)


class RegionsChips(StackLayout):
    app: 'View' = ObjectProperty(None)

    def add_regions(self, regions: List[str]):
        [self.add_widget(RegionChip(region_name=region)) for region in regions]


class ClickButton(ButtonBehavior, Image):
    pass


class SearchResult(BoxLayout):
    food: db.Food = ObjectProperty(None)


class SearchBar(MDTextField):
    @mainthread
    def clear_field(self, do_clear_text: bool = True) -> None:
        if do_clear_text:
            self.text = ''
        self.focus = True


class RootWidget(BoxLayout):
    regions_chips: RegionsChips = ObjectProperty(None)
    search_bar: SearchBar = ObjectProperty(None)
    search_results: RecycleView = ObjectProperty(None)
    stack_scroll_view: ScrollView = ObjectProperty(None)
    stack_box_layout: BoxLayout = ObjectProperty(None)


class SaveStackContent(BoxLayout):
    pass


class RemoveSavedStack(ILeftBodyTouch, ButtonBehavior, Image):
    pass


class LoadStackContent(BoxLayout):
    container: MDList = ObjectProperty(None)


class StackLoadOption(TwoLineAvatarListItem):
    pass


class View(MDApp):
    model: Model
    root: RootWidget

    save_as_dialog: MDDialog = None
    load_from_dialog: MDDialog = None
    load_from_content: LoadStackContent

    TITLE = 'Sam'
    session_manager: SessionManager
    stack_session_manager: SessionManager
    regions_d: Dict[str, db.Region]
    model: Model
    build_obj: Build

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
        self.stack: Dict[str, db.Food] = dict()
        self.food_cards: Dict[str, FoodCard] = dict()
        self.selected_regions: Set[str] = set()
        self.dat_dir = Path(os.path.expanduser("~/Desktop/Sam/Preferences"))
        self.load_from_options: Dict[str, StackLoadOption] = {}
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
                self.root.regions_chips.add_regions(list(sorted(self.regions_d.keys(), reverse=True)))

            self.stack_session_manager = model.Database(
                stacks.Schema, f'sqlite:///{self.dat_dir / "saved-stacks.db"}'
            ).connect(log.spawn('StacksDB'))

            with self.stack_session_manager() as stack_session:
                # noinspection PyProtectedMember
                results = stack_session.query(stacks.Stack).order_by(stacks.Stack.name).all()

            self.saved_stacks = {r.name: r for r in results}
            self.load_from_options = {name: StackLoadOption(
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
            scroll_to_widget = self.food_cards[food.food_id]
            if not is_tail_recursion:
                self.start_snack_bar(f'Food ID {food.food_id} is already in the stack')

        else:
            food_card = FoodCard(food=food, validated_qty=getattr(food, 'validated_qty', 1.0))
            self.stack[food.food_id] = food
            self.food_cards[food.food_id] = food_card
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

        else:
            self.root.search_bar.clear_field()

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
            del self.food_cards[food_id]

            self.root.stack_box_layout.remove_widget(food_card)
            log.info(f'Removed food `{food_id}` from stack')

        self.root.search_bar.clear_field(False)
        self.recalculate_scroll_view()
        self.stack_present = bool(self.stack)

    def clear_food_cards(self) -> None:
        log.info('clear_food_cards button pressed')
        self.remove_from_stack(*self.food_cards.values())

        def callback(*_) -> None:
            self.root.search_bar.clear_field()

        Clock.schedule_once(callback, .1)

    def select_stack_dialog(self) -> None:
        log.info('load_stack button pressed')

        if not self.saved_stacks:
            return self.start_snack_bar('No stacks have been saved so far.')

        if not self.load_from_dialog:
            self.load_from_content = LoadStackContent()
            self.load_from_dialog = MDDialog(
                title="Load Stack",
                type="custom",
                content_cls=self.load_from_content,
                items=[], buttons=[],
                on_dismiss=self.root.search_bar.clear_field,
            )

        self.load_from_content.container.clear_widgets()
        for _, option in self.load_from_options.items():
            self.load_from_content.container.add_widget(option)

        self.load_from_dialog.open()

    def update_stack_dialog(self) -> None:
        if not self.save_as_dialog:
            content = SaveStackContent()

            @mainthread
            def callback(*_) -> None:
                content.input_field.focus = True

            self.save_as_dialog = MDDialog(
                title="Save Stack As",
                type="custom",
                content_cls=content,
                buttons=[],
                on_open=callback,
                on_dismiss=self.root.search_bar.clear_field,
            )

        self.save_as_dialog.content_cls.input_field.text = ''
        self.save_as_dialog.open()

    def select_stack(self, stack_name: str) -> None:
        self.load_from_dialog.dismiss()
        items = self.saved_stacks[stack_name].foods

        with self.session_manager() as session:
            # noinspection PyUnresolvedReferences
            foods: List[db.Food] = session.query(db.Food) \
                .filter(db.Food.food_id.in_(items.keys())) \
                .all()

        for food in foods:
            food.validated_qty = items[food.food_id]

        _foods = {food.food_id: food for food in foods}
        foods = [_foods[k] for k in items.keys()]
        foods.reverse()
        self.add_food(multiple_values=foods)

        log.info(f'selected stack `{stack_name}`')

    def delete_stack(self, stack_name: str) -> None:
        with self.stack_session_manager() as session:
            session.query(stacks.Stack).filter_by(id=self.saved_stacks.pop(stack_name).id).delete()

        self.load_from_content.container.remove_widget(self.load_from_options.pop(stack_name))
        if not self.load_from_options:
            self.load_from_dialog.dismiss()

        log.info(f'deleted stack `{stack_name}`')

    def update_stack(self, stack_name: str) -> None:
        self.save_as_dialog.dismiss()
        if stack_name in self.saved_stacks:
            self.delete_stack(stack_name)

        with self.stack_session_manager() as session:
            self.saved_stacks[stack_name] = session.make(stacks.Stack(name=stack_name, foods={
                card.food.food_id: float(card.validated_qty) for card in self.food_cards.values()
            }))

            self.load_from_options[stack_name] = StackLoadOption(
                text=stack_name, secondary_text=self.saved_stacks[stack_name].created_at.strftime('%m/%d/%Y')
            )

        log.info(f'updated stack `{stack_name}`')

    def begin_analysis(self) -> None:
        with self.session_manager() as session:
            spreadsheet_out.make(
                db.Stack.from_gui(
                    session, [self.regions_d[r] for r in self.selected_regions], list(self.stack.values()),
                    {k: v.validated_qty for k, v in self.food_cards.items()},
                ).for_spreadsheet(self.build_obj.app_version),
                f'Sam-{datetime.datetime.now().strftime("%Y%m%d-%H%M%S")}'
            )
        self.close_app()

    @mainthread
    def close_app(self) -> None:
        self.get_running_app().stop()


if __name__ == '__main__':
    View().run()
