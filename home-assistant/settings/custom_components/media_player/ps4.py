"""Playstation 4 media_player using ps4-waker."""
import json
import logging
import socket
from datetime import timedelta

import voluptuous as vol

import homeassistant.util as util
from homeassistant.components.media_player import (
    ENTITY_IMAGE_URL, MEDIA_TYPE_CHANNEL, MediaPlayerDevice, PLATFORM_SCHEMA,
    SUPPORT_SELECT_SOURCE, SUPPORT_STOP, SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
)
from homeassistant.const import (
    CONF_FILENAME, CONF_HOST, CONF_NAME, STATE_IDLE, STATE_OFF, STATE_PLAYING,
    STATE_UNKNOWN,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.util.json import load_json, save_json

REQUIREMENTS = [
    'https://github.com/hmn/python-ps4/archive/master.zip'
    '#pyps4==dev']
#    'https://github.com/hthiery/python-ps4/archive/master.zip'
#    '#pyps4==dev']
# REQUIREMENTS = ['pyps4==0.1.3']

_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)

SUPPORT_PS4 = SUPPORT_TURN_OFF | SUPPORT_TURN_ON | \
    SUPPORT_STOP | SUPPORT_SELECT_SOURCE

DEFAULT_NAME = 'Playstation 4'
ICON = 'mdi:playstation'
CONF_CREDENTIALS_FILENAME = "credentials_filename"
CONF_GAMES_FILENAME = 'games_filename'
CONF_LOCAL_STORE = "local_store"

CREDENTIALS_FILE = ''
PS4_GAMES_FILE = '.ps4-games.json'
MEDIA_IMAGE_DEFAULT = None
LOCAL_STORE = 'games'
CONFIG_FILE = '.ps4.conf'

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_FILENAME, default=CONFIG_FILE): cv.string,
    vol.Optional(CONF_CREDENTIALS_FILENAME,
                 default=CREDENTIALS_FILE): cv.string,
    vol.Optional(CONF_GAMES_FILENAME, default=PS4_GAMES_FILE): cv.string,
    vol.Optional(CONF_LOCAL_STORE, default=LOCAL_STORE): cv.string
})


def _check_ps4(host, credentials):
    """Check if PS4 is responding."""
    import pyps4

    if host is None:
        return False

    if credentials is None:
        return False

    try:
        try:
            playstation = pyps4.Ps4(host, credentials)
            info = playstation.get_status()
            _LOGGER.debug("Searched for PS4 [%s] on network and got : %s",
                          host, info)
        except IOError as error:
            _LOGGER.error("Error connecting to PS4 [%s] : %s", host, error)
            return False
        finally:
            pass

    except (IOError, OSError) as error:
        _LOGGER.error("Error loading PS4 [%s] credentials : %s", host, error)
        return False

    return True


def setup_ps4(host, name, hass, config, add_devices, credentials):
    """Set up PS4."""
    import pyps4
    games_filename = hass.config.path(config.get(CONF_GAMES_FILENAME))
    local_store = config.get(CONF_LOCAL_STORE)

    try:
        ps4 = pyps4.Ps4(host, credentials)
    except (IOError, OSError) as error:
        _LOGGER.error("Error loading PS4 credentials [%s] : %s", host, error)

    add_devices([PS4Device(name, ps4, local_store, games_filename)], True)


def request_configuration(host, name, hass, config, add_devices, credentials):
    """Request configuration steps from the user."""
    configurator = hass.components.configurator
    # We got an error if this method is called while we are configuring
    if host in _CONFIGURING:
        configurator.notify_errors(
            _CONFIGURING[host],
            'Failed to register host, please try again [%s].',
            host)
        return

    def ps4_configuration_callback(data):
        """Handle configuration changes."""
        credentials = data.get('credentials')
        if _check_ps4(host, credentials):
            setup_ps4(host, name, hass,
                      config, add_devices, credentials)

            def success():
                """Set up was successful."""
                conf = load_json(hass.config.path(config.get(CONF_FILENAME)))
                conf[host] = {'credentials': credentials}
                save_json(hass.config.path(config.get(CONF_FILENAME)), conf)
                req_config = _CONFIGURING.pop(host)
                hass.async_add_job(configurator.request_done, req_config)

            hass.async_add_job(success)

    _CONFIGURING[host] = configurator.request_config(
        DEFAULT_NAME,
        ps4_configuration_callback,
        description='Enter credentials',
        # entity_picture='/static/images/logo_ps4.png',
        link_name='Howto generate credentials',
        link_url='https://home-assistant.io/components/media_player.ps4/',
        submit_caption='Confirm',
        fields=[{
            'id': 'credentials',
            'name': 'PS4-Waker credentials json',
            'type': 'text'
        }])


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the PS4 platform."""
    if discovery_info is not None:
        host = discovery_info.get(CONF_HOST)
        name = DEFAULT_NAME
        credentials = None
    else:
        host = config.get(CONF_HOST)
        name = config.get(CONF_NAME, DEFAULT_NAME)
        if config.get(CONF_CREDENTIALS_FILENAME) != '':
            credentials = hass.config.path(
                config.get(CONF_CREDENTIALS_FILENAME))
        else:
            credentials = None

    if not credentials:
        conf = load_json(hass.config.path(config.get(CONF_FILENAME)))
        if conf.get(host, {}).get('credentials'):
            credentials = conf[host]['credentials']

    if host is None:
        request_configuration(host, name, hass, config,
                              add_devices, credentials)
        return

    if credentials is None:
        request_configuration(host, name, hass, config,
                              add_devices, credentials)
        return

    # if not _check_ps4(host, credentials):
    #     request_configuration(host, name, hass, config,
    #                           add_devices, credentials)
    #     return

    setup_ps4(host, name, hass,
              config, add_devices, credentials)


class PS4Device(MediaPlayerDevice):
    """Representation of a PS4."""

    def __init__(self, name, ps4, local_store, games_filename):
        """Initialize the ps4 device."""
        self.ps4 = ps4
        self._name = name
        self._state = STATE_UNKNOWN
        self._gamesmap = {}
        self._local_store = local_store
        self._games_filename = games_filename
        self._media_content_id = None
        self._media_title = None
        self._source = None
        self._source_selected = None
        self._source_list = []
        self._games = {}
        self._load_games()

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update(self):
        """Retrieve the latest data."""
        try:
            data = self.ps4.get_status()
            _LOGGER.debug("ps4 get_status, %s", data)

            # save current game running.
            if data.get('running-app-titleid'):
                if data.get('running-app-titleid') not in self._games.keys():
                    game = {data.get('running-app-titleid'):
                            data.get('running-app-name')}
                    self._games.update(game)
                    self._save_games()

            if data.get('status') == 'Ok':
                if self._source_selected is None:
                    _LOGGER.debug(
                        "updating source, selected:%s current:%s running:%s",
                        self._source_selected,
                        self._source,
                        data.get('running-app-name'))
                    self._media_title = data.get('running-app-name')
                    self._media_content_id = data.get('running-app-titleid')
                    self._source = data.get('running-app-name')
                elif self._source_selected == data.get('running-app-name'):
                    _LOGGER.debug(
                        "selected source, selected:%s current:%s running:%s",
                        self._source_selected,
                        self._source,
                        data.get('running-app-name'))
                    self._media_title = data.get('running-app-name')
                    self._media_content_id = data.get('running-app-titleid')
                    self._source = data.get('running-app-name')
                    self._source_selected = None
                else:
                    _LOGGER.debug(
                        "selecting source, selected:%s current:%s running:%s",
                        self._source_selected,
                        self._source,
                        data.get('running-app-name'))

                if self._media_content_id is not None:
                    self._state = STATE_PLAYING
                    # Check if cover art is in the gamesmap
                    self.check_gamesmap()
                else:
                    self._state = STATE_IDLE
            else:
                self._state = STATE_OFF
                self._media_title = None
                self._media_content_id = None
                self._source = None
                self._source_selected = None
        except socket.timeout as error:
            _LOGGER.debug("PS4 socket timed out, %s", error)
            self._state = STATE_OFF
            self._media_title = None
            self._media_content_id = None
            self._source = None
            self._source_selected = None

    def check_gamesmap(self):
        """Check games map for coverart."""
        if self._media_content_id not in self._gamesmap:
            # Attempt to get cover art from playstation store
            self.ps_store_cover_art()

    def ps_store_cover_art(self):
        """Store coverart from PS store in games map."""
        import requests
        import urllib

        cover_art = None
        try:
            url = 'https://store.playstation.com'
            url += '/valkyrie-api/en/US/19/faceted-search/'
            url += urllib.parse.quote(self._media_title.encode('utf-8'))
            url += '?query='
            url += urllib.parse.quote(self._media_title.encode('utf-8'))
            url += '&platform=ps4'
            headers = {
                'User-Agent':
                    'Mozilla/5.0 '
                    '(Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/63.0.3239.84 Safari/537.36'
            }
            req = requests.get(url, headers=headers)
        except requests.exceptions.HTTPError as error:
            _LOGGER.error("PS cover art HTTP error, %s", error)

        except requests.exceptions.RequestException as error:
            _LOGGER.error("PS cover art request failed, %s", error)

        for item in req.json()['included']:
            if 'attributes' in item:
                game = item['attributes']
                if 'game-content-type' in game and \
                   game['game-content-type'] in \
                   ['App', 'Game', 'Full Game', 'PSN Game']:
                    if 'thumbnail-url-base' in game:
                        _LOGGER.debug("Found cover art for %s, %s %s",
                                      self._media_content_id,
                                      game['game-content-type'],
                                      game['thumbnail-url-base'])
                        cover_art = game['thumbnail-url-base']
                        cover_art += '?w=512&h=512'
                        self._gamesmap[self._media_content_id] = cover_art
                        break

    @property
    def entity_picture(self):
        """Return picture."""
        if self._state == STATE_OFF:
            return None

        image_hash = self.media_image_hash
        if image_hash is not None:
            return ENTITY_IMAGE_URL.format(
                self.entity_id, self.access_token, image_hash)

        if self._media_content_id is None:
            return None

        filename = "/local/%s/%s.jpg" % \
            (self._local_store, self._media_content_id)
        return filename

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def icon(self):
        """Icon."""
        return ICON

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        return self._media_content_id

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_CHANNEL

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        if self._media_content_id is None:
            return MEDIA_IMAGE_DEFAULT

        try:
            return self._gamesmap[self._media_content_id]
        except KeyError:
            return MEDIA_IMAGE_DEFAULT

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._media_title

    @property
    def supported_features(self):
        """Media player features that are supported."""
        return SUPPORT_PS4

    @property
    def source(self):
        """Return the current input source."""
        return self._source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_list

    def turn_off(self):
        """Turn off media player."""
        self.ps4.standby()

    def turn_on(self):
        """Turn on the media player."""
        self.ps4.wakeup()

    def media_pause(self):
        """Send keypress ps to return to menu."""
        self.ps4.remote_control('ps')

    def media_stop(self):
        """Send keypress ps to return to menu."""
        self.ps4.remote_control('ps')

    def select_source(self, source):
        """Select input source."""
        if self._source_selected is not None:
            _LOGGER.debug(
                'Application %s is already in the process of starting (%s)',
                self._source_selected, source)
            return

        for title_id, game in self._games.items():
            if source == game:
                _LOGGER.debug(
                    'Starting PS4 game %s (%s) using source %s',
                    game, title_id, source)
                self._source_selected = source
                self._source = source
                self._media_title = game
                self._media_content_id = title_id
                self.ps4.start_title(title_id)
                return

    def _load_games(self):
        _LOGGER.debug('_load_games: %s', self._games_filename)
        try:
            with open(self._games_filename, 'r') as file:
                self._games = json.load(file)
                self._source_list = list(sorted(self._games.values()))
        except FileNotFoundError:
            self._save_games()
        except ValueError as error:
            _LOGGER.error('Games json file wrong: %s', error)

    def _save_games(self):
        _LOGGER.debug('_save_games: %s', self._games_filename)
        try:
            with open(self._games_filename, 'w') as file:
                json.dump(self._games, file)
                self._source_list = list(sorted(self._games.values()))
        except FileNotFoundError:
            pass
