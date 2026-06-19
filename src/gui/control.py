import sys
import logging
import threading
import requests
import multiprocessing as mp
import setproctitle

# TODO: Port to Gtk4/adwaita someday...
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gio, GLib, GdkPixbuf, Gdk

from pydbus import SessionBus
import yt_dlp

from hidamari.monitor import *
from hidamari.commons import *
from hidamari.gui.gui_utils import get_thumbnail, debounce
from hidamari.utils import (
    ConfigUtil,
    setup_autostart,
    is_gnome,
    is_wayland,
    get_video_paths,
)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(LOGGER_NAME)

APP_ID = f"{PROJECT}.gui"
APP_TITLE = "Evera"
APP_UI_RESOURCE_PATH = "/io/jeffshee/Evera/control.ui"


class ControlPanel(Gtk.Application):
    def __init__(self, version, *args, **kwargs):
        super(ControlPanel, self).__init__(
            *args,
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.FLAGS_NONE,
            **kwargs,
        )
        setproctitle.setproctitle(mp.current_process().name)
        # Builder init
        self.builder = Gtk.Builder()
        self.builder.set_application(self)
        try:
            self.builder.add_from_resource(APP_UI_RESOURCE_PATH)
        except GLib.Error:
            ui_path = os.path.join(os.path.dirname(__file__), "..", "assets", "control.ui")
            self.builder.add_from_file(os.path.abspath(ui_path))
        # Handlers declared in `control.ui``
        signals = {
            "on_volume_changed": self.on_volume_changed,
            "on_streaming_activate": self.on_streaming_activate,
            "on_web_page_activate": self.on_web_page_activate,
            "on_blur_radius_changed": self.on_blur_radius_changed,
        }
        self.builder.connect_signals(signals)

        # Variables init
        self.version = version
        self.window = None
        self.server = None
        self.icon_view = None
        self.video_paths = None
        self.all_key = "all"

        self.is_autostart = os.path.isfile(AUTOSTART_DESKTOP_PATH)

        self._connect_server()
        self._load_config()

        # initialize monitors
        self.monitors = Monitors()
        # get video paths
        video_paths = self.config[CONFIG_KEY_DATA_SOURCE]
        for monitor in self.monitors.get_monitors():
            # check if monitor exists in paths
            if monitor in video_paths:
                self.monitors.get_monitor(monitor).set_wallpaper(video_paths[monitor])
            else:
                self.monitors.get_monitor(monitor).set_wallpaper(video_paths['Default'])

        self._setup_context_menu() # setup context menu for selecting monitors

    def _connect_server(self):
        try:
            self.server = SessionBus().get(DBUS_NAME_SERVER)
        except GLib.Error:
            logger.error("[GUI] Couldn't connect to server")
    
    def _setup_context_menu(self):
        self.contextMenu_monitors = Gtk.Menu()
        self.contextMenu_monitors.show_all()
        
        for monitor_name,monitor in self.monitors.get_monitors().items():
            item = Gtk.MenuItem(label=f"Set For {monitor_name}")
            item.connect("activate", self.on_set_as, monitor)
            self.contextMenu_monitors.append(item)

        # add all option
        item = Gtk.MenuItem(label=f"Set For All")
        item.connect("activate", self.on_set_as, self.all_key)
        self.contextMenu_monitors.append(item)

    def _load_config(self):
        self.config = ConfigUtil().load()

    def _save_config(self):
        ConfigUtil().save(self.config)

    @debounce(1)
    def _save_config_delay(self):
        self._save_config()

    def do_startup(self):
        Gtk.Application.do_startup(self)

        screen = Gdk.Screen.get_default()
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
<<<<<<< HEAD
            @define-color bg-dark #0a0a0f;
            @define-color bg-surface #111118;
            @define-color bg-card #16161f;
            @define-color bg-elevated #1a1a26;
            @define-color border-subtle #1e1e30;
            @define-color border-muted #2a2a40;
            @define-color text-primary #e8e8f0;
            @define-color text-secondary #8888a0;
            @define-color accent #3b82f6;
            @define-color accent-glow #2563eb;
            @define-color accent-dim rgba(59, 130, 246, 0.15);
            @define-color surface-hover rgba(59, 130, 246, 0.08);

            window {
                background: @bg-dark;
                color: @text-primary;
            }

            headerbar {
                background: linear-gradient(180deg, #0f0f1a 0%, #0a0a0f 100%);
                border: none;
                border-bottom: 1px solid @border-subtle;
                box-shadow: 0 2px 16px rgba(0,0,0,0.5);
                padding: 4px 8px;
                min-height: 48px;
            }

            .stack-switcher {
                background: @bg-card;
                border-radius: 10px;
                padding: 3px;
            }

            .stack-switcher button {
                background: transparent;
                color: @text-secondary;
                border: none;
                border-radius: 8px;
                padding: 6px 18px;
                margin: 0;
                font-weight: 500;
            }

            .stack-switcher button:checked {
                background: @accent-dim;
                color: @accent;
                box-shadow: 0 0 12px rgba(59, 130, 246, 0.1);
            }

            .stack-switcher button:hover {
                background: @surface-hover;
                color: @text-primary;
            }

            entry {
                background: @bg-card;
                color: @text-primary;
                border: 1px solid @border-muted;
                border-radius: 8px;
                padding: 8px 14px;
                min-height: 20px;
            }

            entry:focus {
                border-color: @accent;
                box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
                background: @bg-elevated;
            }

            entry:disabled {
                opacity: 0.5;
            }

            button {
                background: @bg-card;
                color: @text-primary;
                border: 1px solid @border-muted;
                border-radius: 8px;
                padding: 7px 14px;
                min-height: 20px;
                font-weight: 500;
            }

            button:hover {
                background: @bg-elevated;
                border-color: @border-muted;
            }

            button:active {
                background: @accent-dim;
            }

            button.suggested-action {
                background: linear-gradient(135deg, @accent 0%, @accent-glow 100%);
                color: #ffffff;
                border: none;
                font-weight: 600;
                box-shadow: 0 2px 8px rgba(59, 130, 246, 0.25);
            }

            button.suggested-action:hover {
                background: linear-gradient(135deg, #4b8bf7 0%, #3575e8 100%);
                box-shadow: 0 4px 20px rgba(59, 130, 246, 0.45);
            }

            button.suggested-action:active {
                background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
                box-shadow: 0 1px 4px rgba(59, 130, 246, 0.2);
            }

            button.toggle:checked {
                background: @accent-dim;
                border-color: @accent;
                color: @accent;
            }

            scale slider {
                background: @accent;
                border: 2px solid @bg-dark;
                border-radius: 50%;
                min-width: 16px;
                min-height: 16px;
                box-shadow: 0 0 8px rgba(59, 130, 246, 0.3);
            }

            scale slider:hover {
                box-shadow: 0 0 16px rgba(59, 130, 246, 0.5);
            }

            scale trough {
                background: @bg-card;
                border: 1px solid @border-subtle;
                border-radius: 8px;
                min-height: 6px;
            }

            scale trough highlight {
                background: linear-gradient(90deg, @accent 0%, #60a5fa 100%);
                border-radius: 8px;
            }

            spinbutton {
                background: @bg-card;
                color: @text-primary;
                border: 1px solid @border-muted;
                border-radius: 8px;
            }

            spinbutton button {
                background: transparent;
                border: none;
                color: @text-primary;
                min-width: 24px;
                padding: 4px;
            }

            spinbutton button:hover {
                background: @surface-hover;
            }

            .view {
                background: @bg-card;
                color: @text-primary;
            }

            scrolledwindow {
                border: 1px solid @border-subtle;
                border-radius: 10px;
                background: @bg-surface;
            }

            scrolledwindow .view {
                border-radius: 10px;
                background: transparent;
            }

            scrollbar {
                background: @bg-dark;
                border: none;
            }

            scrollbar slider {
                background: @border-muted;
                border-radius: 4px;
                min-width: 6px;
            }

            scrollbar slider:hover {
                background: @accent;
            }

            label {
                color: @text-primary;
            }

            separator {
                background: @border-subtle;
            }

            popover {
                background: @bg-elevated;
                border: 1px solid @border-muted;
                border-radius: 14px;
                box-shadow: 0 8px 32px rgba(0,0,0,0.6);
            }

            modelbutton {
                color: @text-primary;
                border-radius: 8px;
                padding: 8px 16px;
                margin: 2px 4px;
            }

            modelbutton:hover {
                background: @surface-hover;
            }

            modelbutton:checked {
                background: @accent-dim;
                color: @accent;
            }

            iconview {
                background: transparent;
                color: @text-primary;
            }

            iconview:selected {
                background: @accent-dim;
                border: 1px solid @accent;
                border-radius: 10px;
            }

            .titlebar button {
                background: transparent;
                border: none;
                border-radius: 6px;
                padding: 6px;
                min-width: 32px;
                min-height: 32px;
            }

            .titlebar button:hover {
                background: @surface-hover;
            }

            .titlebar button:active {
                background: @accent-dim;
            }

            .titlebar button.close:hover {
                background: rgba(239, 68, 68, 0.2);
                color: #ef4444;
            }

            expander {
                color: @text-primary;
            }

            expander label {
                color: @text-secondary;
                font-size: 0.9em;
            }

            expander label:hover {
                color: @accent;
            }

            filechooserbutton button {
                background: @bg-card;
                border: 1px solid @border-muted;
            }

            GtkExpander {
                border: none;
            }

            GtkExpander .title {
                color: @text-secondary;
            }

            GtkExpander .title:hover {
                color: @accent;
            }

            #LabelBlurRadius, #LabelVolume {
                color: @text-secondary;
                font-size: 0.9em;
            }

            .flat {
                background: transparent;
                border: none;
                box-shadow: none;
            }

            .flat:hover {
                background: @surface-hover;
            }

            .flat:active {
                background: @accent-dim;
            }
=======
            window { background: rgba(30, 30, 40, 0.98); }
            headerbar { background: linear-gradient(to bottom, #2a2a3d, #1e1e2e); border: none; box-shadow: 0 1px 8px rgba(0,0,0,0.3); }
            .stack-switcher button { background: transparent; color: #cdd6f4; border: none; border-radius: 8px; padding: 6px 16px; margin: 4px 2px; }
            .stack-switcher button:checked { background: rgba(137, 180, 250, 0.3); color: #89b4fa; }
            .stack-switcher button:hover { background: rgba(137, 180, 250, 0.15); }
            entry { background: #313244; color: #cdd6f4; border: 1px solid #45475a; border-radius: 8px; padding: 6px 12px; }
            entry:focus { border-color: #89b4fa; }
            button { background: #313244; color: #cdd6f4; border: 1px solid #45475a; border-radius: 8px; padding: 6px 12px; }
            button:hover { background: #45475a; }
            button.suggested-action { background: #89b4fa; color: #1e1e2e; border: none; font-weight: bold; }
            button.suggested-action:hover { background: #74c7ec; }
            scale slider { background: #89b4fa; border: none; border-radius: 50%; min-width: 14px; min-height: 14px; }
            scale trough { background: #45475a; border-radius: 8px; min-height: 6px; }
            scale trough highlight { background: #89b4fa; border-radius: 8px; }
            spinbutton { background: #313244; color: #cdd6f4; border: 1px solid #45475a; border-radius: 8px; }
            .view { background: #313244; color: #cdd6f4; }
            scrolledwindow { border: 1px solid #45475a; border-radius: 8px; }
            scrolledwindow .view { border-radius: 8px; }
            label { color: #cdd6f4; }
            separator { background: #45475a; }
            popover { background: #1e1e2e; border: 1px solid #45475a; border-radius: 12px; }
            modelbutton { color: #cdd6f4; border-radius: 6px; padding: 6px 12px; }
            modelbutton:hover { background: rgba(137, 180, 250, 0.2); }
            iconview { background: #313244; color: #cdd6f4; border-radius: 8px; }
            iconview:selected { background: rgba(137, 180, 250, 0.3); }
            .titlebar button { background: transparent; border: none; }
            .titlebar button:hover { background: rgba(137, 180, 250, 0.15); }
>>>>>>> a9c496c063d94b4d19ef5681f161f863e9061c33
        """)
        Gtk.StyleContext.add_provider_for_screen(
            screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        actions = [
            (
                "local_video_dir",
                lambda *_: subprocess.run(
                    ["xdg-open", os.path.realpath(VIDEO_WALLPAPER_DIR)]
                ),
            ),
            ("local_video_refresh", self._reload_icon_view),
            ("local_video_apply", self.on_local_video_apply),
            ("local_web_page_apply", self.on_local_web_page_apply),
            ("play_pause", self.on_play_pause),
            ("feeling_lucky", self.on_feeling_lucky),
            (
                "config",
                lambda *_: subprocess.run(["xdg-open", os.path.realpath(CONFIG_PATH)]),
            ),
            ("about", self.on_about),
            ("quit", self.on_quit),
        ]

        for action_name, handler in actions:
            action = Gio.SimpleAction.new(action_name, None)
            action.connect("activate", handler)
            self.add_action(action)

        statefuls = [
            ("mute", self.config[CONFIG_KEY_MUTE], self.on_mute),
            ("autostart", self.is_autostart, self.on_autostart),
            (
                "static_wallpaper",
                self.config[CONFIG_KEY_STATIC_WALLPAPER],
                self.on_static_wallpaper,
            ),
            (
                "pause_when_maximized",
                self.config[CONFIG_KEY_PAUSE_WHEN_MAXIMIZED],
                self.on_pause_when_maximized,
            ),
            (
                "mute_when_maximized",
                self.config[CONFIG_KEY_MUTE_WHEN_MAXIMIZED],
                self.on_mute_when_maximized,
            ),
        ]

        for action_name, state, handler in statefuls:
            action = Gio.SimpleAction.new_stateful(
                action_name, None, GLib.Variant.new_boolean(state)
            )
            action.connect("change-state", handler)
            self.add_action(action)

        if is_wayland():
            self.builder.get_object("TogglePauseWhenMaximized").set_visible(False)
            self.builder.get_object("ToggleMuteWhenMaximized").set_visible(False)

        if not is_gnome():
            # Disable static wallpaper functionality for non-GNOME DE
            self.builder.get_object("ToggleStaticWallpaper").set_visible(False)
            self.builder.get_object("LabelBlurRadius").set_visible(False)
            self.builder.get_object("SpinBlurRadius").set_visible(False)

        self._reload_all_widgets()

    def do_activate(self):
        if self.window is None:
            self.window: Gtk.ApplicationWindow = self.builder.get_object(
                "ApplicationWindow"
            )
            self.window.set_title("Evera")
            self.window.set_application(self)
            self.window.set_position(Gtk.WindowPosition.CENTER)
        self.window.present()

        if self.server is None:
            self._show_error("Couldn't connect to server")

        if self.config[CONFIG_KEY_FIRST_TIME]:
            self._show_welcome()
            self.config[CONFIG_KEY_FIRST_TIME] = False
            self._save_config()

    def _show_welcome(self):
        # Welcome dialog
        dialog = Gtk.MessageDialog(
            parent=self.window,
            modal=True,
            destroy_with_parent=True,
            text="Welcome to Evera ✨",
            message_type=Gtk.MessageType.INFO,
            #    secondary_text="You can bring up the Menu by <b>Right click</b> on the desktop",
            secondary_text="Quickstart for adding local videos:\n ・Click the folder icon to open the Evera folder\n ・Put your videos there\n ・Click the refresh button",
            secondary_use_markup=True,
            buttons=Gtk.ButtonsType.OK,
        )
        dialog.run()
        dialog.destroy()

    def _show_error(self, error):
        dialog = Gtk.MessageDialog(
            parent=self.window,
            modal=True,
            destroy_with_parent=True,
            text="Oops!",
            message_type=Gtk.MessageType.ERROR,
            secondary_text=error,
            buttons=Gtk.ButtonsType.OK,
        )
        dialog.run()
        dialog.destroy()

    def on_local_video_apply(self, *_):
        selected = self.icon_view.get_selected_items()
        if len(selected) != 0:
            # show menu
            self.contextMenu_monitors.show_all()
            self.contextMenu_monitors.popup(None, None, None, None, 0, Gtk.get_current_event_time())
        else:
            dialog = Gtk.MessageDialog(
                parent=self.window,
                modal=True,
                destroy_with_parent=True,
                text="No Video Selected",
                message_type=Gtk.MessageType.INFO,
                secondary_text="There are no video selected.\nPlease choose one first.",
                secondary_use_markup=True,
                buttons=Gtk.ButtonsType.OK,
            )
            dialog.run()
            dialog.destroy()

    def on_set_as(self, widget, monitor):
        index = self.icon_view.get_selected_items()[0].get_indices()[0]
        video_path = self.video_paths[index]
        logger.info(f"[GUI] Local Video Set To {video_path} For Monitor {monitor}")
        self.config[CONFIG_KEY_MODE] = MODE_VIDEO
        paths = self.config[CONFIG_KEY_DATA_SOURCE] if not None else []
        # all option
        if monitor == self.all_key:
            for name,monitor in self.monitors.get_monitors().items():
                paths[name] = video_path
                monitor.set_wallpaper(video_path)
        else:
            paths[monitor.name] = video_path
            self.monitors.get_monitor(monitor.name).set_wallpaper(video_path)

        # also update the Default video
        paths['Default'] = video_path
        self.config[CONFIG_KEY_DATA_SOURCE] = paths
        self._save_config()
        print(video_path, monitor.name)
        if self.server is not None:
            self.server.video(video_path, monitor.name)

    def on_local_web_page_apply(self, *_):
        file_chooser: Gtk.FileChooserButton = self.builder.get_object("FileChooser")
        choose: Gio.File = file_chooser.get_file()
        if choose is None:
            self._show_error("Please choose a HTML file")
            return
        file_path = choose.get_path()
        logger.info(f"[GUI] Local Webpage: {file_path}")
        self.config[CONFIG_KEY_MODE] = MODE_WEBPAGE
        self.config[CONFIG_KEY_DATA_SOURCE]['Default'] = file_path #! we dont want to break the config, webpage and stream modes will kept in Default source
        self._save_config()
        if self.server is not None:
            self.server.webpage(choose.get_path())

    def on_play_pause(self, *_):
        if self.server is None:
            return
        prev_state = self.server.is_paused_by_user
        self.server.is_paused_by_user = not prev_state
        if not prev_state:
            self.server.pause_playback()
        else:
            self.server.start_playback()

    def on_feeling_lucky(self, *_):
        if self.server is not None:
            self.server.feeling_lucky()

    def set_mute_toggle_icon(self):
        toggle_icon: Gtk.Image = self.builder.get_object("ToggleMuteIcon")
        volume, is_mute = self.config[CONFIG_KEY_VOLUME], self.config[CONFIG_KEY_MUTE]
        if volume == 0 or is_mute:
            icon_name = "audio-volume-muted-symbolic"
        elif volume < 30:
            icon_name = "audio-volume-low-symbolic"
        elif volume < 60:
            icon_name = "audio-volume-medium-symbolic"
        else:
            icon_name = "audio-volume-high-symbolic"
        toggle_icon.set_from_icon_name(icon_name=icon_name, size=0)

    def set_scale_volume_sensitive(self):
        scale = self.builder.get_object("ScaleVolume")
        if self.config[CONFIG_KEY_MUTE]:
            scale.set_sensitive(False)
        else:
            scale.set_sensitive(True)

    def set_spin_blur_radius_sensitive(self):
        spin = self.builder.get_object("SpinBlurRadius")
        if self.config[CONFIG_KEY_STATIC_WALLPAPER]:
            spin.set_sensitive(True)
        else:
            spin.set_sensitive(False)

    def on_volume_changed(self, adjustment):
        self.config[CONFIG_KEY_VOLUME] = int(adjustment.get_value())
        logger.info(f"[GUI] Volume: {self.config[CONFIG_KEY_VOLUME]}")
        self._save_config_delay()
        if self.server is not None:
            self.server.volume = self.config[CONFIG_KEY_VOLUME]
        self.set_mute_toggle_icon()

    def on_blur_radius_changed(self, adjustment):
        self.config[CONFIG_KEY_BLUR_RADIUS] = int(adjustment.get_value())
        logger.info(f"[GUI] Blur radius: {self.config[CONFIG_KEY_BLUR_RADIUS]}")
        self._save_config_delay()
        if self.server is not None:
            self.server.blur_radius = self.config[CONFIG_KEY_BLUR_RADIUS]

    def on_mute(self, action, state):
        action.set_state(state)
        self.config[CONFIG_KEY_MUTE] = bool(state)
        logger.info(f"[GUI] {action.get_name()}: {state}")
        self._save_config()
        if self.server is not None:
            self.server.is_mute = self.config[CONFIG_KEY_MUTE]
        self.set_mute_toggle_icon()
        self.set_scale_volume_sensitive()

    def on_autostart(self, action, state):
        action.set_state(state)
        self.is_autostart = bool(state)
        logger.info(f"[GUI] {action.get_name()}: {state}")
        setup_autostart(state)

    def on_static_wallpaper(self, action, state):
        action.set_state(state)
        self.config[CONFIG_KEY_STATIC_WALLPAPER] = bool(state)
        logger.info(f"[GUI] {action.get_name()}: {state}")
        self._save_config()
        if self.server is not None:
            self.server.is_static_wallpaper = self.config[CONFIG_KEY_STATIC_WALLPAPER]
        self.set_spin_blur_radius_sensitive()

    def on_pause_when_maximized(self, action, state):
        action.set_state(state)
        self.config[CONFIG_KEY_PAUSE_WHEN_MAXIMIZED] = bool(state)
        logger.info(f"[GUI] {action.get_name()}: {state}")
        self._save_config()
        if self.server is not None:
            self.server.is_pause_when_maximized = self.config[CONFIG_KEY_PAUSE_WHEN_MAXIMIZED]

    def on_mute_when_maximized(self, action, state):
        action.set_state(state)
        self.config[CONFIG_KEY_MUTE_WHEN_MAXIMIZED] = bool(state)
        logger.info(f"[GUI] {action.get_name()}: {state}")
        self._save_config()
        if self.server is not None:
            self.server.is_mute_when_maximized = self.config[CONFIG_KEY_MUTE_WHEN_MAXIMIZED]

    def on_about(self, *_):
        try:
            self.builder.add_from_resource(APP_UI_RESOURCE_PATH)
        except GLib.Error:
            self.builder.add_from_file(os.path.abspath("./assets/control.ui"))
        about_dialog: Gtk.AboutDialog = self.builder.get_object("AboutDialog")
        about_dialog.set_transient_for(self.window)
        about_dialog.set_version(self.version)
        about_dialog.set_modal(True)
        about_dialog.present()

    def _check_url(self, url):
        # Check if the url is valid
        try:
            response = requests.get(url)
        except requests.exceptions.RequestException as e:
            logger.error(f"[GUI] Failed to access {url}. Error:\n{e}")
            self._show_error(f"Failed to access {url}. Error:\n{e}")
            return False
        if response.status_code >= 400:
            logger.error(
                f"[GUI] Failed to access {url}. Error code: {response.status_code}"
            )
            self._show_error(
                f"Failed to access {url}. Error code: {response.status_code}"
            )
            return False
        return True

    def _check_yt_dlp(self, raw_url):
        # Check if the url is valid (yt_dlp)
        try:
            with yt_dlp.YoutubeDL({"noplaylist": True}) as ydl:
                ydl.extract_info(raw_url, download=False)
        except yt_dlp.utils.DownloadError as e:
            s = " ".join(str(e).split(" ")[1:])
            logger.error(f"[GUI] Failed to stream {raw_url}. Error:\n{s}")
            self._show_error(f"Failed to stream {raw_url}. Error:\n{s}")
            return False
        return True

    def on_streaming_activate(self, entry: Gtk.Entry, *_):
        url = entry.get_text()
        if not self._check_yt_dlp(url):
            return
        logger.info(f"[GUI] Streaming: {url}")
        self.config[CONFIG_KEY_MODE] = MODE_STREAM
        self.config[CONFIG_KEY_DATA_SOURCE]['Default'] = url #! we dont want to break the config, webpage and stream modes will kept in Default source
        self._save_config()
        if self.server is not None:
            self.server.stream(url)

    def on_web_page_activate(self, entry: Gtk.Entry, *_):
        url = entry.get_text()
        if not self._check_url(url):
            return
        logger.info(f"[GUI] Webpage: {url}")
        self.config[CONFIG_KEY_MODE] = MODE_WEBPAGE
        self.config[CONFIG_KEY_DATA_SOURCE]['Default'] = url #! we dont want to break the config, webpage and stream modes will kept in Default source
        self._save_config()
        if self.server is not None:
            self.server.webpage(url)
    
    def on_icon_view_button_press(self, widget, event):
        if event.button == Gdk.BUTTON_SECONDARY:  # Right click
            path_info = widget.get_path_at_pos(event.x, event.y)
            if path_info is not None:
                tree_path = Gtk.TreePath(path_info[0])
                self.icon_view.grab_focus()  
                widget.select_path(tree_path)
                self.contextMenu_monitors.show_all()
                self.contextMenu_monitors.popup(None, None, None, None, 0, Gtk.get_current_event_time())
                return True 
        return False

    def on_quit(self, *_):
        if self.server is not None:
            try:
                self.server.quit()
            except GLib.Error:
                # Ignore NoReply error
                pass
        self.quit()

    def _reload_all_widgets(self):
        self._reload_icon_view()
        self.set_mute_toggle_icon()
        self.set_scale_volume_sensitive()
        self.set_spin_blur_radius_sensitive()
        toggle_mute: Gtk.ToggleButton = self.builder.get_object("ToggleMute")
        toggle_mute.set_state = self.config[CONFIG_KEY_MUTE]

        scale_volume: Gtk.Scale = self.builder.get_object("ScaleVolume")
        adjustment_volume: Gtk.Adjustment = self.builder.get_object("AdjustmentVolume")
        # Temporary block signal
        adjustment_volume.handler_block_by_func(self.on_volume_changed)
        scale_volume.set_value(self.config[CONFIG_KEY_VOLUME])
        adjustment_volume.handler_unblock_by_func(self.on_volume_changed)

        spin_blur_radius: Gtk.Scale = self.builder.get_object("SpinBlurRadius")
        adjustment_blur: Gtk.Adjustment = self.builder.get_object("AdjustmentBlur")
        # Temporary block signal
        adjustment_blur.handler_block_by_func(self.on_blur_radius_changed)
        spin_blur_radius.set_value(self.config[CONFIG_KEY_BLUR_RADIUS])
        adjustment_blur.handler_unblock_by_func(self.on_blur_radius_changed)

        toggle_mute: Gtk.ToggleButton = self.builder.get_object("ToggleAutostart")
        toggle_mute.set_state = self.is_autostart

    def _reload_icon_view(self, *_):
        self.video_paths = get_video_paths()
        list_store = Gtk.ListStore(GdkPixbuf.Pixbuf, str)
        self.icon_view: Gtk.IconView = self.builder.get_object("IconView")
        self.icon_view.set_pixbuf_column(0)
        self.icon_view.set_text_column(1)
        self.icon_view.set_model(list_store)
        self.icon_view.connect("button-press-event", self.on_icon_view_button_press)
        for idx, video_path in enumerate(self.video_paths):
            pixbuf = Gtk.IconTheme().get_default().load_icon("video-x-generic", 96, 0)
            list_store.append([pixbuf, os.path.basename(video_path)])
            thread = threading.Thread(
                target=get_thumbnail, args=(video_path, list_store, idx)
            )
            thread.daemon = True
            thread.start()


def main(
    version="devel", pkgdatadir="/app/share/evera", localedir="/app/share/locale"
):
    try:
        resource = Gio.Resource.load(os.path.join(pkgdatadir, "evera.gresource"))
        resource._register()
        icon_theme = Gtk.IconTheme.get_default()
        icon_theme.add_resource_path("/io/jeffshee/Evera/icons")
    except GLib.Error:
        logger.error("[GUI] Couldn't load resource")

    app = ControlPanel(version)
    app.run(sys.argv)


if __name__ == "__main__":
    main()
