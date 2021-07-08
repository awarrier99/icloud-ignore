import os
import sys
import time
import queue

from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import RegexMatchingEventHandler


class ICloudIgnoreUtility:
    def __init__(self, BASE_DIR):
        self.BASE_DIR = BASE_DIR
        self.ignore_list = ['node_modules', 'site-packages',  '.pub-cache', 'build']
        self.last_ignored_timestamp = 0
        self.last_ignored_filename = None
        self.running = False
        self.event_queue = queue.Queue()

    def log(self, message: str):
        print('[{}] {}'.format(datetime.now().strftime('%m-%d-%Y %I:%M:%S %p'), message), flush=True)

    def ignore(self, path: str):
        os.rename(path, f'{path}.nosync')
        os.symlink(f'{path}.nosync', path)

    def should_ignore(self, path: str) -> bool:
        path_segments = path.split('/')
        return any(map(lambda s: s in self.ignore_list, path_segments))

    def is_ignored(self, path: str) -> bool:
        return '.nosync' in path or os.path.islink(path)

    def process_event(self, event):
        self.log(f'File system change detected: {event}')
        
        if self.running:
            self.log('File system walk already in progress')
            self.log('Queueing event')
            self.event_queue.put(event)
            return

        self.ignore_event_target(event)
        
    def ignore_event_target(self, event):
        target = event.src_path

        if abs(time.time() - os.stat(target).st_mtime) < 10:
            self.log(f'Waiting for {target} to be stale for at least 10 seconds')

            while abs(time.time() - os.stat(target).st_mtime) < 10:
                time.sleep(1)

        self.log(f'Handling event: {event}')

        parent = os.path.abspath(os.path.join(target, os.pardir))
        if self.should_ignore(parent):
            self.log(f'Skipping {target} as ancestor directory is ignored')
            return

        if self.is_ignored(target):
            self.log(f'Skipping {target} as it is already ignored')
            return
        
        if self.should_ignore(target):
            self.log(f'Ignoring {target}')
            self.ignore(target)

    def ignore_matching(self):
        self.running = True
        self.log(f'Walking file system')

        for dir_path, dirs, _ in os.walk(self.BASE_DIR):
            if self.should_ignore(dir_path):
                self.log(f'Skipping {dir_path} walk as ancestor directory is ignored')
                continue

            self.log(f'Walking {dir_path}')
            
            for d in dirs:
                path = os.path.join(dir_path, d)
                self.log(f'Testing directory {path}')
                if self.is_ignored(path):
                    self.log(f'Skipping {path} as it is already ignored')
                    continue

                if self.should_ignore(d):
                    self.log(f'Ignoring {path}')
                    self.ignore(path)

        self.running = False
        if not self.event_queue.empty():
            self.log('Dequeuing and handling events')
            
            while not self.event_queue.empty():
                self.ignore_event_target(self.event_queue.get())

    def watch(self):
        self.log(f'File system: {self.BASE_DIR}')

        regexes = list(map(lambda i: f'^.*{i}$', self.ignore_list))
        ignore_regexes = list(map(lambda i: f'^.*{i}.+$', self.ignore_list))
        event_handler = RegexMatchingEventHandler(regexes=regexes, ignore_regexes=ignore_regexes)
        event_handler.on_created = self.process_event

        watcher = Observer()
        watcher.schedule(event_handler, self.BASE_DIR, recursive=True)
        watcher.start()
        self.log('Watching file system')

        self.log('Performing initial file system check')
        self.ignore_matching()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.log('Terminating watcher\n')
            self.log('{}\n'.format('=' * 50))
            watcher.stop()
            watcher.join()

if __name__ == '__main__':
    watcher = ICloudIgnoreUtility(sys.argv[1])
    watcher.watch()
