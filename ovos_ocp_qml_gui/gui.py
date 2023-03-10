import enum
from os.path import join
from time import sleep

from ovos_plugin_common_play.ocp.gui import AbstractOCPMediaPlayerGUI
from ovos_plugin_common_play.ocp.status import PlaybackType, PlayerState
from ovos_utils.log import LOG

from ovos_ocp_qml_gui.utils import is_qtav_available


class VideoPlayerBackend(str, enum.Enum):
    AUTO = "auto"
    QTAV = "qtav"
    NATIVE = "native"


class OCPMediaPlayerQML(AbstractOCPMediaPlayerGUI):
    # Home:
    # The home search page will always be shown at Protocol level index 0
    # This is to ensure that the home is always available to the user
    # regardless of what other pages are currently open
    # Swiping from the player to the left will always show the home page

    # The home page will only be in view if the user is not currently playing an active track
    # If the user is playing a track, the player will be shown instead
    # This is to ensure that the user always returns to the player when they are playing a track

    # The search_spinner_page has been integrated into the home page as an overlay
    # It will be shown when the user is searching for a track and will be hidden when the search is complete
    # on platforms that don't support the notification system

    # Player:
    # Player loader will always be shown at Protocol level index 1
    # The merged playlist and disambiguation pages will always be shown at Protocol level index 2

    # If the user has just opened the ocp home page, and nothing was played previously,
    # the player and merged playlist/disambiguation page will not be shown

    # If the user has just opened the ocp home page, and a track was previously played,
    # the player and merged playlist/disambiguation page will always be shown

    # If the player is not paused or stopped, the player will be shown instead of the home page
    # when ocp is opened

    # Timeout is used to ensure that ocp is fully closed once the timeout has expired

    # QML resource definitions
    @property
    def video_backend(self):
        return self.player.settings.get("video_player_backend") or \
               VideoPlayerBackend.AUTO

    @property
    def home_screen_page(self):
        return join(self.player.res_dir, "ui", "Home.qml")

    @property
    def disambiguation_playlists_page(self):
        return join(self.player.res_dir, "ui", "SuggestionsView.qml")

    @property
    def audio_player_page(self):
        return join(self.player.res_dir, "ui", "OVOSAudioPlayer.qml")

    @property
    def audio_service_page(self):
        return join(self.player.res_dir, "ui", "OVOSSyncPlayer.qml")

    @property
    def video_player_page(self):
        qtav = join(self.player.res_dir, "ui", "OVOSVideoPlayerQtAv.qml")
        native = join(self.player.res_dir, "ui", "OVOSVideoPlayer.qml")
        has_qtav = is_qtav_available()
        if has_qtav:
            LOG.info("QtAV detected")

        if self.video_backend == VideoPlayerBackend.AUTO:
            # detect if qtav is available, if yes use it
            if has_qtav:
                LOG.debug("defaulting to OVOSVideoPlayerQtAv")
                return qtav
            LOG.debug("defaulting to native OVOSVideoPlayer")
        elif self.video_backend == VideoPlayerBackend.QTAV:
            LOG.debug("OVOSVideoPlayerQtAv explicitly configured")
            return qtav
        elif self.video_backend == VideoPlayerBackend.NATIVE:
            LOG.debug("native OVOSVideoPlayer explicitly configured")

        return native

    @property
    def web_player_page(self):
        return join(self.player.res_dir, "ui", "OVOSWebPlayer.qml")

    @property
    def player_loader_page(self):
        return join(self.player.res_dir, "ui", "PlayerLoader.qml")

    # OCP pre-rendering abstract methods
    def prepare_display(self, page_requested, timeout=None):
        state2str = {PlayerState.PLAYING: "Playing",
                     PlayerState.PAUSED: "Paused",
                     PlayerState.STOPPED: "Stopped"}
        self["status"] = state2str[self.player.state]
        self["app_view_timeout_enabled"] = self.player.app_view_timeout_enabled
        self["app_view_timeout"] = self.player.app_view_timeout_value
        self["app_view_timeout_mode"] = self.player.app_view_timeout_mode

        LOG.debug(f"manage_display: page_requested: {page_requested}")
        LOG.debug(f"manage_display: player_status: {self.player.state}")

    def prepare_home(self):
        self.update_ocp_skills()  # populate self["skillCards"]
        self.clear_notification()

        if (self.player.state == PlayerState.PLAYING and self.player.app_view_timeout_enabled
                and self.player.app_view_timeout_mode == "all"):
            self.schedule_app_view_timeout()

    def prepare_player(self):
        # Always clear the spinner and notification before showing the player
        self.remove_search_spinner()
        self.clear_notification()
        self.update_current_track()  # populate now_playing metadata
        check_backend = self._get_player_page()
        if self.get("playerBackend", "") != check_backend:
            self.unload_player_loader()

    def prepare_audio_player(self):
        self.prepare_player()

    def prepare_video_player(self):
        self.prepare_player()

    def prepare_sync_player(self):
        self.prepare_player()

    def prepare_web_player(self):
        self.prepare_player()

    def prepare_playlist(self):
        self.update_playlist()  # populate self["playlistModel"]

    def prepare_search(self):
        self.update_search_results()  # populate self["searchModel"]

    def prepare_search_spinner(self):
        pass

    def prepare_playback_error(self):
        pass

    # OCP rendering abstract methods
    def render_home(self):
        if self.player.state == PlayerState.PLAYING:
            self.show_page(self.player_loader_page, override_idle=True, override_animations=True)
        else:
            self.show_page(self.home_screen_page, override_idle=True, override_animations=True)

    def render_player(self):
        self["playerBackend"] = self._get_player_page()
        self.show_pages(self._get_pages_to_display(), 0, override_idle=True, override_animations=True)

    def render_audio_player(self):
        self.render_player()

    def render_video_player(self):
        self.render_player()

    def render_sync_player(self):
        self.render_player()

    def render_web_player(self):
        self.render_player()

    def render_playlist(self, timeout=None):
        self["displaySuggestionBar"] = False
        self.send_event("ocp.gui.show.suggestion.view.playlist")
        if timeout is not None:
            self.show_page(self.disambiguation_playlists_page, override_idle=timeout, override_animations=True)
        else:
            self.show_page(self.disambiguation_playlists_page, override_idle=True, override_animations=True)

    def render_disambiguation(self, timeout=None):
        self["displaySuggestionBar"] = False
        self.send_event("ocp.gui.show.suggestion.view.disambiguation")
        if timeout is not None:
            self.show_page(self.disambiguation_playlists_page, override_idle=timeout, override_animations=True)
        else:
            self.show_page(self.disambiguation_playlists_page, override_idle=True, override_animations=True)

    def render_playback_error(self):
        if self.active_extension == "smartspeaker":
            self.display_notification("Sorry, An error occurred while playing media")
            sleep(0.4)
            self.clear_notification()
        else:
            self["footer_text"] = "Sorry, An error occurred while playing media"
            self.remove_search_spinner()

    def render_search_spinner(self):
        self.render_home()
        sleep(0.2)
        self.send_event("ocp.gui.show.busy.overlay")
        self["footer_text"] = "Querying Skills\n\n"

    def remove_search_spinner(self):
        self.send_event("ocp.gui.hide.busy.overlay")

    # page helpers
    def unload_player_loader(self):
        self.send_event("ocp.gui.player.loader.clear")

    def _get_player_page(self):
        if self.player.active_backend == PlaybackType.AUDIO_SERVICE or \
                self.player.settings.get("force_audioservice", False):
            return self.audio_service_page
        elif self.player.active_backend == PlaybackType.VIDEO:
            return self.video_player_page
        elif self.player.active_backend == PlaybackType.AUDIO:
            return self.audio_player_page
        elif self.player.active_backend == PlaybackType.WEBVIEW:
            return self.web_player_page
        elif self.player.active_backend == PlaybackType.MPRIS:
            return self.audio_service_page
        else:  # external playback (eg. skill)
            # TODO ?
            return self.audio_service_page

    def _get_pages_to_display(self):
        # determine pages to be shown
        self["playerBackend"] = self._get_player_page()
        LOG.debug(f"pages to display backend: {self['playerBackend']}")

        if len(self.player.disambiguation):
            self["displaySuggestionBar"] = False
            self.send_event("ocp.gui.show.suggestion.view.disambiguation")

        if len(self.player.tracks):
            self["displaySuggestionBar"] = False
            self.send_event("ocp.gui.show.suggestion.view.playlist")

        if len(self.player.disambiguation) and len(self.player.tracks):
            self["displaySuggestionBar"] = True
            self.send_event("ocp.gui.show.suggestion.view.playlist")

        pages = [self.player_loader_page, self.disambiguation_playlists_page]

        return pages
