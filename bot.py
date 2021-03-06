import threading
import time
from time import sleep

from dotmap import DotMap

import commands as cm
import log
import processor
from db import Const
from db import db
from lib import app
from access import accessControl
import sys


def telegram_poller():
    """ 
    - continuously listen to the messages on the telegram chat
    - create tasks for the messages
    - submit to the thread pool
    - wait 3 seconds and re-do the same
    """
    threading.current_thread().setName("Telegram")
    try:
        log.info("Starting Telegram Poller")
        while True:
            last_updated_id = db.config(Const.TELEGRAM_UPDATE_ID)
            msgs = app.get_messages(last_updated_id, timeout=15)

            for message in msgs:
                current_time = int(time.time())
                message.source = "telegram"

                # Don't process Old messages
                last_updated_id = message.update_id
                if not message['text'] or message.date and message.date < (current_time - 11):
                    log.info('discarding: %s ', message)
                    db.set_config(Const.TELEGRAM_UPDATE_ID, last_updated_id + 1)
                    continue

                db.set_config(Const.TELEGRAM_UPDATE_ID, last_updated_id + 1)
                processor.process_message(message)

    except Exception as e1:
        log.exception(e1)
        app.send_msg("Error occured !", accessControl.adminChatId)


# Add the poller to Executer 
processor.executor.submit(telegram_poller)

default_commands = [
    "symboladd ada trx ltc xlm icx eth",
    "hot 1d 7 10",
    "schd "+str(60*60*6)+" hot 1d 7 10", #every 6 hours
    "schd "+str(60*30)+" macd all 4h 1000",
    "schdinfo"
]


def process_shell_command(text):
    if text == 'help':
        log.info('-' * 30)
        for x in cm.commands:
            log.info(x)
        log.info('-' * 30)
    else:
        if len(text.strip()) > 0:
            local_message = DotMap()
            local_message.chat.id = accessControl.adminChatId
            local_message.text = "/" + text
            local_message.chat.username = accessControl.adminUserId
            local_message.source = "terminal"
            processor.process_message(local_message, use_executor=True)


# Poll Local messages
try:
    log.info("running default commands")
    for x in default_commands:
        process_shell_command(x)

    if sys.stdin.isatty():
        print("reading from Terminal:")
        while True:
            inp = input("\n")
            process_shell_command(inp)
    else:
        sleep(999999999) # dumb way to sleep so long
except Exception as e:
    log.exception(e)
