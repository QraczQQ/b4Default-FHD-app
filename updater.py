# -*- coding: utf-8 -*-
"""GitHub version browser and in-place updater for b4Default-FHD Skin App."""
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
from Screens.Screen import Screen
from Screens.Standby import TryQuitMainloop

from .dialog import b4SkinAppMessageBox as MessageBox
from .settings import tr


REPOSITORY = 'QraczQQ/b4Default-FHD-app'
TAGS_URL = 'https://api.github.com/repos/%s/tags?per_page=100' % REPOSITORY
PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
VERSION_RE = re.compile(r'^v?(\d+)\.(\d+)\.(\d+)$')
MAX_ARCHIVE_SIZE = 20 * 1024 * 1024


def read_version(path=None):
    """Read the installed version without making plugin import depend on I/O."""
    try:
        with open(path or os.path.join(PLUGIN_DIR, 'VERSION'), 'r') as version_file:
            value = version_file.read().strip()
        return value if VERSION_RE.match(value) else '0.0.0'
    except Exception:
        return '0.0.0'


APP_VERSION = read_version()


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


def fetch_versions():
    """Return stable semantic-version tags, newest first."""
    result = []
    for item in _request_json(TAGS_URL):
        tag = str(item.get('name', '')).strip()
        version = _version_tuple(tag)
        archive_url = item.get('zipball_url')
        if version is not None and archive_url:
            result.append({
                'tag': tag,
                'version': '%d.%d.%d' % version,
                'version_tuple': version,
                'url': str(archive_url),
            })
    result.sort(key=lambda release: release['version_tuple'], reverse=True)
    return result


def _download(url, destination):
    request = Request(url, headers={'User-Agent': 'b4Default-FHD-Skin-App/%s' % APP_VERSION})
    response = urlopen(request, timeout=45)
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
            # Unix symlinks in a ZIP are not needed by this plugin.
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError(tr('Paczka zawiera niedozwolony link.', 'The package contains a disallowed link.'))
        archive.extractall(destination)


def _find_source_root(extracted):
    candidates = []
    for name in os.listdir(extracted):
        path = os.path.join(extracted, name)
        if os.path.isdir(path):
            candidates.extend((path, os.path.join(path, 'skin_plugin', 'b4Default-FHD-app')))
    for candidate in candidates:
        if os.path.isfile(os.path.join(candidate, 'VERSION')) and os.path.isfile(os.path.join(candidate, 'plugin.py')):
            return candidate
    raise ValueError(tr('Paczka nie zawiera kompletnej wtyczki.', 'The package does not contain a complete plugin.'))


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


def install_release(release, plugin_dir=PLUGIN_DIR):
    """Download, validate and atomically overlay one tagged version."""
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
        _download(release['url'], archive_path)
        _safe_extract(archive_path, extracted)
        source = _find_source_root(extracted)
        package_version = read_version(os.path.join(source, 'VERSION'))
        if _version_tuple(package_version) != release['version_tuple']:
            raise ValueError(tr(
                'Numer w pliku VERSION nie zgadza się z wybraną wersją.',
                'The VERSION file does not match the selected release.'))

        planned = list(_runtime_files(source))
        for relative in planned:
            source_file = os.path.join(source, relative)
            target_file = os.path.join(plugin_dir, relative)
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
        return package_version
    except Exception:
        for relative in planned:
            temporary = os.path.join(plugin_dir, relative) + '.b4skinapp-new'
            try:
                if os.path.isfile(temporary):
                    os.unlink(temporary)
            except Exception:
                pass
        for relative in installed:
            backup_file = os.path.join(backup, relative)
            target_file = os.path.join(plugin_dir, relative)
            if os.path.isfile(backup_file):
                shutil.copy2(backup_file, target_file)
        for relative in created:
            target_file = os.path.join(plugin_dir, relative)
            try:
                if os.path.isfile(target_file):
                    os.unlink(target_file)
            except Exception:
                pass
        raise
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


class b4SkinAppUpdater(Screen):
    skin = '''<screen name="b4SkinAppUpdater" position="center,center" size="1120,690" title="b4SkinApp — Aktualizacja" backgroundColor="#000B111A">
      <eLabel position="0,0" size="1120,6" backgroundColor="#0034D6CF" />
      <widget name="heading" position="42,28" size="1036,52" font="Regular;34" foregroundColor="#00F2F5FA" backgroundColor="#000B111A" />
      <widget name="installed" position="42,84" size="1036,40" font="Regular;23" foregroundColor="#00ADBACA" backgroundColor="#000B111A" />
      <widget name="versions" position="42,142" size="1036,380" itemHeight="54" font="Regular;28" backgroundColor="#00141E2A" foregroundColor="#00F2F5FA" backgroundColorSelected="#00007678" foregroundColorSelected="#00FFFFFF" scrollbarMode="showOnDemand" />
      <widget name="status" position="42,538" size="1036,62" font="Regular;22" foregroundColor="#00ADBACA" backgroundColor="#000B111A" />
      <eLabel position="42,628" size="6,28" backgroundColor="#00FF5A68" />
      <widget name="key_red" position="58,618" size="250,46" font="Regular;25" foregroundColor="#00F2F5FA" backgroundColor="#000B111A" />
      <eLabel position="390,628" size="6,28" backgroundColor="#006BE3A2" />
      <widget name="key_green" position="406,618" size="300,46" font="Regular;25" foregroundColor="#00F2F5FA" backgroundColor="#000B111A" />
      <eLabel position="758,628" size="6,28" backgroundColor="#00F6C56C" />
      <widget name="key_yellow" position="774,618" size="300,46" font="Regular;25" foregroundColor="#00F2F5FA" backgroundColor="#000B111A" />
    </screen>'''

    def __init__(self, session):
        Screen.__init__(self, session)
        self.setTitle(tr('b4SkinApp — Aktualizacja', 'b4SkinApp — Update'))
        self['heading'] = Label(tr('Wybierz wersję z GitHub', 'Choose a GitHub version'))
        self['installed'] = Label(tr('Zainstalowana wersja: ', 'Installed version: ') + APP_VERSION)
        self['versions'] = MenuList([])
        self['status'] = Label('')
        self['key_red'] = Label(tr('Zamknij', 'Close'))
        self['key_green'] = Label(tr('Zainstaluj', 'Install'))
        self['key_yellow'] = Label(tr('Odśwież', 'Refresh'))
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
             'green': self.installSelected, 'yellow': self.refresh}, -2)
        self.onShown.append(self._first_show)
        self.onClose.append(self._on_close)

    def _first_show(self):
        if self.onShown:
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
        self['status'].setText(tr('Pobieranie listy wersji…', 'Downloading version list…'))
        self['versions'].setList([])
        self.releases = []
        self._run(fetch_versions, self._versions_loaded)

    def _versions_loaded(self, success, result):
        if not success:
            self['status'].setText(tr('Nie udało się pobrać wersji: ', 'Could not download versions: ') + result)
            return
        self.releases = result
        current = _version_tuple(APP_VERSION) or (0, 0, 0)
        entries = []
        for release in result:
            suffix = tr('  — nowsza', '  — newer') if release['version_tuple'] > current else ''
            if release['version_tuple'] == current:
                suffix = tr('  — zainstalowana', '  — installed')
            entries.append(release['version'] + suffix)
        self['versions'].setList(entries)
        if entries:
            newer = len([release for release in result if release['version_tuple'] > current])
            self['status'].setText(
                tr('Dostępne nowsze wersje: %d', 'Newer versions available: %d') % newer)
        else:
            self['status'].setText(tr(
                'Brak wersji. Opublikuj w repozytorium tag v1.0.1.',
                'No versions found. Publish the v1.0.1 tag in the repository.'))

    def installSelected(self):
        if self.busy or not self.releases:
            return
        index = self['versions'].getSelectedIndex()
        if index < 0 or index >= len(self.releases):
            return
        release = self.releases[index]
        question = tr(
            'Zainstalować wersję %s?\nPliki wtyczki zostaną zastąpione, a ustawienia użytkownika pozostaną bez zmian.',
            'Install version %s?\nPlugin files will be replaced; user settings will remain unchanged.') % release['version']
        self.session.openWithCallback(
            lambda answer: self._confirmed(answer, release),
            MessageBox, question, MessageBox.TYPE_YESNO, default=False)

    def _confirmed(self, answer, release):
        if not answer or self.busy:
            return
        self['status'].setText(tr('Pobieranie i instalowanie wersji %s…', 'Downloading and installing version %s…') % release['version'])
        self._run(lambda: install_release(release), self._installed)

    def _installed(self, success, result):
        if not success:
            self['status'].setText(tr('Aktualizacja nie powiodła się.', 'Update failed.'))
            self.session.open(MessageBox, tr('Nie udało się zaktualizować wtyczki:\n', 'Could not update the plugin:\n') + result, MessageBox.TYPE_ERROR)
            return
        self['status'].setText(tr('Zainstalowano wersję %s.', 'Installed version %s.') % result)
        self.session.openWithCallback(
            self._restart, MessageBox,
            tr('Zainstalowano wersję %s. Uruchomić ponownie GUI?', 'Version %s was installed. Restart the GUI?') % result,
            MessageBox.TYPE_YESNO, default=True)

    def _restart(self, answer):
        if answer:
            self.session.open(TryQuitMainloop, 3)
        self.close()
