# -*- coding: utf-8 -*-
"""Weather integration for b4Default-FHD Skin App.

Inline weather and the full-screen weather launcher are intentionally separate.
The inline manager can read two OpenATV-compatible backends:

* current OpenATV / MetrixWeather via Tools.Weatherinfo;
* classic OE-Alliance Weather Plugin via its MSNWeather API.

Auto mode prefers a configured classic Weather Plugin (because that reflects the
location explicitly selected by the user) and falls back to the current OpenATV
MetrixWeather backend when the classic service is unavailable.  Missing weather
software never breaks the skin and never leaves an unexplained empty panel.
"""
import os

from Components.PluginComponent import plugins
from Components.Sources.StaticText import StaticText
from Components.config import config
from Plugins.Plugin import PluginDescriptor
from enigma import eTimer

from .dialog import b4SkinAppMessageBox as MessageBox
from .paths import SKIN_DIR
from .settings import settings, tr

WORDS = ('weather', 'pogoda', 'foreca', 'wetter', 'meteo')
SOURCE_CITY = 'b4WeatherCity'
SOURCE_TEMP = 'b4WeatherTemp'
SOURCE_CONDITION = 'b4WeatherCondition'
SOURCE_ICON = 'b4WeatherIcon'
SOURCE_VISIBLE = 'b4WeatherVisible'
B4SKINAPP_ANIMATED_WEATHER_ICONS = os.path.join(SKIN_DIR, 'animated_weather_icons')
B4SKINAPP_STATIC_WEATHER_ICONS = os.path.join(SKIN_DIR, 'weather_icons')


def _log(message):
    try:
        print('[b4SkinApp][Weather] %s' % message)
    except Exception:
        pass


def launcher(descriptor):
    # Current OpenATV uses .function, older forks may expose .fnc or __call__.
    for attr in ('function', 'fnc', '__call__'):
        value = getattr(descriptor, attr, None)
        if callable(value):
            return value
    return None


def weather_plugins(show_all=False):
    found = {}
    locations = set((
        PluginDescriptor.WHERE_PLUGINMENU,
        PluginDescriptor.WHERE_EXTENSIONSMENU,
        getattr(PluginDescriptor, 'WHERE_MAINMENU', PluginDescriptor.WHERE_PLUGINMENU),
    ))
    for where in locations:
        for descriptor in plugins.getPlugins(where):
            name = str(getattr(descriptor, 'name', ''))
            path = str(getattr(descriptor, 'path', '') or '')
            fnc = launcher(descriptor)
            module = str(getattr(fnc, '__module__', ''))
            identity = (name + ' ' + path + ' ' + module).lower()
            if 'b4skinapp' in identity or name.startswith('b4Default-FHD Skin App'):
                continue
            if not callable(fnc):
                continue
            if not show_all and not any(word in identity for word in WORDS):
                continue
            key = path + '|' + name
            found.setdefault(key, (name, descriptor, identity))
    return [(key, value[0], value[1]) for key, value in sorted(found.items(), key=lambda x: x[1][0].lower())]


def preferred_weather_key(entries=None):
    """Prefer OE-Alliance/OpenATV Weather Plugin as the full-screen launcher."""
    entries = entries if entries is not None else weather_plugins()
    if not entries:
        return ''
    for key, name, descriptor in entries:
        fnc = launcher(descriptor)
        identity = ('%s %s %s' % (name, getattr(descriptor, 'path', '') or '', getattr(fnc, '__module__', '') or '')).lower()
        if 'weatherplugin' in identity or name.strip().lower() == 'weather plugin':
            return key
    return entries[0][0]


def open_weather(session, key=None):
    if key is None:
        if not settings.weatherEnabled.value:
            session.open(MessageBox, tr('Włącz skrót pogody w ustawieniach b4SkinApp.', 'Enable the weather shortcut in b4SkinApp settings.'), MessageBox.TYPE_INFO)
            return
        key = settings.weatherPlugin.value or preferred_weather_key()
    selected = next((p for p in weather_plugins(show_all=True) if p[0] == key), None)
    if selected is None:
        session.open(MessageBox, tr(
            'Nie znaleziono wybranej wtyczki pogody. Zainstaluj z feedu OpenATV „Weather Plugin” albo wybierz inną zainstalowaną wtyczkę.',
            'The selected weather plugin is unavailable. Install “Weather Plugin” from the OpenATV feed or select another installed weather plugin.'
        ), MessageBox.TYPE_INFO)
        return
    try:
        selected[2](session=session)
    except Exception as error:
        session.open(MessageBox, tr('Nie udało się otworzyć wtyczki pogody: ', 'Could not open the weather plugin: ') + str(error), MessageBox.TYPE_ERROR)


def _set_text(source, value):
    value = value or ''
    try:
        source.setText(value)
    except Exception:
        source.text = value


def _value(obj, name, default=''):
    try:
        return getattr(obj, name).value
    except Exception:
        return default


class b4WeatherManager(object):
    """Publish stable weather session sources used by skin XML."""
    INITIAL_DELAY = 1500
    REFRESH_INTERVAL = 30 * 60 * 1000
    RETRY_INTERVAL = 5 * 60 * 1000
    PROVIDER_TIMEOUT = 20 * 1000

    def __init__(self, session):
        self.session = session
        self.weatherData = None
        self.weatherInfo = None
        self.iconPath = ''
        self.iconCode = ''
        self.waiting = ''
        self.provider = ''
        self.timer = eTimer()
        try:
            self.timer.timeout.connect(self._timer_event)
        except Exception:
            self.timer.callback.append(self._timer_event)
        self._set_visibility(settings.weatherInline.value)
        if settings.weatherInline.value:
            self._publish(city=tr('Pogoda', 'Weather'), condition=tr('Ładowanie…', 'Loading…'))
        else:
            self._publish()
        self._arm(self.INITIAL_DELAY)

    def _arm(self, milliseconds, waiting=''):
        self.waiting = waiting
        try:
            self.timer.stop()
        except Exception:
            pass
        self.timer.start(int(milliseconds), True)

    def _timer_event(self):
        waiting = self.waiting
        self.waiting = ''
        if waiting == 'classic':
            _log('classic Weather Plugin timed out')
            self._cancel_classic()
            if settings.weatherProvider.value == 'auto' and self._start_metrix():
                return
            self._failed(tr('Brak danych pogodowych', 'No weather data'))
            return
        if waiting == 'metrix':
            _log('OpenATV/MetrixWeather timed out')
            self._cancel_metrix()
            self._failed(tr('Brak danych pogodowych', 'No weather data'))
            return
        self.refresh()

    def _source(self, name):
        try:
            return self.session.screen[name]
        except Exception:
            return None

    def _publish(self, city='', temp='', condition='', icon=''):
        for name, value in (
            (SOURCE_CITY, city),
            (SOURCE_TEMP, temp),
            (SOURCE_CONDITION, condition),
            (SOURCE_ICON, icon),
        ):
            source = self._source(name)
            if source is not None:
                _set_text(source, value)

    def _set_visibility(self, visible):
        source = self._source(SOURCE_VISIBLE)
        if source is not None:
            _set_text(source, '1' if visible else '')

    def _cancel_classic(self):
        if self.weatherData is not None:
            try:
                self.weatherData.cancel()
            except Exception:
                pass
        self.weatherData = None

    def _cancel_metrix(self):
        if self.weatherInfo is not None:
            try:
                self.weatherInfo.stop()
            except Exception:
                pass
        self.weatherInfo = None

    def _cancel(self):
        self._cancel_classic()
        self._cancel_metrix()

    def _failed(self, text):
        # Keep the panel meaningful instead of presenting an empty dark rectangle.
        self._publish(city=tr('Pogoda', 'Weather'), condition=text)
        self._arm(self.RETRY_INTERVAL)

    def refresh(self):
        self._cancel()
        self.provider = ''
        self._set_visibility(settings.weatherInline.value)
        if not settings.weatherInline.value:
            self._publish()
            self._arm(self.REFRESH_INTERVAL)
            return

        provider = getattr(settings, 'weatherProvider', None)
        provider = getattr(provider, 'value', 'auto')
        if provider == 'weatherplugin':
            if not self._start_classic():
                self._failed(tr('Skonfiguruj Weather Plugin', 'Configure Weather Plugin'))
            return
        if provider == 'metrix':
            if not self._start_metrix():
                self._failed(tr('Skonfiguruj pogodę OpenATV', 'Configure OpenATV weather'))
            return

        # Auto: use an explicitly configured Weather Plugin first.  If it is not
        # present/configured, use the current OpenATV/Metrix Weatherinfo backend.
        if self._start_classic():
            return
        if self._start_metrix():
            return
        self._failed(tr('Brak skonfigurowanego źródła', 'No configured weather source'))

    def _start_classic(self):
        try:
            from Plugins.Extensions.WeatherPlugin import plugin as weather_plugin
            from Plugins.Extensions.WeatherPlugin.MSNWeather import MSNWeather
            cfg = weather_plugin.config.plugins.WeatherPlugin
            count = int(cfg.entrycount.value)
            if count < 1 or len(cfg.Entry) < 1:
                return False
            entry = cfg.Entry[0]
            city = str(_value(entry, 'city', '') or '')
            code = str(_value(entry, 'weatherlocationcode', '') or '')
            degree = str(_value(entry, 'degreetype', 'C') or 'C')
            if not code:
                return False
            self.provider = 'classic'
            self._publish(city=city or tr('Pogoda', 'Weather'), condition=tr('Pobieranie danych…', 'Getting data…'))
            self.iconPath = ''
            self.iconCode = ''
            self.weatherData = MSNWeather()
            self.weatherData.getWeatherData(degree, code, city, self._classic_result, self._classic_icon)
            self._arm(self.PROVIDER_TIMEOUT, 'classic')
            _log('using configured Weather Plugin')
            return True
        except Exception as error:
            _log('Weather Plugin unavailable: %s' % error)
            self._cancel_classic()
            return False

    def _classic_icon(self, index, filename):
        if self.provider != 'classic' or not settings.weatherInline.value:
            return
        try:
            if int(index) != -1:
                return
        except Exception:
            return
        self.iconPath = str(filename or '')
        source = self._source(SOURCE_ICON)
        if source is not None:
            icon = self._weather_icon(self.iconCode, self.iconPath)
            _set_text(source, icon)

    def _classic_result(self, result, errortext):
        data = self.weatherData
        if data is None or self.provider != 'classic':
            return
        if result != getattr(data, 'OK', 1):
            _log('Weather Plugin data error: %s' % (errortext or 'unknown'))
            self._cancel_classic()
            if settings.weatherProvider.value == 'auto' and self._start_metrix():
                return
            self._failed(tr('Błąd Weather Plugin', 'Weather Plugin error'))
            return
        try:
            item = data.weatherItems.get('-1')
            if item is None:
                raise ValueError('missing current weather item')
            city = str(data.city or '')
            temperature = str(getattr(item, 'temperature', '') or '').strip()
            degree = str(getattr(data, 'degreetype', '') or '').strip()
            temp = ('%s°%s' % (temperature, degree)) if temperature else ''
            condition = str(getattr(item, 'skytext', '') or '').strip()
            self.iconCode = self._normalise_weather_code(getattr(item, 'code', ''))
            if not self.iconCode:
                self.iconCode = self._normalise_weather_code(getattr(item, 'skycode', ''))
            provider_icon = str(getattr(item, 'iconFilename', '') or self.iconPath or '')
            icon = self._weather_icon(self.iconCode, provider_icon)
            self._publish(city=city, temp=temp, condition=condition, icon=icon)
            self._arm(self.REFRESH_INTERVAL)
            _log('Weather Plugin data published: code=%s icon=%s' % (self.iconCode or 'NA', icon or 'none'))
        except Exception as error:
            _log('Weather Plugin result parse error: %s' % error)
            self._cancel_classic()
            if settings.weatherProvider.value == 'auto' and self._start_metrix():
                return
            self._failed(tr('Niepełne dane pogodowe', 'Incomplete weather data'))

    def _ensure_metrix_config(self):
        if hasattr(config.plugins, 'MetrixWeather'):
            return True
        try:
            # Loading MyMetrixLite defines config.plugins.MetrixWeather on OpenATV.
            from Plugins.Extensions.MyMetrixLite import plugin as _metrix_plugin  # noqa: F401
        except Exception as error:
            _log('MyMetrixLite config unavailable: %s' % error)
        return hasattr(config.plugins, 'MetrixWeather')

    def _start_metrix(self):
        try:
            if not self._ensure_metrix_config():
                return False
            from Tools.Weatherinfo import Weatherinfo
            cfg = config.plugins.MetrixWeather
            city = str(_value(cfg, 'weathercity', '') or '')
            geocode = str(_value(cfg, 'owm_geocode', '') or '')
            parts = [x.strip() for x in geocode.split(',')]
            if not city or len(parts) != 2 or not parts[0] or not parts[1]:
                return False
            # Validate that coordinates are numeric before starting the backend.
            float(parts[0]); float(parts[1])
            source = str(_value(cfg, 'weatherservice', 'MSN') or 'MSN')
            mode = {'MSN': 'msn', 'OpenMeteo': 'omw', 'openweather': 'owm'}.get(source, 'msn')
            api_key = str(_value(cfg, 'apikey', '') or '')
            unit_value = str(_value(cfg, 'tempUnit', 'Celsius') or 'Celsius')
            units = 'imperial' if unit_value == 'Fahrenheit' else 'metric'
            scheme = str(config.osd.language.value or 'en_GB').replace('_', '-')
            self.provider = 'metrix'
            self._publish(city=city, condition=tr('Pobieranie danych…', 'Getting data…'))
            self.weatherInfo = Weatherinfo(mode, api_key)
            # OpenATV uses geodata=(city, longitude, latitude).
            self.weatherInfo.start(geodata=(city, parts[0], parts[1]), units=units, scheme=scheme, reduced=True, callback=self._metrix_result)
            self._arm(self.PROVIDER_TIMEOUT, 'metrix')
            _log('using OpenATV/MetrixWeather (%s)' % mode)
            return True
        except Exception as error:
            _log('OpenATV/MetrixWeather unavailable: %s' % error)
            self._cancel_metrix()
            return False

    def _normalise_weather_code(self, code):
        code = os.path.splitext(os.path.basename(str(code or '').strip()))[0]
        if code.upper() == 'NA':
            return 'NA'
        return code if code.isdigit() else ''

    def _weather_icon(self, code, provider_icon=''):
        code = self._normalise_weather_code(code)
        provider_icon = str(provider_icon or '').strip()
        candidates = []
        if code:
            candidates.extend((
                os.path.join(B4SKINAPP_ANIMATED_WEATHER_ICONS, code, 'a0.png'),
                os.path.join(B4SKINAPP_STATIC_WEATHER_ICONS, code + '.png'),
            ))
        if provider_icon:
            candidates.append(provider_icon)
        candidates.extend((
            os.path.join(B4SKINAPP_ANIMATED_WEATHER_ICONS, 'NA', 'a0.png'),
            os.path.join(B4SKINAPP_STATIC_WEATHER_ICONS, 'NA.png'),
        ))
        return next((filename for filename in candidates if os.path.isfile(filename)), '')

    def _metrix_icon(self, current):
        return self._weather_icon(current.get('yahooCode', ''))

    def _metrix_result(self, data, error):
        if self.provider != 'metrix':
            return
        if error or not isinstance(data, dict):
            _log('OpenATV/MetrixWeather data error: %s' % (error or 'empty data'))
            self._cancel_metrix()
            self._failed(tr('Błąd danych OpenATV', 'OpenATV weather error'))
            return
        try:
            current = data.get('current') or {}
            city = str(data.get('name') or _value(config.plugins.MetrixWeather, 'weathercity', '') or '')
            temp_value = current.get('temp', '')
            unit_value = str(_value(config.plugins.MetrixWeather, 'tempUnit', 'Celsius') or 'Celsius')
            unit = 'F' if unit_value == 'Fahrenheit' else 'C'
            temp = ('%s°%s' % (temp_value, unit)) if temp_value not in ('', None) else ''
            condition = str(current.get('text') or '')
            icon = self._metrix_icon(current)
            if not (city or temp or condition):
                raise ValueError('empty current weather payload')
            self._publish(city=city, temp=temp, condition=condition, icon=icon)
            self._arm(self.REFRESH_INTERVAL)
            _log('OpenATV/MetrixWeather data published')
        except Exception as exc:
            _log('OpenATV/MetrixWeather result parse error: %s' % exc)
            self._cancel_metrix()
            self._failed(tr('Niepełne dane OpenATV', 'Incomplete OpenATV weather data'))

    def stop(self):
        try:
            self.timer.stop()
        except Exception:
            pass
        self._cancel()


def start_weather_sources(session):
    """Install safe session sources before skin screens reference them."""
    if session is None or not hasattr(session, 'screen'):
        return
    defaults = {
        SOURCE_CITY: tr('Pogoda', 'Weather'),
        SOURCE_TEMP: '',
        SOURCE_CONDITION: tr('Ładowanie…', 'Loading…'),
        SOURCE_ICON: '',
        SOURCE_VISIBLE: '1' if settings.weatherInline.value else '',
    }
    for name in (SOURCE_CITY, SOURCE_TEMP, SOURCE_CONDITION, SOURCE_ICON, SOURCE_VISIBLE):
        if name not in session.screen:
            session.screen[name] = StaticText(defaults[name])
    manager = getattr(session, '_b4WeatherManager', None)
    if manager is None:
        manager = b4WeatherManager(session)
        session._b4WeatherManager = manager
