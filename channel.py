# -*- coding: utf-8 -*-
"""Large, readable channel-list typography restricted to this screen instance."""
from types import MethodType
from enigma import eSize, gFont
from Components.config import config
from .settings import settings

# The option always means the real number of visible services.  In particular,
# the two-line service-list mode must not silently replace 18 rows with 10 (or
# 14 with 8).  Font sizes are derived from the resulting item height so that
# the same profiles also work with a skin whose list widget is not 840 px high.
ROWS = {'standard': 18, 'large': 15, 'xlarge': 14}
SINGLE_LINE_FONT_SCALE = {
    'ServiceName': ('NextBold', 0.57, 20),
    'ServiceInfo': ('Next', 0.40, 16),
    'ServiceNumber': ('Next', 0.48, 18),
}
TWO_LINE_FONT_SCALE = {
    'ServiceName': ('NextBold', 0.47, 16),
    'ServiceInfo': ('Next', 0.35, 14),
    'ServiceNumber': ('Next', 0.48, 18),
}


def _layout(service_list):
    rows = ROWS.get(settings.listSize.value, ROWS['large'])
    item_height = max(1, service_list.listHeight // rows)
    return rows, item_height


def _scaled_font(item_height, scale, minimum):
    return max(minimum, int(item_height * scale + 0.5))


def configure_channel_list(screen):
    service_list = screen['list']
    if not all(hasattr(service_list, key) for key in ('ServiceNameFontName', 'setItemsPerPage', 'setFontsize', 'setMode', 'l', 'listHeight')):
        return False

    def set_rows(instance):
        rows, item_height = _layout(instance)
        instance.ItemHeight = item_height
        instance.l.setItemHeight(item_height)
        instance.instance.resize(eSize(instance.listWidth, rows * item_height))

    def set_fonts(instance):
        item_height = _layout(instance)[1]
        font_scale = TWO_LINE_FONT_SCALE if config.usage.servicelist_twolines.value else SINGLE_LINE_FONT_SCALE
        for field, definition in font_scale.items():
            family, scale, minimum = definition
            points = _scaled_font(item_height, scale, minimum)
            setattr(instance, field + 'FontName', family)
            setattr(instance, field + 'FontSize', points)
            setattr(instance, field + 'Font', gFont(family, points))
        progress_scale = 0.32 if config.usage.servicelist_twolines.value else 0.35
        progress_points = _scaled_font(item_height, progress_scale, 14)
        instance.progressInfoFontName = 'Next'
        instance.progressInfoFontSize = progress_points
        instance.ProgressInfoFont = gFont('Next', progress_points)
        instance.l.setElementFont(instance.l.celServiceName, instance.ServiceNameFont)
        instance.l.setElementFont(instance.l.celServiceInfo, instance.ServiceInfoFont)
        instance.l.setElementFont(instance.l.celServiceNumber, instance.ServiceNumberFont)

    service_list.setItemsPerPage = MethodType(set_rows, service_list)
    service_list.setFontsize = MethodType(set_fonts, service_list)
    service_list.setFontsize()
    service_list.setMode(service_list.mode)
    return True


def _apply_channel_list(screen):
    try:
        if not configure_channel_list(screen):
            print('[DreamNG][Channel] unsupported service-list implementation')
    except Exception as error:
        print('[DreamNG][Channel] configuration failed: %s' % error)


def install_channel_list_hook():
    """Attach DreamNG typography to every real ChannelSelection instance."""
    try:
        from Screens.ChannelSelection import ChannelSelection
    except Exception as error:
        print('[DreamNG][Channel] ChannelSelection unavailable: %s' % error)
        return False

    if not getattr(ChannelSelection, '_dreamng_hook_installed', False):
        original_apply_skin = ChannelSelection.applySkin

        def dreamng_apply_skin(screen, *args, **kwargs):
            result = original_apply_skin(screen, *args, **kwargs)
            _apply_channel_list(screen)
            return result

        ChannelSelection.applySkin = dreamng_apply_skin
        ChannelSelection._dreamng_original_apply_skin = original_apply_skin
        ChannelSelection._dreamng_hook_installed = True

    instance = getattr(ChannelSelection, 'instance', None)
    if instance is not None:
        service_list = instance['list']
        if getattr(instance, 'instance', None) is not None and getattr(service_list, 'instance', None) is not None:
            _apply_channel_list(instance)
    return True
