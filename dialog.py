# -*- coding: utf-8 -*-
"""Adaptive layout for DreamNG-owned messages; system MessageBox is untouched."""
from enigma import eSize, ePoint, eLabel, gFont, getDesktop
from Components.ActionMap import ActionMap
from Components.config import config
from Screens.MessageBox import MessageBox


def paginate(text, fits):
    """Split without discarding characters; bound each page by measured height."""
    pages = []
    while text:
        if fits(text):
            pages.append(text)
            break
        low, high = 1, len(text)
        while low < high:
            mid = (low + high + 1) // 2
            if fits(text[:mid]):
                low = mid
            else:
                high = mid - 1
        cut = low
        boundary = max(text.rfind('\n', 0, cut), text.rfind(' ', 0, cut))
        if boundary > cut // 2:
            cut = boundary + 1
        pages.append(text[:cut])
        text = text[cut:]
    return pages or ['']


def layout_message(screen):
    desktop = getDesktop(0).size()
    width = min(1280, desktop.width() - 120)
    max_height = desktop.height() - 160
    margin, top, row, footer = 36, 118, 54, 52
    count = len(getattr(screen, 'list', None) or [])
    list_height = min(count, 6) * row
    gap = 20 if count else 0
    text_width = width - 2 * margin
    text_max = max(100, max_height - top - list_height - gap - footer)
    label = screen['text']
    # Keep the full original even if a plugin reruns onLayoutFinish.
    original = getattr(screen, 'text', None)
    if not isinstance(original, str):
        original = getattr(screen, '_dreamng_full_message', label.getText())
    screen._dreamng_full_message = original
    label.instance.resize(eSize(text_width, text_max))
    def measured(text):
        label.setText(text)
        return label.getSize()[1]
    pages = paginate(original, lambda text: measured(text) <= text_max - 12)
    text_height = min(text_max, max(90, max(measured(page) for page in pages) + 12))
    height = top + text_height + gap + list_height + footer
    screen.instance.resize(eSize(width, height))
    screen.instance.move(ePoint((desktop.width() - width) // 2, (desktop.height() - height) // 2))
    label.instance.move(ePoint(margin, top))
    label.instance.resize(eSize(text_width, text_height))
    screen['list'].instance.move(ePoint(margin, top + text_height + gap))
    screen['list'].instance.resize(eSize(text_width, max(row, list_height)))
    if not count:
        screen['list'].hide()
    if 'Title' in screen and getattr(screen['Title'], 'master', None):
        screen['Title'].master.instance.resize(eSize(width - 160, 58))
    # The footer belongs to this screen and is destroyed along with it.
    hint = getattr(screen, '_dreamng_page_hint', None)
    if hint is None:
        hint = eLabel(screen.instance)
        hint.setFont(gFont('Next', 20))
        hint.setTransparent(1)
        screen._dreamng_page_hint = hint
    hint.move(ePoint(margin, height - 40))
    hint.resize(eSize(text_width, 32))
    pl = config.osd.language.value.startswith('pl')
    screen._dreamng_message_page = 0
    def show(delta=0):
        screen._dreamng_message_page = max(0, min(len(pages) - 1, screen._dreamng_message_page + delta))
        label.setText(pages[screen._dreamng_message_page])
        hint.setText(('%d / %d   |   \u2190 \u2192  %s' % (screen._dreamng_message_page + 1, len(pages),
                      'Strony komunikatu' if pl else 'Message pages')) if len(pages) > 1 else '')
    key = 'dreamngMessagePages'
    if key in screen:
        screen[key].setEnabled(False)
    if len(pages) > 1:
        screen[key] = ActionMap(['DirectionActions'], {'left': lambda: show(-1), 'right': lambda: show(1)}, -10)
    show()


class DreamNGMessageBox(MessageBox):
    """MessageBox with DreamNG pagination, limited to this plugin's dialogs."""

    def __init__(self, session, *args, **kwargs):
        MessageBox.__init__(self, session, *args, **kwargs)
        names = self.skinName if isinstance(self.skinName, list) else [self.skinName]
        if 'DreamNGMessageBox' not in names:
            names.insert(0, 'DreamNGMessageBox')
        self.skinName = names

    def applySkin(self, *args, **kwargs):
        result = MessageBox.applySkin(self, *args, **kwargs)
        self._dreamng_layout_message()
        return result

    def _dreamng_layout_message(self):
        try:
            layout_message(self)
        except Exception as error:
            print('[DreamNG][MessageBox] layout failed: %s' % error)
