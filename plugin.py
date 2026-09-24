# -*- coding: utf-8 -*-
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.Standby import TryQuitMainloop
from Components.ActionMap import ActionMap
from Components.ConfigList import ConfigListScreen
from Components.Label import Label
from Components.config import ConfigSelection, ConfigYesNo, getConfigListEntry, configfile
from .theme import current_palette, apply_palette, apply_panel_visibility, apply_channel_colors, palette_choices
from .settings import settings, tr
from .channel import install_channel_list_hook
from .dialog import b4SkinAppMessageBox as MessageBox
from .weather import weather_plugins, preferred_weather_key, open_weather, start_weather_sources
from .updater import APP_VERSION, b4SkinAppUpdater
from .paths import SKIN_PATH


class b4SkinAppStyle(Screen, ConfigListScreen):
    skin = '''<screen name="b4SkinAppStyle" position="center,center" size="1360,800" title="b4Default-FHD Skin App" backgroundColor="#000B111A" flags="wfNoBorder">
      <eLabel position="0,0" size="1360,6" backgroundColor="#0034D6CF" />
      <widget name="heading" position="44,30" size="690,56" font="Regular;36" foregroundColor="#00F2F5FA" backgroundColor="#000B111A" />
      <widget name="version" position="742,34" size="574,46" font="Regular;24" halign="right" foregroundColor="#00ADBACA" backgroundColor="#000B111A" />
      <widget name="config" position="44,112" size="1272,504" itemHeight="56" font="Regular;30" backgroundColor="#00141E2A" foregroundColor="#00F2F5FA" backgroundColorSelected="#00007678" foregroundColorSelected="#00FFFFFF" scrollbarMode="showOnDemand" />
      <widget name="description" position="44,625" size="1272,72" font="Regular;20" foregroundColor="#00ADBACA" backgroundColor="#000B111A" />
      <eLabel position="44,714" size="6,30" backgroundColor="#00FF5A68" />
      <widget name="key_red" position="62,704" size="280,48" font="Regular;27" foregroundColor="#00F2F5FA" backgroundColor="#000B111A" />
      <eLabel position="362,714" size="6,30" backgroundColor="#006BE3A2" />
      <widget name="key_green" position="380,704" size="280,48" font="Regular;27" foregroundColor="#00F2F5FA" backgroundColor="#000B111A" />
      <eLabel position="998,714" size="6,30" backgroundColor="#004CA3FF" />
      <widget name="key_blue" position="1016,704" size="280,48" font="Regular;27" foregroundColor="#00F2F5FA" backgroundColor="#000B111A" />
      <eLabel position="680,714" size="6,30" backgroundColor="#00F6C56C" />
      <widget name="key_yellow" position="698,704" size="292,48" font="Regular;25" foregroundColor="#00F2F5FA" backgroundColor="#000B111A" />
    </screen>''' 

    def __init__(self, session):
        Screen.__init__(self, session)
        self.setTitle('b4Default-FHD Skin App')
        self['heading'] = Label(tr('b4Default-FHD Skin App — wygląd i pogoda', 'b4Default-FHD Skin App — appearance and weather'))
        self['version'] = Label(tr('Wersja ', 'Version ') + APP_VERSION + tr('  |  MENU: Aktualizacja', '  |  MENU: Update'))
        self['key_red'] = Label(tr('Anuluj', 'Cancel'))
        self['key_green'] = Label(tr('Zapisz', 'Save'))
        self.showAllPlugins = False
        self['key_yellow'] = Label(tr('Wszystkie wtyczki', 'All plugins'))
        self['key_blue'] = Label(tr('Otwórz pogodę', 'Open weather'))
        self['description'] = Label(tr(
            'Lista 840 px: Standard 18 × 46 px, Duża 15 × 56 px, Bardzo duża 14 × 60 px. Czcionki dopasowują się do wysokości wiersza.\nPogoda inline: Auto najpierw używa skonfigurowanego Weather Plugin; backend OpenATV / MetrixWeather jest tylko rezerwą.\nWybrana niżej wtyczka jest skrótem do pełnego ekranu i nie musi być źródłem danych inline.',
            '840 px list: Standard 18 × 46 px, Large 15 × 56 px, Extra large 14 × 60 px. Fonts adapt to the row height.\nInline weather: Auto first uses the configured Weather Plugin; OpenATV / MetrixWeather is only a fallback.\nThe plugin selected below is a launcher for its full screen and does not have to be the inline data provider.'))
        # Enigma2 understands inline \cAARRGGBB escapes in config text.  Each
        # palette name therefore doubles as a live preview of its accent.
        self.palette = ConfigSelection(default=current_palette(SKIN_PATH), choices=palette_choices())
        self.listSize = ConfigSelection(default=settings.listSize.value, choices=[('standard', tr('Standard — 18 kanałów', 'Standard — 18 channels')), ('large', tr('Duża — 15 kanałów', 'Large — 15 channels')), ('xlarge', tr('Bardzo duża — 14 kanałów', 'Extra large — 14 channels'))])
        self.showTimeDate = ConfigYesNo(default=settings.showTimeDate.value)
        self.showExtraInfo = ConfigYesNo(default=settings.showExtraInfo.value)
        self.showCI = ConfigYesNo(default=settings.showCI.value)
        self.showReceiverPanel = ConfigSelection(
            default=settings.showReceiverPanel.value,
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
        self.weatherInline = ConfigYesNo(default=settings.weatherInline.value)
        self.weatherProvider = ConfigSelection(default=settings.weatherProvider.value, choices=[
            ('weatherplugin', 'Weather Plugin'),
            ('auto', tr('Automatycznie (WeatherPlugin → OpenATV)', 'Automatic (WeatherPlugin → OpenATV)')),
            ('metrix', 'OpenATV / MetrixWeather'),
        ])
        self.weatherEnabled = ConfigYesNo(default=settings.weatherEnabled.value)
        found = weather_plugins()
        if settings.weatherPlugin.value and settings.weatherPlugin.value not in [p[0] for p in found]:
            found.extend(p for p in weather_plugins(show_all=True) if p[0] == settings.weatherPlugin.value)
        choices = [(key, name) for key, name, descriptor in found]
        if not choices:
            choices = [('', tr('Brak zainstalowanej wtyczki pogody', 'No installed weather plugin found'))]
        default = settings.weatherPlugin.value or preferred_weather_key(found)
        if default and default not in [key for key, name in choices]:
            choices.append((default, tr('Poprzednio wybrana — niedostępna', 'Previously selected — unavailable')))
        self.weatherPlugin = ConfigSelection(default=default if default in [key for key, name in choices] else choices[0][0], choices=choices)
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
            getConfigListEntry(tr('Źródło danych pogody', 'Inline weather provider'), self.weatherProvider),
            getConfigListEntry(tr('Skrót do pełnej wtyczki pogody', 'Weather plugin shortcut'), self.weatherEnabled),
            getConfigListEntry(tr('Wtyczka pogody', 'Weather plugin'), self.weatherPlugin)
        ], session=session)
        self['actions'] = ActionMap(['OkCancelActions', 'ColorActions', 'MenuActions'], {'cancel': self.close, 'red': self.close, 'green': self.saveStyle, 'ok': self.saveStyle, 'blue': self.previewWeather, 'yellow': self.togglePluginList, 'menu': self.openUpdater}, -2)

    def openUpdater(self):
        self.session.open(b4SkinAppUpdater)

    def togglePluginList(self):
        self.showAllPlugins = not self.showAllPlugins
        selected = self.weatherPlugin.value
        entries = weather_plugins(show_all=self.showAllPlugins)
        choices = [(key, name) for key, name, descriptor in entries]
        if not choices:
            choices = [('', tr('Brak dostępnych wtyczek', 'No available plugins'))]
        self.weatherPlugin.setChoices(choices, default=selected if selected in [x[0] for x in choices] else choices[0][0])
        self['key_yellow'].setText(tr('Tylko pogodowe', 'Weather only') if self.showAllPlugins else tr('Wszystkie wtyczki', 'All plugins'))
        self['config'].invalidateCurrent()

    def previewWeather(self):
        open_weather(self.session, self.weatherPlugin.value)

    def saveStyle(self):
        # Missing weather software must never block saving unrelated skin options.
        # The inline sources stay empty until a supported provider is configured.
        restart_needed = (self.listSize.value != settings.listSize.value or
                          self.weatherEnabled.value != settings.weatherEnabled.value or
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
            settings.weatherEnabled.value = self.weatherEnabled.value
            settings.weatherPlugin.value = self.weatherPlugin.value
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
