# k-cube-daemon/core/watcher.py
from PyQt6.QtCore import QObject, pyqtSignal, QThread
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time


class _ChangeHandler(FileSystemEventHandler):
    def __init__(self, changed_signal: pyqtSignal):
        super().__init__()
        self.changed_signal = changed_signal

    def on_any_event(self, event):
        if ".kcube" in event.src_path or event.is_directory:
            return
        self.changed_signal.emit()


class WatcherThread(QThread):
    file_changed = pyqtSignal()

    def __init__(self, path_to_watch: str):
        super().__init__()
        self.path = path_to_watch
        self._is_running = False

    def run(self):
        self._is_running = True
        # 在线程内部创建 Observer
        observer = Observer()
        event_handler = _ChangeHandler(self.file_changed)
        observer.schedule(event_handler, self.path, recursive=True)
        observer.start()

        while self._is_running:
            time.sleep(0.5)

        observer.stop()
        observer.join()

    def stop(self):
        self._is_running = False
