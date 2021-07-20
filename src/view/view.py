import datetime
from typing import Dict
from typing import List
from typing import Set

from kivy import Logger
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.clock import mainthread
from kivy.input import MotionEvent
from kivy.lang import Builder
from kivy.properties import BooleanProperty
from kivy.properties import ColorProperty
from kivy.properties import ObjectProperty
from kivy.properties import StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import NoTransition
from kivy.uix.screenmanager import Screen
from kivy.uix.screenmanager import ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.stacklayout import StackLayout
from kivy.utils import get_color_from_hex
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
# noinspection PyProtectedMember
from kivymd.uix.snackbar import BaseSnackbar
from kivymd.uix.textfield import MDTextField
from kivymd.utils.fitimage import FitImage

from src import __RESOURCE__
from src import model
from src.base import loggers
from src.controller import spreadsheet_out
from src.model import db
from src.model.config import Build
from src.model.config import Model
from src.model.enums import FoodSource
from src.view.palette import *

__all__ = [
    'View',
]

log = loggers.Logger('View', Logger)


class TopBar(FitImage):
    source = StringProperty('Sam header.png')


class USDASourceButton(Label):
    parent: BoxLayout = ObjectProperty(None)

    def on_touch_down(self, touch: MotionEvent) -> bool:
        if self.collide_point(*touch.pos):
            if touch.is_double_tap:
                Clock.schedule_interval(self.parent.root.shrink, .003)

        return super().on_touch_down(touch)


class HerbalifeSourceButton(FloatLayout):
    parent: BoxLayout = ObjectProperty(None)

    def on_touch_down(self, touch: MotionEvent) -> bool:
        if self.collide_point(*touch.pos):
            if touch.is_double_tap:
                Clock.schedule_interval(self.parent.root.shrink, .003)

        return super().on_touch_down(touch)


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
                self.app.warning_snack_bar(f'`{self.text}` is not a valid QTY')
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


class FoodCard(MDCard):
    food_id = StringProperty('Food ID')
    description = StringProperty('Food Description')
    serving_size = StringProperty('Serving Size')
    source: FoodSource = ObjectProperty(None)
    first = True

    app: 'View' = ObjectProperty(None)
    qty_field: FoodQTYField = ObjectProperty(None)
    description_label: MDLabel = ObjectProperty(None)
    food_source_div: BoxLayout = ObjectProperty(None)

    height_decrement_qty: float
    char_lookup: Dict[str, int]

    def __init__(self, **kwargs) -> None:
        self.validated_qty = 1.0
        super().__init__(**kwargs)

    def on_kv_post(self, base_widget):
        if type(self).first:
            type(self).height_decrement_qty = self.height / 20
            type(self).first = False
        self.add_logo()

    @mainthread
    def add_logo(self) -> None:
        if self.source == FoodSource.USDA:
            self.food_source_div.add_widget(USDASourceButton())
        elif self.source == FoodSource.HLF:
            self.food_source_div.add_widget(HerbalifeSourceButton())

    def shrink(self, *_) -> None:
        if self.children:
            self.clear_widgets()
            self.md_bg_color = get_color_from_hex('#fafafa')

        self.height -= self.height_decrement_qty
        if self.height > self.height_decrement_qty:
            self.app.recalculate_scroll_view()

        else:
            Clock.unschedule(self.shrink)
            self.app.remove_from_stack(self)


class CustomSnackBar(BaseSnackbar):
    text = StringProperty(None)
    icon = StringProperty(None)


class LoadingScreen(Screen):
    label_text: str = StringProperty('loading...')
    is_good: bool = BooleanProperty(True)
    is_loading: bool = BooleanProperty(True)

    def set(self, label_text: str, is_good: bool, is_loading: bool) -> None:
        self.label_text = label_text
        self.is_good = is_good
        self.is_loading = is_loading


class EmptyStackScreen(Screen):
    input_field: MDTextField = ObjectProperty(None)

    def on_enter(self, *args):
        def callback(*_) -> None:
            log.info('giving input field focus now')
            self.input_field.focus = True

        super().on_enter(*args)
        Clock.schedule_once(callback, .1)


class PopulatedStackScreen(Screen):
    input_field: MDTextField = ObjectProperty(None)
    food_scroll_view: ScrollView = ObjectProperty(None)
    food_stack_layout: StackLayout = ObjectProperty(None)


class CheckMark(BoxLayout):
    pass


class RegionChip(ButtonBehavior, BoxLayout):
    parent: StackLayout
    selected = BooleanProperty(False)
    selected_color = ColorProperty([0, 0, 0, 0])
    default_color = ColorProperty([0, 0, 0, 0])
    region_name = StringProperty('region_name')
    check_box_div: MDBoxLayout = ObjectProperty(None)
    label: Label = ObjectProperty(None)
    color = ColorProperty([0, 0, 0, 0])

    def on_press(self) -> None:
        self.selected = not self.selected
        _regions = self.parent.root.selected_regions
        if self.selected:
            _regions.add(self.region_name)
            _to_color = self.selected_color
            self.check_box_div.add_widget(CheckMark())
            self.parent.root.selection_made = True
        else:
            self.check_box_div.clear_widgets()
            _to_color = self.default_color
            _regions.remove(self.region_name)
            if not self.parent.root.selected_regions:
                self.parent.root.selection_made = False

        Animation(
            color=_to_color,
            d=0.3,
        ).start(self)


# noinspection PyAbstractClass
class SubmitInstruction(ButtonBehavior, MDLabel):
    root: 'AnalysisScreen' = ObjectProperty(None)

    def on_press(self) -> bool:
        if self.root.selection_made:
            self.root.begin_analysis()
            return True

        return super().on_press()


class AnalysisScreen(Screen):
    app: 'View' = ObjectProperty(None)
    chip_stack: StackLayout = ObjectProperty(None)
    chip_interval = .05
    regions_to_be_added: List[str]
    selected_regions: Set[str]
    selection_made = BooleanProperty(False)
    submit_instruction: SubmitInstruction = ObjectProperty(None)

    def begin_analysis(self) -> None:
        log.info(f'Beginning analysis')
        self.app.begin_analysis(self.selected_regions)

    def on_enter(self, *args):
        self.regions_to_be_added = list(self.app.regions_d.keys())
        self.selected_regions = set()
        Clock.schedule_interval(self.add_chip, self.chip_interval)

    def add_chip(self, *_) -> None:
        self.chip_stack.add_widget(RegionChip(region_name=self.regions_to_be_added.pop()))
        if not self.regions_to_be_added:
            Clock.unschedule(self.add_chip)


class RootWidget(BoxLayout):
    bottom_bar: BoxLayout = ObjectProperty(None)


class View(MDApp):
    model: Model

    root: RootWidget
    screen_manager: ScreenManager

    loading_screen: LoadingScreen
    empty_stack_screen: EmptyStackScreen
    populated_stack_screen: PopulatedStackScreen

    food_stack_layout: StackLayout
    food_scroll_view: ScrollView

    analysis_screen: AnalysisScreen

    def __init__(self, **kwargs) -> None:
        kwargs['title'] = 'Sam'
        self.stack: Dict[str, db.Food] = dict()
        self.food_cards: Dict[str, FoodCard] = dict()
        self.model = Model(**__RESOURCE__.cfg('app.yml', parse=True))
        self.build_obj = Build(**__RESOURCE__.cfg('build.yml', parse=True))
        self.session_manager = model.Database(
            db.Schema, f'sqlite:///{__RESOURCE__.db(self.model.CONNECTION_STRING_SUFFIX)}'
        ).connect(log.spawn('Database'))
        with self.session_manager() as session:
            self.regions_d: Dict[str, db.Region] = db.Region.all(session)
        super().__init__(**kwargs)

    def build(self):
        self.theme_cls.colors = THEME
        self.theme_cls.primary_palette = PRIMARY_PALETTE
        self.theme_cls.accent_palette = 'Orange'

        self.root = Builder.load_file(__RESOURCE__.cfg('view.kv'))

        self.screen_manager = ScreenManager(transition=NoTransition())
        self.loading_screen = LoadingScreen(name='loading')
        self.empty_stack_screen = EmptyStackScreen(name='empty_stack')
        self.populated_stack_screen = PopulatedStackScreen(name='populated_stack')

        self.food_stack_layout = self.populated_stack_screen.food_stack_layout
        self.food_scroll_view = self.populated_stack_screen.food_scroll_view

        self.analysis_screen = AnalysisScreen(name='analysis')

        self.screen_manager.add_widget(self.loading_screen)
        self.screen_manager.add_widget(self.empty_stack_screen)
        self.screen_manager.add_widget(self.populated_stack_screen)
        self.screen_manager.add_widget(self.analysis_screen)
        self.root.bottom_bar.add_widget(self.screen_manager)

        self.screen_manager.current = 'populated_stack'
        self.screen_manager.current = 'empty_stack'

        return self.root

    @staticmethod
    @mainthread
    def warning_snack_bar(text: str, icon: str = "information-outline") -> None:
        CustomSnackBar(text=text, icon=icon).open()

    @mainthread
    def clear_field(self, do_clear_text: bool = True) -> None:
        if do_clear_text:
            self.screen_manager.current_screen.input_field.text = ''
        self.screen_manager.current_screen.input_field.focus = True

    def add_food(self, value: str = None, multiple_values: Set[str] = None) -> None:
        is_tail_recursion = multiple_values is not None
        if is_tail_recursion and value is not None:
            raise TypeError

        food_id = (value if value is not None else multiple_values.pop()).upper().strip()  # type: ignore

        if not food_id:
            return

        if food_id in self.stack:
            scroll_to_widget = self.food_cards[food_id]
            if not is_tail_recursion:
                self.warning_snack_bar(f'Food ID {food_id} is already in the stack')

        else:
            try:
                with self.session_manager() as session:
                    food = db.Food.get(session, food_id)
                if food is None:
                    raise ValueError

            except (TypeError, ValueError):
                self.clear_field(do_clear_text=False)
                return self.warning_snack_bar(f'Food ID `{food_id}` was not found')

            food_card = FoodCard()
            food_card.food_id = food_id
            food_card.description = food.description
            food_card.serving_size = food.qty_per_serving
            food_card.source = food.source
            self.stack[food_id] = food
            self.food_cards[food_id] = food_card
            self.food_stack_layout.add_widget(food_card)
            scroll_to_widget = food_card

        @mainthread
        def scroll_to_widget_callback(widget):
            if self.food_stack_layout.height > self.food_scroll_view.height:
                self.food_scroll_view.scroll_to(widget)

        if scroll_to_widget:
            self.screen_manager.current = 'populated_stack'
            scroll_to_widget_callback(scroll_to_widget)

        if is_tail_recursion and multiple_values:
            def callback(*_) -> None:
                self.add_food(multiple_values=multiple_values)

            Clock.schedule_once(callback, .1)

        else:
            self.clear_field()

    @mainthread
    def recalculate_scroll_view(self) -> None:
        if self.food_stack_layout.height < self.food_scroll_view.height:
            self.food_scroll_view.scroll_y = 1.

    def proceed_to_region_selection_screen(self) -> None:
        log.info('proceed_to_region_selection_screen')
        self.screen_manager.current = 'analysis'

    def clear_food_cards(self) -> None:
        log.info('clear_food_cards button pressed')
        self.remove_from_stack(*self.food_cards.values())

    @mainthread
    def remove_from_stack(self, *food_cards: FoodCard) -> None:
        for food_card in food_cards:
            food_id = food_card.food_id
            del self.stack[food_id]
            del self.food_cards[food_id]

            self.food_stack_layout.remove_widget(food_card)
            log.info(f'Removed food `{food_card.food_id}` from stack')

        if not self.stack:
            self.screen_manager.current = 'empty_stack'

        self.clear_field()
        self.recalculate_scroll_view()

    def begin_analysis(self, regions: Set[str]) -> None:
        with self.session_manager() as session:
            spreadsheet_out.make(
                db.Stack.from_gui(
                    session, [self.regions_d[r] for r in regions], list(self.stack.values()),
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
