import os
import sys
import time

from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler


class ICloudIgnoreUtility:
    def __init__(self, BASE_DIR):
        self.BASE_DIR = BASE_DIR
        self.ignore_list = ['node_modules', 'site-packages',  '.pub-cache', 'build']
        self.last_ignored_timestamp = 0
        self.last_ignored_filename = None
        self.running = False
        self.stale = False
        self.cached_event = None

    def log(self, message: str):
        print('[{}] {}'.format(datetime.now().strftime('%m-%d-%Y %I:%M:%S %p'), message), flush=True)

    def ignore(self, f: str):
        os.rename(f, f'{f}.nosync')
        os.symlink(f'{f}.nosync', f)
        self.last_ignored_timestamp = time.monotonic()
        self.last_ignored_filename = f

    def should_ignore(self, d: str) -> bool:
        return any(map(lambda s: s in d, self.ignore_list))

    def is_ignored(self, path: str) -> bool:
        return '.nosync' in path or os.path.islink(path)

    def is_self_generated_event(self, event) -> bool:
        src = event.src_path
        dst = getattr(event, 'dst_path', None)

        if abs(time.monotonic() - self.last_ignored_timestamp) < 1:
            src_match = self.last_ignored_filename in src or src in self.last_ignored_filename
            dst_match = dst and (self.last_ignored_filename in dst or dst in self.last_ignored_filename)
            if src_match or dst_match:
                return True

        return False

    def ignore_matching(self, event):
        if event:
            self.log(f'File system change detected: {event}')
            if self.running:
                self.log('File system walk already in progress')
                self.log(f'Marking as stale and delaying event: {event}')
                self.stale = True
                self.cached_event = event
                return

            if self.is_self_generated_event(event):
                self.log(f'Ignoring self-generated event: {event}')
                return

        self.running = True
        self.log(f'Walking file system')

        for dir_path, dirs, _ in os.walk(self.BASE_DIR):
            if self.should_ignore(dir_path):
                self.log(f'Skipping {dir_path} walk as top-level directory is or will be ignored')
                continue

            self.log(f'Walking {dir_path}')
            
            for d in dirs:
                path = os.path.join(dir_path, d)
                self.log(f'Testing directory {path}')
                if not self.is_ignored(path) and self.should_ignore(d):
                    self.log(f'Ignoring {path}')
                    self.ignore(path)

        self.running = False

        if self.stale:
            self.log('File system is stale')
            self.log(f'Firing last delayed event: {self.cached_event}')
            self.stale = False
            self.ignore_matching(self.cached_event)

    def watch(self):
        self.log(f'File system: {self.BASE_DIR}')
        self.log('Performing initial file system check')
        self.ignore_matching(None)

        event_handler = PatternMatchingEventHandler(['*'], case_sensitive=True)
        event_handler.on_created = event_handler.on_modified = event_handler.on_moved = self.ignore_matching

        watcher = Observer()
        watcher.schedule(event_handler, self.BASE_DIR, recursive=True)
        watcher.start()
        self.log('Watching file system')

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.log('Terminating watcher\n')
            self.log('{}\n'.format('=' * 50))
            watcher.stop()
            watcher.join()

if __name__ == '__main__':
    watcher =  ICloudIgnoreUtility(os.path.abspath(os.path.expandvars(os.path.expanduser(sys.argv[1]))))
    watcher.watch()
