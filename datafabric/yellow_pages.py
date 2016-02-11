import itertools
import os

from distributed import sync

class YellowPages(object):
    class Block(object):
        def __init__(self, capacity):
            self.capacity = capacity
            self.size = 0
            self.variables = {}

    def __init__(self, executor):
        self._executor = executor
        self._blocks = {} # this is a dict of IP addresses and blocks

    def __del__(self):
        def func(blocks):
            import posix_ipc

            for name in blocks:
                sm = posix_ipc.SharedMemory(name)
                sm.close_fd()
                sm.unlink()

        for ip in self._blocks:
            self._executor.submit(func, self._blocks[ip], workers = (ip,))

        self._blocks.clear()

    def __getitem__(self, name):
        return self._blocks[name]

    def blocks(self):
        res = []
        for ip, block in self._blocks.items():
            for name in block:
                res.append((ip, name))

        return res

    def allocate(self, names, size):
        def func(name, size):
            import posix_ipc

            sm = posix_ipc.SharedMemory(name, flags = posix_ipc.O_CREAT | posix_ipc.O_EXCL, size = size)
            sm.close_fd()

            return YellowPages.Block(size)

        futures = self._executor.map(func, names, itertools.repeat(size, len(names)))
        self._executor.gather(futures)

        s = sync(self._executor.loop, self._executor.scheduler.who_has)
        for name, future in zip(names, futures):
            ip = itertools.chain(*s[future.key]).next()
            try:
                block = self._blocks[ip]
            except KeyError:
                block = {}
                self._blocks[ip] = block

            block[name] = future.result()

    def insert(self, name, size):
        for blocks in self._blocks.values():
            for block in blocks.values():
                if block.size + size <= block.capacity:
                    block.size += size
                    block.variables[name] = size

    def remove(self, name):
        pass

    def nodes(self):
        return self._blocks

    def read(self):
        pass
