# -*- coding: utf-8 -*-
import threading

from enigma import eTimer
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.Standby import TryQuitMainloop
from Components.ActionMap import ActionMap
from Components.ConfigList import ConfigListScreen
from Components.Label import Label
from Components.config import ConfigSelection, ConfigYesNo, getConfigListEntry, configfile
from .theme import current_palette, apply_palette, apply_panel_visibility, apply_channel_colors, palette_choices, read_panel_visibility
from .settings import settings, tr
from .channel import install_channel_list_hook
from .dialog import b4SkinAppMessageBox as MessageBox
from .weather import open_weather, start_weather_sources
from .updater import APP_VERSION, SKIN_VERSION, b4SkinAppUpdater, fetch_available_updates
from .paths import SKIN_PATH


class b4SkinAppStyle(Screen, ConfigListScreen):
    skin = '''<screen name="b4SkinAppStyle" position="center,center" size="1360,800" title="b4Default-FHD Skin App" backgroundColor="#000B111A" flags="wfNoBorder">
      <eLabel position="0,0" size="1360,6" backgroundColor="#0034D6CF" />
      <widget name="heading" position="44,30" size="690,56" font="Regular;36" foregroundColor="#00F2F5FA" backgroundColor="#000B111A" />
      <widget name="version" position="742,18" size="574,62" font="Regular;22" halign="right" foregroundColor="#00ADBACA" backgroundColor="#000B111A" />
      <widget name="update_hint" position="742,80" size="574,28" font="Regular;20" halign="right" foregroundColor="#00F6C56C" backgroundColor="#000B111A" />
      <widget name="config" position="44,112" size="1272,504" itemHeight="56" font="Regular;30" backgroundColor="#00141E2A" foregroundColor="#00F2F5FA" backgroundColorSelected="#00007678" foregroundColorSelected="#00FFFFFF" scrollbarMode="showOnDemand" />
      <widget name="description" position="44,625" size="1272,72" font="Regular;20" foregroundColor="#00ADBACA" backgroundColor="#000B111A" />
      <eLabel position="44,714" size="6,30" backgroundColor="#00FF5A68" />
      <widget name="key_red" position="62,704" size="280,48" font="Regular;27" foregroundColor="#00F2F5FA" backgroundColor="#000B111A" />
      <eLabel position="362,714" size="6,30" backgroundColor="#006BE3A2" />
      <widget name="key_green" position="380,704" size="280,48" font="Regular;27" foregroundColor="#00F2F5FA" backgroundColor="#000B111A" />
    </screen>''' 

    def __init__(self, session):
        Screen.__init__(self, session)
        self.setTitle('b4Default-FHD Skin App')
        self['heading'] = Label(tr('b4Default-FHD Skin App — wygląd i pogoda', 'b4Default-FHD Skin App — appearance and weather'))
        self['version'] = Label('Plugin: %s\nSkin: %s' % (APP_VERSION, SKIN_VERSION))
        self['update_hint'] = Label('')
        self['key_red'] = Label(tr('Anuluj', 'Cancel'))
        self['key_green'] = Label(tr('Zapisz', 'Save'))
        self['description'] = Label(tr(
            'Lista 840 px: Standard 18 × 46 px, Duża 15 × 56 px, Bardzo duża 14 × 60 px. Czcionki dopasowują się do wysokości wiersza.\nPogoda inline: Auto najpierw używa skonfigurowanego Weather Plugin; backend OpenATV / MetrixWeather jest tylko rezerwą.',
            '840 px list: Standard 18 × 46 px, Large 15 × 56 px, Extra large 14 × 60 px. Fonts adapt to the row height.\nInline weather: Auto first uses the configured Weather Plugin; OpenATV / MetrixWeather is only a fallback.'))
        # Enigma2 understands inline \cAARRGGBB escapes in config text.  Each
        # palette name therefore doubles as a live preview of its accent.
        self.palette = ConfigSelection(default=current_palette(SKIN_PATH), choices=palette_choices())
        self.listSize = ConfigSelection(default=settings.listSize.value, choices=[('standard', tr('Standard — 18 kanałów', 'Standard — 18 channels')), ('large', tr('Duża — 15 kanałów', 'Large — 15 channels')), ('xlarge', tr('Bardzo duża — 14 kanałów', 'Extra large — 14 channels'))])
        try:
            panel_visibility = read_panel_visibility(SKIN_PATH)
        except Exception:
            panel_visibility = {}
        self.showTimeDate = ConfigYesNo(default=panel_visibility.get('infobartimedate', settings.showTimeDate.value))
        self.showExtraInfo = ConfigYesNo(default=panel_visibility.get('infobarsat', settings.showExtraInfo.value))
        self.showCI = ConfigYesNo(default=panel_visibility.get('infobarCI', settings.showCI.value))
        self.showReceiverPanel = ConfigSelection(
            default='dreambox' if panel_visibility.get('infobardng', settings.showReceiverPanel.value == 'dreambox') else 'no',
            choices=[('no', tr('Nie', 'No')), ('dreambox', 'DMTwo/DMOne')],
        )
        color_choices = [
            ('white', tr('Biały', 'White')),
            ('yellow', tr('Żółty', 'Yellow')),
            ('grey', tr('Szary', 'Grey')),
            ('nextAccent', tr('Kolor przewodni', 'Accent colour')),
            ('nextMuted', tr('Przygaszony', 'Muted')),
            ('nextGold', tr('Złoty', 'Gold')),
            ('orange', tr('Pomarańczowy', 'Orange')),
            ('red', tr('Czerwony', 'Red')),
            ('green', tr('Zielony', 'Green')),
            ('blue', tr('Niebieski', 'Blue')),
        ]
        self.channelNameColor = ConfigSelection(default=settings.channelNameColor.value, choices=color_choices)
        self.channelDescriptionColor = ConfigSelection(default=settings.channelDescriptionColor.value, choices=color_choices)
        self.weatherInline = ConfigYesNo(default=panel_visibility.get('infobarweather', settings.weatherInline.value))
        self.weatherProvider = ConfigSelection(default=settings.weatherProvider.value, choices=[
            ('weatherplugin', 'Weather Plugin'),
            ('auto', tr('Automatycznie (WeatherPlugin → OpenATV)', 'Automatic (WeatherPlugin → OpenATV)')),
            ('metrix', 'OpenATV / MetrixWeather'),
        ])
        ConfigListScreen.__init__(self, [
            getConfigListEntry(tr('Kolor przewodni', 'Accent colour'), self.palette),
            getConfigListEntry(tr('Czcionka listy kanałów', 'Channel list font'), self.listSize),
            getConfigListEntry(tr('Kolor nazwy kanału', 'Channel name colour'), self.channelNameColor),
            getConfigListEntry(tr('Kolor opisu kanału', 'Channel description colour'), self.channelDescriptionColor),
            getConfigListEntry(tr('Pokaż datę i czas', 'Show date and time'), self.showTimeDate),
            getConfigListEntry(tr('Pokaż dane dodatkowe', 'Show additional information'), self.showExtraInfo),
            getConfigListEntry(tr('Pokaż Dane CI', 'Show CI data'), self.showCI),
            getConfigListEntry(tr('Pokaż panel odbiornika', 'Show receiver panel'), self.showReceiverPanel),
            getConfigListEntry(tr('Pogoda bezpośrednio w skinie', 'Inline weather in skin'), self.weatherInline),
            getConfigListEntry(tr('Źródło danych pogody', 'Inline weather provider'), self.weatherProvider)
        ], session=session)
        self['actions'] = ActionMap(['OkCancelActions', 'ColorActions', 'MenuActions'], {'cancel': self.close, 'red': self.close, 'green': self.saveStyle, 'ok': self.saveStyle, 'menu': self.openUpdater}, -2)
        self.updateAvailable = False
        self.updateCheckClosed = False
        self.updateCheckResult = None
        self.updateCheckThread = None
        self.updateCheckTimer = eTimer()
        try:
            self.updateCheckTimer.timeout.connect(self._pollUpdateCheck)
        except Exception:
            self.updateCheckTimer.callback.append(self._pollUpdateCheck)
        self.onShown.append(self._startUpdateCheck)
        self.onClose.append(self._stopUpdateCheck)

    def openUpdater(self):
        if self.updateAvailable:
            self.session.open(b4SkinAppUpdater)

    def _startUpdateCheck(self):
        if self._startUpdateCheck in self.onShown:
            self.onShown.remove(self._startUpdateCheck)

        def check():
            try:
                self.updateCheckResult = (True, fetch_available_updates())
            except Exception:
                self.updateCheckResult = (False, [])

        self.updateCheckThread = threading.Thread(target=check)
        self.updateCheckThread.daemon = True
        self.updateCheckThread.start()
        self.updateCheckTimer.start(200, True)

    def _pollUpdateCheck(self):
        if self.updateCheckClosed:
            return
        if self.updateCheckThread is not None and self.updateCheckThread.is_alive():
            self.updateCheckTimer.start(200, True)
            return
        success, updates = self.updateCheckResult or (False, [])
        self.updateAvailable = bool(success and updates)
        self['update_hint'].setText(
            tr('MENU: Aktualizacja', 'MENU: Update') if self.updateAvailable else '')

    def _stopUpdateCheck(self):
        self.updateCheckClosed = True
        try:
            self.updateCheckTimer.stop()
        except Exception:
            pass

    def saveStyle(self):
        # Missing weather software must never block saving unrelated skin options.
        # The inline sources stay empty until a supported provider is configured.
        restart_needed = (self.listSize.value != settings.listSize.value or
                          self.weatherInline.value != settings.weatherInline.value or
                          self.weatherProvider.value != settings.weatherProvider.value or
                          self.showTimeDate.value != settings.showTimeDate.value or
                          self.showExtraInfo.value != settings.showExtraInfo.value or
                          self.showCI.value != settings.showCI.value or
                          self.showReceiverPanel.value != settings.showReceiverPanel.value or
                          self.channelNameColor.value != settings.channelNameColor.value or
                          self.channelDescriptionColor.value != settings.channelDescriptionColor.value)
        try:
            restart_needed = apply_palette(SKIN_PATH, self.palette.value) or restart_needed
            restart_needed = apply_channel_colors(
                SKIN_PATH,
                self.channelNameColor.value,
                self.channelDescriptionColor.value,
            ) or restart_needed
            panel_visibility = {
                'infobartimedate': self.showTimeDate.value,
                'infobarweather': self.weatherInline.value,
                'infobarsat': self.showExtraInfo.value,
                'infobardng': self.showReceiverPanel.value == 'dreambox',
                'infobarCI': self.showCI.value,
            }
            restart_needed = apply_panel_visibility(SKIN_PATH, panel_visibility) or restart_needed
            settings.listSize.value = self.listSize.value
            settings.showTimeDate.value = self.showTimeDate.value
            settings.showExtraInfo.value = self.showExtraInfo.value
            settings.showCI.value = self.showCI.value
            settings.showReceiverPanel.value = self.showReceiverPanel.value
            settings.channelNameColor.value = self.channelNameColor.value
            settings.channelDescriptionColor.value = self.channelDescriptionColor.value
            settings.weatherInline.value = self.weatherInline.value
            settings.weatherProvider.value = self.weatherProvider.value
            settings.save()
            configfile.save()
            # Apply inline-weather visibility immediately as well.  A GUI
            # restart may still be required for the extension-menu shortcut.
            manager = getattr(self.session, '_b4WeatherManager', None)
            if manager is not None:
                manager.refresh()
        except Exception as error:
            self.session.open(MessageBox, tr('Nie udało się zapisać ustawień: ', 'Could not save settings: ') + str(error), MessageBox.TYPE_ERROR)
            return
        if restart_needed:
            self.session.openWithCallback(self.restart, MessageBox, tr('Ustawienia zapisane. Uruchomić ponownie GUI?\nW czasie nagrywania wybierz Nie.', 'Settings saved. Restart the GUI?\nChoose No while recording.'), MessageBox.TYPE_YESNO, default=False)
        else:
            self.close()

    def restart(self, answer):
        if answer:
            self.session.open(TryQuitMainloop, 3)
        self.close()


def main(session, **kwargs):
    session.open(b4SkinAppStyle)


def weather_main(session, **kwargs):
    open_weather(session)


def sessionstart(reason, **kwargs):
    if reason == 0:
        install_channel_list_hook()
        start_weather_sources(kwargs.get('session'))


def Plugins(**kwargs):
    result = [
        PluginDescriptor(where=PluginDescriptor.WHERE_SESSIONSTART, fnc=sessionstart),
        PluginDescriptor(name='b4Default-FHD Skin App', description=tr('Wygląd, większe czcionki i pogoda', 'Appearance, larger fonts and weather'), where=PluginDescriptor.WHERE_PLUGINMENU, icon='plugin.png', fnc=main),
    ]
    if settings.weatherEnabled.value:
        result.append(PluginDescriptor(name=tr('b4SkinApp — Pogoda', 'b4SkinApp — Weather'), description=tr('Otwórz wybraną wtyczkę pogody', 'Open selected weather plugin'), where=PluginDescriptor.WHERE_EXTENSIONSMENU, fnc=weather_main))
    return result
