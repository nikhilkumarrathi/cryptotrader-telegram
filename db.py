from threading import Lock

from tinydb import TinyDB, where

import log
import threading
import time
# https://tinydb.readthedocs.io/en/v1.3.0/api.html#module-tinydb.queries
# https://tinydb.readthedocs.io/en/v1.3.0/usage.html


class Const:
    SNAPSHOT = "snapshot"
    TELEGRAM_UPDATE_ID = 'telegram_update_id'
    SYMBOLS = 'symbols'
    BALANCE = 'balance'
    BALANCE_HASH = 'balance_hash'


k = 'k'
v = 'v'


def get_lock_wrapper(lock: Lock, name):
    def locked(fn):
        def wrapped(*args):
            # log.debug("Running method with lock: %s",name)
            try:
                start = time.time()
                lock.acquire()
                end = time.time()
                # log.debug("acquired lock in %f ms", (end*1000-start*1000))
                return fn(*args)
            finally:
                lock.release()
        return wrapped
    return locked


dblock = get_lock_wrapper(threading.Lock(), "db")
orderlock = get_lock_wrapper(threading.Lock(), "order")


class DB:
    def __init__(self):
        self.db = TinyDB('db/db.json')
        self.statusTable = self.db.table("status")
        self.configTable = self.db.table("config")
        self.accountTable = self.db.table("account")
        self.setup()
        log.info("Setup done for DB")

    def setup(self):
        if not self.statusTable.contains(where(k) == Const.TELEGRAM_UPDATE_ID):
            self.statusTable.insert({k: Const.TELEGRAM_UPDATE_ID, v: 1})

    @dblock
    def config(self, key, default=None):
        data = self.statusTable.get(where(k) == key)

        if not data and default is not None:
            data = {k: key, v: default}
            self.statusTable.insert(data)

        return data[v] if data and v in data else default

    @dblock
    def set_config(self, key, value):
        if self.statusTable.contains(where(k) == key):
            self.statusTable.update({v: value}, where(k) == key)
        else:
            self.statusTable.insert({k: key, v: value})


db = DB()
