from dataclasses import dataclass
from dataclasses import InitVar
from typing import Tuple

from kivy.clock import mainthread
from kivy.core.window import Window
from kivy.input import MotionEvent

__all__ = [
    'show',
    'hide',
    'TouchDown',
]


@mainthread
def show(*widgets) -> None:
    for widget in widgets:
        if hasattr(widget, '_saved_attrs'):
            widget.height, widget.size_hint_y, widget.opacity, widget.disabled = getattr(widget, '_saved_attrs')
            delattr(widget, '_saved_attrs')


@mainthread
def hide(*widgets) -> None:
    for widget in widgets:
        if not hasattr(widget, '_saved_attrs'):
            setattr(widget, '_saved_attrs', (widget.height, widget.size_hint_y, widget.opacity, widget.disabled))
            widget.height, widget.size_hint_y, widget.opacity, widget.disabled = 0, None, 0, True


@dataclass
class TouchDown:
    touch: InitVar[MotionEvent]
    last_x: float = 0.
    last_y: float = 0.
    last_top: float = 0.
    last_left: float = 0.

    @staticmethod
    def absolute_touch_coordinates(touch: MotionEvent) -> Tuple[float, float]:
        return touch.pos[0] + Window.left, Window.top + (Window.height - touch.pos[1])

    def __post_init__(self, touch: MotionEvent) -> None:
        self.last_x, self.last_y = self.absolute_touch_coordinates(touch)
        self.last_top, self.last_left = Window.top, Window.left

    def move_to(self, touch: MotionEvent) -> None:
        new_x, new_y = self.absolute_touch_coordinates(touch)
        Window.top, Window.left = self.last_top + (new_y - self.last_y), self.last_left + (new_x - self.last_x)
