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
            self.app.root.focus_search(False)

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


class RootWidget(BoxLayout):
    regions_chips: StackLayout = ObjectProperty(None)
    _search_bar: MDTextField = ObjectProperty(None)
    search_results: RecycleView = ObjectProperty(None)
    stack_view: RecycleView = ObjectProperty(None)

    @mainthread
    def focus_search(self, do_clear_text: bool = True) -> None:
        if do_clear_text:
            self._search_bar.text = ''
        self._search_bar.focus = True


class View(MDApp):
    TITLE = 'Sam'
    root: RootWidget

    update_stack_dialog: UpdateStackDialog = None
    select_stack_dialog: SelectStackDialog = None

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
            self.root.focus_search(False)

        if len(self.root.search_results.data) == 1:
            self.add_food(self.root.search_results.data[0]['food'])

    def __init__(self, **kwargs) -> None:
        kwargs['title'] = type(self).TITLE

        self.stack: Dict[str, db.Food] = dict()
        self.selected_regions: Set[str] = set()
        self.dat_dir = Path(os.path.expanduser('~/Desktop/Sam'))
        self.load_from_options: Dict[str, SelectStackOption] = {}

        with log.timer('Config read'):
            self.model = Model(**__RESOURCE__.cfg('app.yml', parse=True))
            self.build_obj = Build(**__RESOURCE__.cfg('build.yml', parse=True))

            self.session_manager = model.Database(
                db.Schema, f'sqlite:///{__RESOURCE__.db(self.model.CONNECTION_STRING_SUFFIX)}'
            ).connect(log.spawn('Database'))

            with self.session_manager() as session:
                self.regions_d: Dict[str, db.Region] = db.Region.all(session)

            os.makedirs(self.dat_dir, exist_ok=True)
            self.stack_session_manager = model.Database(
                stacks.Schema, f'sqlite:///{self.dat_dir / "Preferences" / "saved-stacks.db"}'
            ).connect(log.spawn('StacksDB'))

            with self.stack_session_manager() as stack_session:
                results = stack_session.query(stacks.Stack) \
                    .order_by(stacks.Stack.name) \
                    .all()

            self.saved_stacks: Dict[str, stacks.Stack] = {r.name: r for r in results}

        super().__init__(**kwargs)

    @staticmethod
    def close_splash_screen() -> None:
        try:
            # noinspection PyUnresolvedReferences
            import pyi_splash
        except ImportError:
            pass
        else:
            pyi_splash.close()

    def on_start(self, *args) -> None:
        log.info(f'on_start called {time.perf_counter()}')
        register_topmost(Window, type(self).TITLE)
        self.close_splash_screen()
        self.root.focus_search()

    def build(self):
        self.theme_cls.colors = THEME
        self.theme_cls.primary_palette = PRIMARY_PALETTE
        self.theme_cls.accent_palette = 'Orange'

        self.root = Builder.load_file(__RESOURCE__.cfg('view.kv'))

        [self.root.regions_chips.add_widget(
            RegionChip(region_name=region)
        ) for region in sorted(self.regions_d.keys(), reverse=True)]

        self.load_from_options = {name: SelectStackOption(
            text=name, secondary_text=stack.created_at.strftime('%m/%d/%Y')
        ) for name, stack in self.saved_stacks.items()}

        return self.root

    @staticmethod
    @mainthread
    def start_snack_bar(text: str, icon: str = "information-outline") -> None:
        CustomSnackBar(text=text, icon=icon).open()

    def after_stack_change(self, clear_field: bool = True) -> None:
        self.root.focus_search(clear_field)
        self.stack_present = bool(self.stack)

    def add_food(self, food: db.Food) -> None:
        if food.food_id in self.stack:
            self.start_snack_bar(f'Food ID {food.food_id} is already in the stack')

        else:
            self.stack[food.food_id] = food

            self.root.stack_view.data.insert(0, dict(food=food))
            self.after_stack_change()

    def add_foods(self, foods: List[db.Food]) -> None:
        self.stack = {food.food_id: food for food in foods}

        self.root.stack_view.data = [dict(food=food) for food in foods]
        self.after_stack_change()

    @mainthread
    def remove_from_stack(self, *foods: db.Food) -> None:
        for food in foods:
            self.stack.pop(food.food_id)

        self.root.stack_view.data = [d for d in self.root.stack_view.data if d['food'].food_id in self.stack]
        self.after_stack_change(False)

    def clear_food_cards(self) -> None:
        log.info('clear_food_cards button pressed')

        self.remove_from_stack(*self.stack.values())
        Clock.schedule_once(self.root.focus_search, .1)

    def open_select_stack_dialog(self) -> None:
        log.info('load_stack button pressed')

        if not self.saved_stacks:
            return self.start_snack_bar('No stacks have been saved so far.')

        if not self.select_stack_dialog:
            self.select_stack_dialog = SelectStackDialog(
                content_cls=SelectStackContent(),
                on_dismiss=self.root.focus_search,
            )

        self.select_stack_dialog.content_cls.container.clear_widgets()
        for _, option in self.load_from_options.items():
            self.select_stack_dialog.content_cls.container.add_widget(option)

        self.select_stack_dialog.open()

    def open_update_stack_dialog(self) -> None:
        if not self.update_stack_dialog:
            content = UpdateStackContent()

            @mainthread
            def callback(*_) -> None:
                content.input_field.focus = True

            self.update_stack_dialog = UpdateStackDialog(
                content_cls=content, on_open=callback,
                on_dismiss=self.root.focus_search,
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
        self.add_foods([_foods[k] for k in items.keys()])

        log.info(f'selected stack `{stack_name}`')

    def delete_stack(self, stack_name: str) -> None:
        with self.stack_session_manager() as session:
            session.query(stacks.Stack) \
                .filter_by(id=self.saved_stacks.pop(stack_name).id) \
                .delete()

        self.select_stack_dialog.content_cls.container.remove_widget(self.load_from_options.pop(stack_name))
        if not self.load_from_options:
            self.select_stack_dialog.dismiss()

        log.info(f'deleted stack `{stack_name}`')

    def update_stack(self, stack_name: str) -> None:
        self.update_stack_dialog.dismiss()
        if stack_name in self.saved_stacks:
            self.delete_stack(stack_name)

        with self.stack_session_manager() as session:
            self.saved_stacks[stack_name] = session.make(stacks.Stack(name=stack_name, foods={
                food.food_id: float(food.num_servings) for food in self.stack.values()
            }))

            self.load_from_options[stack_name] = SelectStackOption(
                text=stack_name, secondary_text=self.saved_stacks[stack_name].created_at.strftime('%m/%d/%Y')
            )

        log.info(f'updated stack `{stack_name}`')
        self.start_snack_bar(f'stack saved as `{stack_name}`')

    def begin_analysis(self) -> None:
        stack = [card['food'] for card in self.root.stack_view.data]
        with self.session_manager() as session:
            bound_foods = db.get_from_ids(session, stack)
            bound_regions = db.get_from_ids(session, list([self.regions_d[r] for r in self.selected_regions]))
            nutrients = db.Nutrient.as_list(session)

        for bound_food, food in zip(bound_foods, stack):
            bound_food.num_servings = food.num_servings

        output.write_spreadsheet(
            Output(nutrients, bound_regions, bound_foods),
            self.dat_dir / 'Results', f'Sam-{datetime.datetime.now().strftime("%Y%m%d-%H%M%S")}',
            self.build_obj.app_version,
        )

        self.close_app()

    @mainthread
    def close_app(self) -> None:
        self.get_running_app().stop()


if __name__ == '__main__':
    View().run()
