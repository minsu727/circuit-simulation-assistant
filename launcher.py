"""Console portable launcher; Streamlit shares this process's lifetime."""
import argparse
import _thread
import logging
from logging.handlers import RotatingFileHandler
import os
import socket
import threading
import time
import urllib.error
import urllib.request
import webbrowser

from runtime_paths import locate_app_resource, locate_ltspice, user_data_root

LOG = logging.getLogger('portable_launcher')


def select_port(preferred=8501):
    for port in range(preferred, min(preferred + 20, 65536)):
        with socket.socket() as sock:
            try:
                sock.bind(('127.0.0.1', port))
                return sock.getsockname()[1]
            except OSError:
                pass
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def local_url(port):
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('Invalid localhost port')
    return f'http://127.0.0.1:{port}'


def wait_until_ready(url, stopped, timeout=60):
    deadline = time.monotonic() + timeout
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while not stopped.is_set() and time.monotonic() < deadline:
        try:
            with opener.open(url + '/_stcore/health', timeout=1) as response:
                if response.status == 200 and response.read(16).strip() == b'ok':
                    return True
        except (OSError, urllib.error.URLError):
            pass
        stopped.wait(.2)
    return False


def open_when_ready(url, stopped, no_browser=False, timeout=60):
    if not wait_until_ready(url, stopped, timeout):
        if not stopped.is_set():
            LOG.error('Local server readiness timed out.')
            print('Startup timed out. Close this window and inspect logs/launcher.log in the application data folder.', flush=True)
            _thread.interrupt_main()
        return
    LOG.info('Local server ready at %s', url)
    print(f'Ready: {url}\nKeep this launcher open. Press Ctrl+C to stop the server.', flush=True)
    if no_browser:
        return
    try:
        opened = webbrowser.open(url, new=2)
        LOG.info('Browser open request accepted: %s', bool(opened))
        if not opened:
            print(f'Open this address manually: {url}', flush=True)
    except Exception:
        LOG.warning('Browser launch failed; server remains available.')
        print(f'Open this address manually: {url}', flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-browser', action='store_true', help='Start server without opening a browser.')
    args = parser.parse_args(argv)
    stopped = threading.Event()
    worker = None
    handler = None
    try:
        data = user_data_root()
        (data / 'logs').mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(data / 'logs/launcher.log', maxBytes=512000, backupCount=2, encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        LOG.addHandler(handler)
        LOG.setLevel(logging.INFO)
        LOG.propagate = False
        script = locate_app_resource()
        # Avoid unrelated CWD configuration and write caches outside resources.
        os.chdir(data)
        os.environ.setdefault('MPLCONFIGDIR', str(data / 'matplotlib'))
        from streamlit.web import bootstrap
        from streamlit import __version__
        if __version__ != '1.63.0':
            raise RuntimeError('Launcher requires the validated Streamlit 1.63.0 bootstrap API.')
        port = select_port()
        url = local_url(port)
        options = {'server.address': '127.0.0.1', 'server.port': port,
                   'server.headless': True, 'server.fileWatcherType': 'none',
                   'server.runOnSave': False, 'browser.gatherUsageStats': False,
                   'global.developmentMode': False, 'server.enableStaticServing': False}
        bootstrap.load_config_options(options)
        LOG.info('Starting portable server; LTspice detected: %s', locate_ltspice() is not None)
        worker = threading.Thread(target=open_when_ready, args=(url, stopped, args.no_browser), daemon=True)
        worker.start()
        bootstrap.run(str(script), False, [], options)
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as error:
        # Do not persist exception contents, environment values or schematic data.
        LOG.error('Startup failed (%s).', type(error).__name__)
        print(f'Application startup failed ({type(error).__name__}). See the application data logs/launcher.log.', flush=True)
        return 1
    finally:
        stopped.set()
        if worker:
            worker.join(timeout=2)
        LOG.info('Launcher stopped.')
        if handler:
            LOG.removeHandler(handler)
            handler.close()


if __name__ == '__main__':
    raise SystemExit(main())
