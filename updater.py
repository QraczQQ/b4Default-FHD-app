# -*- coding: utf-8 -*-
"""GitHub version browser and in-place updater for the plugin and skin."""
from __future__ import print_function

import json
import os
import re
import shutil
import tempfile
import threading
import zipfile

try:
    from urllib.request import Request, urlopen
except ImportError:  # pragma: no cover - compatibility with older images
    from urllib2 import Request, urlopen

from enigma import eTimer
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList
from Components.config import config, configfile
from Screens.Screen import Screen
from Screens.Standby import TryQuitMainloop

from .dialog import b4SkinAppMessageBox as MessageBox
from .paths import SKIN_DIR, SKIN_ROOT
from .settings import tr


PLUGIN_REPOSITORY = 'QraczQQ/b4Default-FHD-app'
SKIN_REPOSITORY = 'QraczQQ/b4Default-FHD-skin'
PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
SKIN_INSTALL_DIR = os.path.join(SKIN_ROOT, 'b4Default-FHD')
VERSION_RE = re.compile(r'^v?(\d+)\.(\d+)\.(\d+)$')
MAX_ARCHIVE_SIZE = 30 * 1024 * 1024


def read_version(path):
    try:
        with open(path, 'r') as version_file:
            value = version_file.read().strip()
        return value if VERSION_RE.match(value) else '0.0.0'
    except Exception:
        return '0.0.0'


APP_VERSION = read_version(os.path.join(PLUGIN_DIR, 'VERSION'))
SKIN_VERSION = read_version(os.path.join(SKIN_DIR, 'VERSION'))

PRODUCTS = {
    'plugin': {
        'name_pl': 'Plugin',
        'name_en': 'Plugin',
        'repository': PLUGIN_REPOSITORY,
        'current': APP_VERSION,
        'marker': 'plugin.py',
        'target': PLUGIN_DIR,
    },
    'skin': {
        'name_pl': 'Skin',
        'name_en': 'Skin',
        'repository': SKIN_REPOSITORY,
        'current': SKIN_VERSION,
        'marker': 'skin.xml',
        'target': SKIN_INSTALL_DIR,
    },
}


def _version_tuple(value):
    match = VERSION_RE.match(value or '')
    return tuple(int(part) for part in match.groups()) if match else None


def _request_json(url):
    request = Request(url, headers={
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'b4Default-FHD-Skin-App/%s' % APP_VERSION,
        'X-GitHub-Api-Version': '2022-11-28',
    })
    response = urlopen(request, timeout=20)
    try:
        payload = response.read()
    finally:
        response.close()
    if not isinstance(payload, str):
        payload = payload.decode('utf-8')
    return json.loads(payload)


def fetch_product_versions(kind):
    """Return one product's semantic-version tags, newest first."""
    product = PRODUCTS[kind]
    url = 'https://api.github.com/repos/%s/tags?per_page=100' % product['repository']
    result = []
    for item in _request_json(url):
        tag = str(item.get('name', '')).strip()
        version = _version_tuple(tag)
        archive_url = item.get('zipball_url')
        if version is not None and archive_url:
            result.append({
                'kind': kind,
                'tag': tag,
                'version': '%d.%d.%d' % version,
                'version_tuple': version,
                'url': str(archive_url),
            })
    result.sort(key=lambda release: release['version_tuple'], reverse=True)
    return result


def fetch_versions():
    result = []
    for kind in ('plugin', 'skin'):
        result.extend(fetch_product_versions(kind))
    return result


def latest_releases(releases):
    """Return at most the newest release of each product."""
    newest = {}
    for release in releases:
        kind = release['kind']
        current = newest.get(kind)
        if current is None or release['version_tuple'] > current['version_tuple']:
            newest[kind] = release
    return [newest[kind] for kind in ('plugin', 'skin') if kind in newest]


def archive_releases(releases):
    """Return published releases older than each product's newest release."""
    newest = dict((release['kind'], release) for release in latest_releases(releases))
    return [
        release for release in releases
        if (release['kind'] in newest and
            release['version_tuple'] < newest[release['kind']]['version_tuple'])
    ]


def fetch_latest_versions():
    return latest_releases(fetch_versions())


def fetch_archive_versions():
    return archive_releases(fetch_versions())


def fetch_available_updates():
    return [
        release for release in fetch_latest_versions()
        if release['version_tuple'] > (_version_tuple(PRODUCTS[release['kind']]['current']) or (0, 0, 0))
    ]


def _download(url, destination):
    request = Request(url, headers={'User-Agent': 'b4Default-FHD-Skin-App/%s' % APP_VERSION})
    response = urlopen(request, timeout=60)
    size = 0
    try:
        with open(destination, 'wb') as archive:
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_ARCHIVE_SIZE:
                    raise ValueError(tr('Paczka aktualizacji jest zbyt duża.', 'The update package is too large.'))
                archive.write(chunk)
    finally:
        response.close()


def _safe_extract(archive_path, destination):
    destination = os.path.abspath(destination)
    with zipfile.ZipFile(archive_path, 'r') as archive:
        for info in archive.infolist():
            member = info.filename.replace('\\', '/')
            target = os.path.abspath(os.path.join(destination, member))
            if target != destination and not target.startswith(destination + os.sep):
                raise ValueError(tr('Paczka zawiera niebezpieczną ścieżkę.', 'The package contains an unsafe path.'))
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError(tr('Paczka zawiera niedozwolony link.', 'The package contains a disallowed link.'))
        archive.extractall(destination)


def _find_source_root(extracted, marker):
    for name in os.listdir(extracted):
        candidate = os.path.join(extracted, name)
        if (os.path.isdir(candidate) and
                os.path.isfile(os.path.join(candidate, 'VERSION')) and
                os.path.isfile(os.path.join(candidate, marker))):
            return candidate
    raise ValueError(tr('Paczka nie zawiera kompletnych plików.', 'The package does not contain complete files.'))


def _runtime_files(source):
    excluded_roots = {'.git', '.github', '.githooks', 'tests', 'tools', '__pycache__'}
    for root, directories, files in os.walk(source):
        directories[:] = [name for name in directories if name not in excluded_roots and not name.startswith('.')]
        relative_root = os.path.relpath(root, source)
        for name in files:
            if name.endswith(('.pyc', '.pyo')) or name.startswith('.'):
                continue
            relative = name if relative_root == '.' else os.path.join(relative_root, name)
            yield relative


def _activate_skin():
    primary_skin = getattr(getattr(config, 'skin', None), 'primary_skin', None)
    if primary_skin is None:
        raise ValueError(tr('Nie można ustawić aktywnego skina.', 'The active skin cannot be configured.'))
    primary_skin.value = 'b4Default-FHD/skin.xml'
    primary_skin.save()
    configfile.save()


def install_release(release):
    """Download, validate and atomically synchronize one product release."""
    product = PRODUCTS[release['kind']]
    target_dir = product['target']
    work_dir = tempfile.mkdtemp(prefix='b4skinapp-update-')
    archive_path = os.path.join(work_dir, 'release.zip')
    extracted = os.path.join(work_dir, 'extracted')
    backup = os.path.join(work_dir, 'backup')
    installed = []
    created = []
    planned = []
    try:
        os.makedirs(extracted)
        os.makedirs(backup)
        if not os.path.isdir(target_dir):
            os.makedirs(target_dir)
        _download(release['url'], archive_path)
        _safe_extract(archive_path, extracted)
        source = _find_source_root(extracted, product['marker'])
        package_version = read_version(os.path.join(source, 'VERSION'))
        if _version_tuple(package_version) != release['version_tuple']:
            raise ValueError(tr(
                'Numer w pliku VERSION nie zgadza się z wybraną wersją.',
                'The VERSION file does not match the selected release.'))

        planned = sorted(_runtime_files(source))
        planned_set = set(planned)
        obsolete = sorted(
            relative for relative in _runtime_files(target_dir)
            if relative not in planned_set
        )
        for relative in planned:
            source_file = os.path.join(source, relative)
            target_file = os.path.join(target_dir, relative)
            target_parent = os.path.dirname(target_file)
            if not os.path.isdir(target_parent):
                os.makedirs(target_parent)
            if os.path.exists(target_file):
                backup_file = os.path.join(backup, relative)
                backup_parent = os.path.dirname(backup_file)
                if not os.path.isdir(backup_parent):
                    os.makedirs(backup_parent)
                shutil.copy2(target_file, backup_file)
                installed.append(relative)
            else:
                created.append(relative)
            temporary = target_file + '.b4skinapp-new'
            shutil.copy2(source_file, temporary)
            os.replace(temporary, target_file)
        # A downgrade must reproduce the selected release, not merely overlay it.
        # Back up files absent from the selected package before removing them so
        # the existing rollback path can restore the previous installation.
        for relative in obsolete:
            target_file = os.path.join(target_dir, relative)
            if not os.path.isfile(target_file):
                continue
            backup_file = os.path.join(backup, relative)
            backup_parent = os.path.dirname(backup_file)
            if not os.path.isdir(backup_parent):
                os.makedirs(backup_parent)
            shutil.copy2(target_file, backup_file)
            installed.append(relative)
            os.unlink(target_file)
        if release['kind'] == 'skin':
            _activate_skin()
        return package_version
    except Exception:
        for relative in planned:
            temporary = os.path.join(target_dir, relative) + '.b4skinapp-new'
            try:
                if os.path.isfile(temporary):
                    os.unlink(temporary)
            except Exception:
                pass
        for relative in installed:
            backup_file = os.path.join(backup, relative)
            target_file = os.path.join(target_dir, relative)
            if os.path.isfile(backup_file):
                shutil.copy2(backup_file, target_file)
        for relative in created:
            target_file = os.path.join(target_dir, relative)
            try:
                if os.path.isfile(target_file):
                    os.unlink(target_file)
            except Exception:
                pass
        raise
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


class b4SkinAppUpdater(Screen):
    skin = '''<screen name="b4SkinAppUpdater" position="center,center" size="1120,690" title="b4SkinApp — Aktualizacja" backgroundColor="#000B111A" flags="wfNoBorder">
      <eLabel position="0,0" size="1114,6" backgroundColor="#00B000FF" />
      <widget name="heading" position="42,28" size="1036,52" font="Regular;34" foregroundColor="#00F2F5FA" backgroundColor="#000B111A" />
      <widget name="installed" position="42,82" size="1036,64" font="Regular;22" foregroundColor="#00ADBACA" backgroundColor="#000B111A" />
      <widget name="versions" position="42,160" size="1036,362" itemHeight="54" font="Regular;28" backgroundColor="#00141E2A" foregroundColor="#00F2F5FA" backgroundColorSelected="#00B000FF" foregroundColorSelected="#00FFFFFF" scrollbarMode="showOnDemand" />
      <widget name="status" position="42,538" size="1036,62" font="Regular;22" foregroundColor="#00ADBACA" backgroundColor="#000B111A" />
      <eLabel position="42,628" size="6,28" backgroundColor="#00FF5A68" />
      <widget name="key_red" position="58,618" size="190,46" font="Regular;23" foregroundColor="#00F2F5FA" backgroundColor="#000B111A" />
      <eLabel position="272,628" size="6,28" backgroundColor="#006BE3A2" />
      <widget name="key_green" position="288,618" size="210,46" font="Regular;23" foregroundColor="#00F2F5FA" backgroundColor="#000B111A" />
      <eLabel position="522,628" size="6,28" backgroundColor="#00F6C56C" />
      <widget name="key_yellow" position="538,618" size="210,46" font="Regular;23" foregroundColor="#00F2F5FA" backgroundColor="#000B111A" />
      <eLabel position="772,628" size="6,28" backgroundColor="#002FA8FF" />
      <widget name="key_blue" position="788,618" size="290,46" font="Regular;23" foregroundColor="#00F2F5FA" backgroundColor="#000B111A" />
      <eLabel position="0,684" size="1120,6" backgroundColor="#00B000FF" />
      <eLabel position="0,6" size="6,678" backgroundColor="#00B000FF" />
      <eLabel position="1114,0" size="6,684" backgroundColor="#00B000FF" />
    </screen>'''

    def __init__(self, session, archive=False):
        Screen.__init__(self, session)
        self.archive = archive
        if self.archive:
            self.setTitle(tr('b4SkinApp — Archiwum wersji', 'b4SkinApp — Version archive'))
            self['heading'] = Label(tr('Archiwum wersji', 'Version archive'))
        else:
            self.setTitle(tr('b4SkinApp — Aktualizacja', 'b4SkinApp — Update'))
            self['heading'] = Label(tr('Najnowsze dostępne wersje', 'Latest available versions'))
        self['installed'] = Label(tr(
            'Plugin: %s\nSkin: %s', 'Plugin: %s\nSkin: %s') % (APP_VERSION, SKIN_VERSION))
        self['versions'] = MenuList([])
        self['status'] = Label('')
        self['key_red'] = Label(tr('Zamknij', 'Close'))
        self['key_green'] = Label(tr('Zainstaluj', 'Install'))
        self['key_yellow'] = Label(tr('Odśwież', 'Refresh'))
        self['key_blue'] = Label('' if self.archive else tr('Archiwum wersji', 'Version archive'))
        self.releases = []
        self.busy = False
        self.closed = False
        self.job = None
        self.job_result = None
        self.timer = eTimer()
        try:
            self.timer.timeout.connect(self._poll_job)
        except Exception:
            self.timer.callback.append(self._poll_job)
        self['actions'] = ActionMap(
            ['OkCancelActions', 'ColorActions'],
            {'cancel': self.closeUpdater, 'red': self.closeUpdater, 'ok': self.installSelected,
             'green': self.installSelected, 'yellow': self.refresh,
             'blue': self.openArchive}, -2)
        self.onShown.append(self._first_show)
        self.onClose.append(self._on_close)

    def _first_show(self):
        if self._first_show in self.onShown:
            self.onShown.remove(self._first_show)
        self.refresh()

    def _on_close(self):
        self.closed = True
        try:
            self.timer.stop()
        except Exception:
            pass

    def closeUpdater(self):
        if not self.busy:
            self.close()

    def openArchive(self):
        if not self.busy and not self.archive:
            self.session.open(b4SkinAppUpdater, archive=True)

    def _run(self, worker, callback):
        if self.busy:
            return
        self.busy = True
        self.job_result = None

        def execute():
            try:
                self.job_result = (True, worker())
            except Exception as error:
                self.job_result = (False, str(error))

        self.job = threading.Thread(target=execute)
        self.job.daemon = True
        self.job.start()
        self.job_callback = callback
        self.timer.start(200, True)

    def _poll_job(self):
        if self.closed:
            return
        if self.job is not None and self.job.is_alive():
            self.timer.start(200, True)
            return
        self.busy = False
        result = self.job_result or (False, tr('Nieznany błąd.', 'Unknown error.'))
        self.job = None
        self.job_callback(result[0], result[1])

    def refresh(self):
        if self.busy:
            return
        if self.archive:
            status = tr('Pobieranie archiwum wersji…', 'Downloading version archive…')
            worker = fetch_archive_versions
        else:
            status = tr('Sprawdzanie najnowszych wersji…', 'Checking latest versions…')
            worker = fetch_latest_versions
        self['status'].setText(status)
        self['versions'].setList([])
        self.releases = []
        self._run(worker, self._versions_loaded)

    def _versions_loaded(self, success, result):
        if not success:
            self['status'].setText(tr('Nie udało się pobrać wersji: ', 'Could not download versions: ') + result)
            return
        self.releases = result
        entries = []
        newer = 0
        for release in result:
            product = PRODUCTS[release['kind']]
            current = _version_tuple(product['current']) or (0, 0, 0)
            suffix = ''
            if release['version_tuple'] > current:
                suffix = tr('  — nowsza', '  — newer')
                newer += 1
            elif release['version_tuple'] == current:
                suffix = tr('  — zainstalowana / reinstalacja',
                            '  — installed / reinstall')
            else:
                suffix = tr('  — starsza / downgrade',
                            '  — older / downgrade')
            entries.append('%s  %s%s' % (tr(product['name_pl'], product['name_en']), release['version'], suffix))
        self['versions'].setList(entries)
        if entries and self.archive:
            self['status'].setText(tr(
                'Wersje archiwalne: %d. Możliwa reinstalacja i downgrade.',
                'Archived versions: %d. Reinstall and downgrade are available.') % len(entries))
        elif entries:
            self['status'].setText(tr(
                'Najnowsze wersje: %d, w tym aktualizacje: %d.',
                'Latest versions: %d, including updates: %d.') % (len(entries), newer))
        elif self.archive:
            self['status'].setText(tr('Brak starszych wersji w archiwum.', 'No older versions in the archive.'))
        else:
            self['status'].setText(tr('Brak opublikowanych wersji.', 'No published versions found.'))

    def installSelected(self):
        if self.busy or not self.releases:
            return
        index = self['versions'].getSelectedIndex()
        if index < 0 or index >= len(self.releases):
            return
        release = self.releases[index]
        product = PRODUCTS[release['kind']]
        product_name = tr(product['name_pl'], product['name_en'])
        current = _version_tuple(product['current']) or (0, 0, 0)
        if release['version_tuple'] < current:
            question = tr(
                'Wykonać downgrade %s do wersji %s?\nPliki zostaną zsynchronizowane z wybraną wersją.',
                'Downgrade %s to version %s?\nFiles will be synchronized with the selected version.')
        elif release['version_tuple'] == current:
            question = tr(
                'Ponownie zainstalować %s w wersji %s?\nPliki zostaną bezpiecznie zastąpione.',
                'Reinstall %s version %s?\nFiles will be replaced safely.')
        else:
            question = tr(
                'Zaktualizować %s do wersji %s?\nPliki zostaną bezpiecznie zastąpione.',
                'Update %s to version %s?\nFiles will be replaced safely.')
        question = question % (product_name, release['version'])
        self.session.openWithCallback(
            lambda answer: self._confirmed(answer, release),
            MessageBox, question, MessageBox.TYPE_YESNO, default=False)

    def _confirmed(self, answer, release):
        if not answer or self.busy:
            return
        product = PRODUCTS[release['kind']]
        self['status'].setText(tr(
            'Pobieranie i instalowanie: %s %s…',
            'Downloading and installing: %s %s…') %
            (tr(product['name_pl'], product['name_en']), release['version']))
        self.installing_release = release
        self._run(lambda: install_release(release), self._installed)

    def _installed(self, success, result):
        if not success:
            self['status'].setText(tr('Aktualizacja nie powiodła się.', 'Update failed.'))
            self.session.open(MessageBox, tr(
                'Nie udało się wykonać aktualizacji:\n',
                'Could not complete the update:\n') + result, MessageBox.TYPE_ERROR)
            return
        product = PRODUCTS[self.installing_release['kind']]
        product_name = tr(product['name_pl'], product['name_en'])
        self['status'].setText(tr('Zainstalowano: %s %s.', 'Installed: %s %s.') % (product_name, result))
        self.session.openWithCallback(
            self._restart, MessageBox,
            tr('Zainstalowano %s %s. Uruchomić ponownie GUI?',
               '%s %s was installed. Restart the GUI?') % (product_name, result),
            MessageBox.TYPE_YESNO, default=True)

    def _restart(self, answer):
        if answer:
            self.session.open(TryQuitMainloop, 3)
        self.close()
