import asyncio
import logging
import sys

from pokesim.runtime.worker import ShutdownCancelFilter


def record(error):
    try:
        raise error
    except BaseException:
        info = sys.exc_info()
    return logging.LogRecord('uvicorn.error', logging.ERROR, __file__, 1,
                             'Exception in ASGI application\n', None, info)


def test_cancelled_streams_are_quiet_while_the_game_stops():
    assert not ShutdownCancelFilter(lambda: True).filter(record(asyncio.CancelledError()))


def test_cancellations_still_show_while_the_game_runs():
    assert ShutdownCancelFilter(lambda: False).filter(record(asyncio.CancelledError()))


def test_real_errors_still_show_while_the_game_stops():
    assert ShutdownCancelFilter(lambda: True).filter(record(ValueError('broken')))


def test_plain_messages_pass():
    message = logging.LogRecord('uvicorn.error', logging.ERROR, __file__, 1, 'Cancel 1 running task(s)', None, None)
    assert ShutdownCancelFilter(lambda: True).filter(message)
