"""Local, atomic palette updates; no network requests or background services."""
import os
import re
import tempfile
import xml.etree.ElementTree as ET

PALETTES = {
    'aurora': ('#0034D6CF', '#00195759'),
    'amber': ('#00F6C56C', '#0060441F'),
    'violet': ('#00BCABFF', '#00483C70'),
    'ocean': ('#002FA8FF', '#001A4566'),
    'emerald': ('#0034D399', '#00184C3C'),
    'ruby': ('#00F05252', '#00602028'),
    'rose': ('#00FF6FAE', '#00602A43'),
    'coral': ('#00FF8066', '#0060352B'),
    'lime': ('#00A8E05F', '#00394F25'),
    'gold': ('#00E8B84A', '#0053411D'),
    'ice': ('#006EDDEB', '#00224F58'),
    'sky': ('#005A9CFF', '#00203963'),
    'magenta': ('#00D86CFF', '#00502A62'),
}
PALETTE_NAMES = (
    ('aurora', 'Aurora'),
    ('amber', 'Amber'),
    ('violet', 'Violet'),
    ('ocean', 'Ocean'),
    ('emerald', 'Emerald'),
    ('ruby', 'Ruby'),
    ('rose', 'Rose'),
    ('coral', 'Coral'),
    ('lime', 'Lime'),
    ('gold', 'Gold'),
    ('ice', 'Ice'),
    ('sky', 'Sky'),
    ('magenta', 'Magenta'),
)
ACCENTS = {'nextAccent', 'infobaraccent1', 'infobarprogress', 'layer-a-accent1',
           'layer-b-accent1', 'layer-a-progress', 'layer-a-underline',
           'scrollbarSlidercolor', 'layer-a-channelselection-progressbar'}
STRONG_SELECTIONS = {
    'aurora': '#00007678',
    'amber': '#00805412',
    'violet': '#006C4A9A',
    'ocean': '#001F6FA8',
    'emerald': '#001B7255',
    'ruby': '#008F2732',
    'rose': '#009A3C69',
    'coral': '#009A4938',
    'lime': '#005E8A32',
    'gold': '#00806A20',
    'ice': '#002A8797',
    'sky': '#00355FA0',
    'magenta': '#00783A95',
}
SELECTIONS = {'nextAccentDim', 'layer-a-selection-background',
              'layer-b-selection-background'}
INFOBAR_PANELS = (
    'infobartimedate',
    'infobarweather',
    'infobarsat',
    'infobardng',
    'infobarCI',
)
CHANNEL_COLORS = (
    'white',
    'yellow',
    'grey',
    'nextAccent',
    'nextMuted',
    'nextGold',
    'orange',
    'red',
    'green',
    'blue',
)


def palette_choices(reset='#00F2F5FA'):
    """Return palette labels coloured with the same accent they preview."""
    reset_code = '\\c' + reset.lstrip('#').upper()
    return [
        (key, '\\c%s%s%s' % (PALETTES[key][0].lstrip('#').upper(), name, reset_code))
        for key, name in PALETTE_NAMES
    ]

def current_palette(path):
    try:
        root = ET.parse(path).getroot()
        value = root.find("./colors/color[@name='nextAccent']").get('value').upper()
        for key, pair in PALETTES.items():
            if pair[0].upper() == value:
                return key
    except (OSError, ET.ParseError, AttributeError):
        pass
    return 'aurora'

def atomic_write(path, payload, mode=0o644):
    directory = os.path.dirname(os.path.abspath(path))
    fd, temp = tempfile.mkstemp(prefix='.b4skinapp-', dir=directory)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fchmod(stream.fileno(), mode)
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

def apply_palette(path, key):
    if key not in PALETTES:
        raise ValueError('Unknown palette')
    with open(path, 'rb') as stream:
        original = stream.read()
    root = ET.fromstring(original)
    if root.tag != 'skin' or root.find("./colors/color[@name='nextAccent']") is None:
        raise ValueError('A compatible Default-FHD skin.xml is required')
    accent, selected = PALETTES[key]
    text = original.decode('utf-8')
    changes = [0]
    def replace(match):
        tag = match.group(0)
        item = ET.fromstring(tag)
        name = item.get('name')
        new = STRONG_SELECTIONS[key] if name == 'nextSelection' else accent if name in ACCENTS else selected if name in SELECTIONS else None
        if new is None:
            return tag
        changes[0] += 1
        return re.sub(r'value\s*=\s*([\"\']).*?\1', 'value="%s"' % new, tag)
    changed = re.sub(r'<color\b[^<>]*/>', replace, text)
    ET.fromstring(changed)
    if changes[0] < 2:
        raise ValueError('Palette entries not found')
    payload = changed.encode('utf-8')
    if payload == original:
        return False
    # The previous XML is recoverable even if writing the new one fails.
    atomic_write(path + '.before-style', original)
    atomic_write(path, payload)
    return True


def apply_panel_visibility(path, visibility):
    """Persist InfoBar panel visibility without relying on skin `condition`."""
    unknown = set(visibility) - set(INFOBAR_PANELS)
    if unknown:
        raise ValueError('Unknown InfoBar panel: %s' % ', '.join(sorted(unknown)))
    with open(path, 'rb') as stream:
        original = stream.read()
    text = original.decode('utf-8')
    screen_pattern = re.compile(
        r'(<screen\b(?=[^>]*\bname\s*=\s*["\']InfoBar["\'])[^>]*>)(.*?)(</screen>)',
        re.DOTALL,
    )
    screen_match = screen_pattern.search(text)
    if screen_match is None:
        raise ValueError('InfoBar screen not found')
    body = screen_match.group(2)
    for name in INFOBAR_PANELS:
        enabled_pattern = re.compile(
            r'^(?P<indent>[ \t]*)<panel\b(?=[^>]*\bname\s*=\s*["\']%s["\'])[^>]*/>[ \t]*(?P<eol>\r?)$'
            % re.escape(name),
            re.MULTILINE,
        )
        disabled_pattern = re.compile(
            r'^(?P<indent>[ \t]*)<!--\s*[A-Za-z0-9_-]+ panel %s disabled\s*-->[ \t]*(?P<eol>\r?)$'
            % re.escape(name),
            re.MULTILINE,
        )
        enabled_match = enabled_pattern.search(body)
        disabled_match = disabled_pattern.search(body)
        if bool(enabled_match) == bool(disabled_match):
            raise ValueError('InfoBar panel marker is missing or duplicated: %s' % name)
        if visibility.get(name, True):
            current = disabled_match or enabled_match
            replacement = '%s<panel name="%s" />%s' % (current.group('indent'), name, current.group('eol'))
        else:
            current = enabled_match or disabled_match
            replacement = '%s<!-- b4SkinApp panel %s disabled -->%s' % (current.group('indent'), name, current.group('eol'))
        body = body[:current.start()] + replacement + body[current.end():]
    changed = text[:screen_match.start(2)] + body + text[screen_match.end(2):]
    ET.fromstring(changed)
    payload = changed.encode('utf-8')
    if payload == original:
        return False
    atomic_write(path + '.before-panels', original)
    atomic_write(path, payload)
    return True


def read_panel_visibility(path):
    """Read the actual InfoBar panel state from skin.xml."""
    with open(path, 'rb') as stream:
        text = stream.read().decode('utf-8')
    screen_pattern = re.compile(
        r'<screen\b(?=[^>]*\bname\s*=\s*["\']InfoBar["\'])[^>]*>(.*?)</screen>',
        re.DOTALL,
    )
    screen_match = screen_pattern.search(text)
    if screen_match is None:
        raise ValueError('InfoBar screen not found')
    body = screen_match.group(1)
    result = {}
    for name in INFOBAR_PANELS:
        enabled = re.search(
            r'^\s*<panel\b(?=[^>]*\bname\s*=\s*["\']%s["\'])[^>]*/>\s*$' % re.escape(name),
            body,
            re.MULTILINE,
        )
        disabled = re.search(
            r'^\s*<!--\s*[A-Za-z0-9_-]+ panel %s disabled\s*-->\s*$' % re.escape(name),
            body,
            re.MULTILINE,
        )
        if bool(enabled) != bool(disabled):
            result[name] = bool(enabled)
    return result


def apply_channel_colors(path, service_name, service_description):
    """Set the normal and selected service-list colors in ChannelSelection."""
    if service_name not in CHANNEL_COLORS:
        raise ValueError('Unknown channel name color: %s' % service_name)
    if service_description not in CHANNEL_COLORS:
        raise ValueError('Unknown channel description color: %s' % service_description)
    with open(path, 'rb') as stream:
        original = stream.read()
    text = original.decode('utf-8')
    screen_pattern = re.compile(
        r'(<screen\b(?=[^>]*\bname\s*=\s*["\']ChannelSelection["\'])[^>]*>)(.*?)(</screen>)',
        re.DOTALL,
    )
    screen_match = screen_pattern.search(text)
    if screen_match is None:
        raise ValueError('ChannelSelection screen not found')
    body = screen_match.group(2)
    widget_pattern = re.compile(
        r'<widget\b(?=[^>]*\bname\s*=\s*["\']list["\'])[^>]*/>',
        re.DOTALL,
    )
    widgets = list(widget_pattern.finditer(body))
    if len(widgets) != 1:
        raise ValueError('ChannelSelection list widget is missing or duplicated')
    widget_match = widgets[0]
    widget = widget_match.group(0)

    def set_attribute(tag, name, value):
        pattern = re.compile(r'(\b%s\s*=\s*)(["\']).*?\2' % re.escape(name))
        if pattern.search(tag) is None:
            raise ValueError('ChannelSelection attribute not found: %s' % name)
        return pattern.sub(lambda match: '%s"%s"' % (match.group(1), value), tag, count=1)

    for attribute in ('foregroundColor', 'foregroundColorSelected'):
        widget = set_attribute(widget, attribute, service_name)
    for attribute in ('colorServiceDescription', 'colorServiceDescriptionSelected'):
        widget = set_attribute(widget, attribute, service_description)
    body = body[:widget_match.start()] + widget + body[widget_match.end():]
    changed = text[:screen_match.start(2)] + body + text[screen_match.end(2):]
    ET.fromstring(changed)
    payload = changed.encode('utf-8')
    if payload == original:
        return False
    atomic_write(path + '.before-channel-colors', original)
    atomic_write(path, payload)
    return True
