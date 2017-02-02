import sys
import os
import logging
import time

import redis
import ujson
from supervisor import childutils

LOG = logging.getLogger(__name__)


def _handle_event(SR, engine_process_name, hdrs, payload):
    event = hdrs.get('eventname', None)
    if not event.startswith('PROCESS_STATE'):
        return
    event = event.split('_', 2)[-1]

    processname = None
    pkvs = payload.split()
    for pkv in pkvs:
        pkey, pvalue = pkv.split(':', 1)
        if pkey == 'processname':
            processname = pvalue
            break
    else:
        LOG.error('processname key not found in payload')
        return

    if processname != engine_process_name:
        return

    SR.publish(
        'mm-engine-status.<minemeld-engine>',
        ujson.dumps({
            'source': '<minemeld-engine>',
            'timestamp': int(time.time())*1000,
            'status': event
        })
    )


def main():
    logging.basicConfig(level=logging.DEBUG)

    engine_process_name = os.environ.get('MM_ENGINE_PROCESSNAME', 'minemeld-engine')

    SR = redis.StrictRedis.from_url(
        os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0')
    )

    while True:
        hdrs, payload = childutils.listener.wait(sys.stdin, sys.stdout)
        LOG.info('hdr: {!r} payload: {!r}'.format(hdrs, payload))

        try:
            _handle_event(SR, engine_process_name, hdrs, payload)

        except:
            LOG.exception('Exception in handling event')

        finally:
            childutils.listener.ok(sys.stdout)
