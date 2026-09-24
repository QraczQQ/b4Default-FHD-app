# -*- coding: utf-8 -*-
from Components.config import config, ConfigSubsection, ConfigSelection, ConfigYesNo, ConfigText

if not hasattr(config.plugins, 'b4skinapp'):
    config.plugins.b4skinapp = ConfigSubsection()
settings = config.plugins.b4skinapp
if not hasattr(settings, 'listSize'):
    settings.listSize = ConfigSelection(default='large', choices=[('standard', 'Standard'), ('large', 'Large'), ('xlarge', 'Extra large')])
# Keep the launcher for users who want to open the complete weather plugin.
if not hasattr(settings, 'weatherEnabled'):
    settings.weatherEnabled = ConfigYesNo(default=True)
if not hasattr(settings, 'weatherInline'):
    settings.weatherInline = ConfigYesNo(default=True)
if not hasattr(settings, 'showTimeDate'):
    settings.showTimeDate = ConfigYesNo(default=True)
if not hasattr(settings, 'showExtraInfo'):
    settings.showExtraInfo = ConfigYesNo(default=True)
if not hasattr(settings, 'showCI'):
    settings.showCI = ConfigYesNo(default=True)
if not hasattr(settings, 'showReceiverPanel'):
    settings.showReceiverPanel = ConfigSelection(default='no', choices=[
        ('no', 'No'),
        ('dreambox', 'DMTwo/DMOne'),
    ])
if not hasattr(settings, 'channelNameColor'):
    settings.channelNameColor = ConfigSelection(default='white', choices=[
        'white', 'yellow', 'grey', 'nextAccent', 'nextMuted', 'nextGold',
        'orange', 'red', 'green', 'blue',
    ])
if not hasattr(settings, 'channelDescriptionColor'):
    settings.channelDescriptionColor = ConfigSelection(default='yellow', choices=[
        'white', 'yellow', 'grey', 'nextAccent', 'nextMuted', 'nextGold',
        'orange', 'red', 'green', 'blue',
    ])
# The inline data provider is deliberately separate from the launcher selection.
# Use the classic Weather Plugin by default. Auto also tries it first and only
# then falls back to the optional OpenATV/MetrixWeather backend.
if not hasattr(settings, 'weatherProvider'):
    settings.weatherProvider = ConfigSelection(default='weatherplugin', choices=[
        ('weatherplugin', 'Weather Plugin'),
        ('auto', 'Auto (WeatherPlugin -> OpenATV)'),
        ('metrix', 'OpenATV / MetrixWeather'),
    ])
if not hasattr(settings, 'weatherPlugin'):
    settings.weatherPlugin = ConfigText(default='', fixed_size=False)


def tr(pl, en):
    return pl if config.osd.language.value.startswith('pl') else en
