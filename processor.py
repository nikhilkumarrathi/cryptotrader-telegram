import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import schedule
from dotmap import DotMap

import commands as cm
from access import accessControl
import log

# Remember to only use single threaded, as we are using global variable for telegram chat_id
executor = ThreadPoolExecutor(max_workers=3)


def run_scheduler():
    threading.current_thread().setName("Scheduler")
    while True:
        schedule.run_pending()
        time.sleep(1)


schedulerExecutor = ThreadPoolExecutor(max_workers=1)
schedulerExecutor.submit(run_scheduler)


def done(fn):
    if fn.cancelled():
        log.warn('{}: cancelled'.format(fn.arg))
    elif fn.done():
        error = fn.exception()
        if error:
            log.error('error returned: {}'.format(error))


def process_message(message: DotMap, use_executor=True):
    text, author = message.text, message.chat.username
    log.debug("To Processor: message: %s ", message.toDict())
    text = re.sub('\s+', ' ', text).strip()
    # command: /<command> [params...]
    command_n_args = text[1:].split(" ")
    curr_command = command_n_args[0].lower()
    params = list(map(lambda x: x.strip(), command_n_args[1:]))

    task = DotMap({'message': message, 'params': params, 'command': curr_command})

    if curr_command in cm.commands:
        access_list = cm.accessManagement[curr_command] if curr_command in cm.accessManagement else []
        access_granted = (author.lower() in access_list or author.lower() == accessControl.adminName)

        if not access_granted:
            message.text = '/' + cm.accessdenied + ' ' + message.text
            task.params = [curr_command] + params
            curr_command = cm.accessdenied

        command_fn = cm.commands[curr_command]

        log.info('submitting task: %s %s', task.command, task.params)
        if use_executor:
            future = executor.submit(command_fn, task)
            future.add_done_callback(done)
        else:
            command_fn(task)

    else:
        log.error(f'command "{curr_command}" not found"')
