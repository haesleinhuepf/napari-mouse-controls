import warnings

from napari_plugin_engine import napari_hook_implementation
from qtpy.QtWidgets import QWidget, QHBoxLayout, QPushButton
from magicgui import magic_factory
import napari
from qtpy.QtCore import QSize
from qtpy.QtGui import QIcon
from pathlib import Path

ICON_ROOT = Path(__file__).parent / "icons"

class MouseControls(QWidget):
    """
    The mouse control widget allows to configure what the mouse is doing,
    so far the left mouse button only. This is useful when working with touch screens.

    See also: https://github.com/napari/napari/issues/2060#issuecomment-755709848
    """
    def __init__(self, napari_viewer):
        super().__init__()
        self.viewer = napari_viewer

        # config
        self.active = False
        self.mouse_down = False
        self.mode = None

        # GUI
        self.setLayout(QHBoxLayout())

        btn = QPushButton("Zoom")
        self._init_button(btn)
        btn.clicked.connect(self._zoom)
        self.layout().addWidget(btn)
        self.layout().addWidget(btn)

        btn = QPushButton("Slicing")
        self._init_button(btn)
        btn.clicked.connect(self._slicing)
        self.layout().addWidget(btn)

        btn = QPushButton("Windowing")
        self._init_button(btn)
        btn.clicked.connect(self._windowing)
        self.layout().addWidget(btn)

        btn = QPushButton("Default")
        self._init_button(btn)
        btn.clicked.connect(self._deactivate)
        self.layout().addWidget(btn)

    def _init_button(self, btn):
        btn.setIcon(QIcon(self._get_icon(btn.text())))
        btn.setIconSize(QSize(50, 50))
        btn.setToolTip(btn.text())
        btn.setText("")


    def _get_icon(self, name):
        path = ICON_ROOT / f'{name.lower().replace(" ", "_")}.png'
        if not path.exists():
            return ""
        return str(path)


    def _handle_move(self, x, y):
        delta_x = x - self.start_x
        delta_y = y - self.start_y

        relative_x = delta_x / self.viewer.window.qt_viewer.width()
        relative_y = delta_y / self.viewer.window.qt_viewer.height()

        if self.mode == "Zoom":
            self.viewer.camera.zoom = self._start_zoom * (1 + relative_y)
            print("zoom", relative_y)
        elif self.mode == "Slicing":
            if len(self.current_step) < 3:
                return

            z_dim = -1
            t_dim = -1
            if len(self.current_step) == 3:
                z_dim = 0
            elif len(self.current_step) == 4:
                z_dim = 1
                t_dim = 0
            else:
                return

            z_range = self.viewer.dims.range[z_dim][1] - self.viewer.dims.range[z_dim][0]
            t_range = self.viewer.dims.range[t_dim][1] - self.viewer.dims.range[t_dim][0]

            print("z range",z_range)
            print("wtf", self.viewer.dims.range)

            new_dims = list(self.current_step)

            if z_dim >= 0:
                new_dims[z_dim] = self.current_step[z_dim] + z_range * (-relative_y)
                if new_dims[z_dim] < self.viewer.dims.range[z_dim][0]:
                    new_dims[z_dim] = self.viewer.dims.range[z_dim][0]
                if new_dims[z_dim] > self.viewer.dims.range[z_dim][1]:
                    new_dims[z_dim] = self.viewer.dims.range[z_dim][1]
            if t_dim >= 0:
                new_dims[t_dim] = self.current_step[t_dim] + t_range * (relative_x)
                if new_dims[t_dim] < self.viewer.dims.range[t_dim][0]:
                    new_dims[t_dim] = self.viewer.dims.range[t_dim][0]
                if new_dims[t_dim] > self.viewer.dims.range[t_dim][1]:
                    new_dims[t_dim] = self.viewer.dims.range[t_dim][1]


            print("Pos", self.current_step[z_dim], new_dims[z_dim])

            self.viewer.dims.current_step = new_dims

            #if relative_y < 1:
            #    self.viewer.camera.zoom = self._start_zoom * (1 + relative_y)
            #else:
            #    self.viewer.camera.zoom = self._start_zoom * (1 - relative_y)

        elif self.mode == "Windowing":
            window_width = self.start_contrast_limits_maximum - self.start_contrast_limits_minimum
            window_position = (self.start_contrast_limits_maximum + self.start_contrast_limits_minimum) / 2
            if relative_y < 1:
                window_width = window_width * (1 - relative_y)
            else:
                window_width = window_width * (1 + relative_y)
            if relative_x < 1:
                window_position = window_position * (1 - relative_x)
            else:
                window_position = window_position * (1 + relative_x)

            new_minimum = window_position - window_width / 2
            new_maximum = window_position + window_width / 2

            self.current_layer.contrast_limits = (new_minimum, new_maximum)

    def _zoom(self):
        self._activate()
        self.mode = "Zoom"

    def _windowing(self):
        self._activate()
        self.mode = "Windowing"

    def _slicing(self):
        self._activate()
        self.mode = "Slicing"

    def _activate(self):
        if self.active:
            return

        self.copy_on_mouse_press = self.viewer.window.qt_viewer.on_mouse_press
        self.copy_on_mouse_move = self.viewer.window.qt_viewer.on_mouse_move
        self.copy_on_mouse_release = self.viewer.window.qt_viewer.on_mouse_release

        def our_mouse_press(event=None):

            if self.mode == "Windowing":
                if len(self.viewer.layers.selection) == 0:
                    warnings.warn("No layer selected")
                    return
                if len(self.viewer.layers.selection) == 0:
                    warnings.warn("Multiple layers selected")
                    return
                selected_layers = [layer for layer in self.viewer.layers.selection if isinstance(layer, napari.layers.Image)]
                if not isinstance(selected_layers[0], napari.layers.Image):
                    warnings.warn("No image layer selected")
                    return

                self.current_layer = selected_layers[0]
                self.start_contrast_limits_minimum = self.current_layer.contrast_limits[0]
                self.start_contrast_limits_maximum = self.current_layer.contrast_limits[1]

            print("mouse press", event.native.x(), event.native.y(), event.native.button())
            self.mouse_down = True
            self.start_x = event.native.x()
            self.start_y = event.native.y()

            self.current_step = list(self.viewer.dims.current_step)
            print("CURRENT step", self.current_step)

            self._start_zoom = self.viewer.camera.zoom

        def our_mouse_move(event=None):
            if not self.mouse_down:
                return
            print("mouse move", event.native.x(), event.native.y(), event.native.button())
            self._handle_move(event.native.x(), event.native.y())

        def our_mouse_release(event=None):
            if not self.mouse_down:
                return
            print("mouse release", event.native.x(), event.native.y(), event.native.button())
            self._handle_move(event.native.x(), event.native.y())
            self.mouse_down = False

        self.viewer.window.qt_viewer.on_mouse_press = our_mouse_press
        self.viewer.window.qt_viewer.on_mouse_move = our_mouse_move
        self.viewer.window.qt_viewer.on_mouse_release = our_mouse_release
        self.viewer.camera.interactive=False
        self.active = True

    def _deactivate(self):
        if not self.active:
            return

        self.viewer.window.qt_viewer.on_mouse_press = self.copy_on_mouse_press
        self.viewer.window.qt_viewer.on_mouse_move = self.copy_on_mouse_move
        self.viewer.window.qt_viewer.on_mouse_release = self.copy_on_mouse_release
        self.viewer.camera.interactive=True
        self.active = False


@napari_hook_implementation
def napari_experimental_provide_dock_widget():
    return [MouseControls]
