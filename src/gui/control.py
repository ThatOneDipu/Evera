import sys
import logging
import re
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
from hidamari.market import (
    fetch_latest,
    search as market_search,
    fetch_by_tag,
    fetch_thumb_bytes,
    get_download_url,
    download_video,
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
            "on_market_search": self.on_market_search,
        }
        self.builder.connect_signals(signals)

        # Variables init
        self.version = version
        self.window = None
        self.server = None
        self.icon_view = None
        self.video_paths = None
        self.all_key = "all"
        self.market_items = []
        self.market_store = None
        self.market_current_tag = None

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
            ("market_apply", self.on_market_apply),
            ("market_refresh", self.on_market_refresh),
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
        self._init_market()

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

    def _init_market(self):
        tags = ["Anime", "Games", "Car", "Nature", "Superhero", "Fantasy",
                "Space", "Technology", "Animal", "Horror", "Japan", "Holiday"]
        flowbox = self.builder.get_object("FlowBoxMarketTags")
        for tag in tags:
            btn = Gtk.ToggleButton(label=tag)
            btn.connect("toggled", self.on_market_tag_toggled, tag.lower())
            flowbox.add(btn)
        flowbox.show_all()

        self.market_store = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str)
        iconview = self.builder.get_object("IconViewMarket")
        iconview.set_pixbuf_column(0)
        iconview.set_text_column(1)
        iconview.set_model(self.market_store)
        iconview.connect("selection-changed", self._on_market_selection_changed)

        self._load_market_wallpapers()

    def _on_market_selection_changed(self, iconview):
        selected = iconview.get_selected_items()
        status = self.builder.get_object("LabelMarketStatus")
        if selected:
            idx = selected[0].get_indices()[0]
            item = self.market_items[idx]
            status.set_markup(f"<b>{item['title']}</b>  ({item['format']})")
        else:
            status.set_text("")

    def _load_market_wallpapers(self, tag=None, query=None):
        self.market_store.clear()
        self.market_items = []
        status = self.builder.get_object("LabelMarketStatus")
        status.set_text("Loading...")

        def fetch_thread():
            if query:
                items = market_search(query)
            elif tag:
                items = fetch_by_tag(tag)
            else:
                items = fetch_latest()
            GLib.idle_add(self._display_market_items, items)

        thread = threading.Thread(target=fetch_thread, daemon=True)
        thread.start()

    def _display_market_items(self, items):
        self.market_items = items
        self.market_store.clear()
        status = self.builder.get_object("LabelMarketStatus")
        if not items:
            status.set_text("No wallpapers found")
            return
        status.set_text(f"Found {len(items)} wallpapers")

        for i, item in enumerate(items):
            pixbuf = Gtk.IconTheme.get_default().load_icon("video-x-generic", 164, 0)
            self.market_store.append([pixbuf, item["title"][:30], item["slug"]])
            thread = threading.Thread(
                target=self._load_market_thumb,
                args=(item["thumb"], self.market_store, i),
                daemon=True,
            )
            thread.start()

    def _load_market_thumb(self, thumb_url, store, idx):
        data = fetch_thumb_bytes(thumb_url)
        if data:
            try:
                loader = GdkPixbuf.PixbufLoader()
                loader.write(data)
                loader.close()
                pixbuf = loader.get_pixbuf()
                pixbuf = pixbuf.scale_simple(164, 92, GdkPixbuf.InterpType.BILINEAR)
                GLib.idle_add(self._update_market_thumb, store, idx, pixbuf)
            except Exception:
                pass

    def _update_market_thumb(self, store, idx, pixbuf):
        if idx < len(store):
            store[idx][0] = pixbuf

    def on_market_refresh(self, *_):
        old_query = self.builder.get_object("EntryMarketSearch").get_text().strip()
        self._load_market_wallpapers(tag=self.market_current_tag, query=old_query or None)

    def on_market_search(self, entry, *args):
        query = entry.get_text().strip()
        if query:
            self.market_current_tag = None
            for btn in self.builder.get_object("FlowBoxMarketTags").get_children():
                btn.set_active(False)
            self._load_market_wallpapers(query=query)

    def on_market_tag_toggled(self, button, tag):
        if button.get_active():
            self.market_current_tag = tag
            self.builder.get_object("EntryMarketSearch").set_text("")
            self._load_market_wallpapers(tag=tag)
        else:
            self.market_current_tag = None

    def on_market_apply(self, *_):
        iconview = self.builder.get_object("IconViewMarket")
        selected = iconview.get_selected_items()
        if not selected:
            self._show_error("Please select a wallpaper first")
            return
        idx = selected[0].get_indices()[0]
        item = self.market_items[idx]
        status = self.builder.get_object("LabelMarketStatus")
        status.set_markup(f"Downloading <b>{item['title']}</b>...")
        self._download_and_apply(item)

    def _download_and_apply(self, item):
        def work():
            video_url = get_download_url(item["slug"])
            if not video_url:
                GLib.idle_add(self._show_error, f"Could not find download URL for {item['title']}")
                return
            safe_name = re.sub(r'[^\w\-_. ]', '', item["title"]).strip()
            ext = os.path.splitext(video_url.split("?")[0])[1] or ".mp4"
            dest = os.path.join(VIDEO_WALLPAPER_DIR, f"{safe_name}{ext}")
            if download_video(video_url, dest):
                GLib.idle_add(self._on_market_downloaded, dest)
            else:
                GLib.idle_add(self._show_error, f"Failed to download {item['title']}")

        thread = threading.Thread(target=work, daemon=True)
        thread.start()

    def _on_market_downloaded(self, path):
        status = self.builder.get_object("LabelMarketStatus")
        status.set_markup(f"Downloaded: <b>{os.path.basename(path)}</b>")
        self.config[CONFIG_KEY_MODE] = MODE_VIDEO
        paths = self.config[CONFIG_KEY_DATA_SOURCE]
        for name in paths:
            paths[name] = path
        self._save_config()
        if self.server is not None:
            self.server.video(path)
        self._reload_icon_view()

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
