import logging

import coloredlogs
import argparse
import functools

log = logging.getLogger("main")
exception = log.exception
info = log.info
debug = log.debug
error = log.error
warn = log.warning


def get_arg(arg):
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--log", help="log help", default="INFO")
        args = parser.parse_args()
        return vars(args)[arg]
    except:
        return "INFO"


def setup(level="INFO"):
    print("setting logging with level: ", level)
    log.setLevel(level)
    logging.getLogger().setLevel(logging.ERROR)
    coloredlogs.install(
        level=level,
        fmt="%(asctime)s %(threadName)s %(levelname)s %(message)s",
        logger=log,
    )


setup(get_arg("log"))
