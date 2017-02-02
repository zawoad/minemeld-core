#  Copyright 2015-2016 Palo Alto Networks, Inc
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import re

import libtaxii
import libtaxii.messages_11
import libtaxii.constants

from flask import request
from flask.ext.login import current_user

from . import config
from .taxiiutils import get_taxii_feeds, taxii_check, taxii_make_response
from .aaa import MMBlueprint
from .logger import LOG


__all__ = ['BLUEPRINT']


BLUEPRINT = MMBlueprint('taxiidiscovery', __name__, url_prefix='')

HOST_RE = re.compile('^[a-zA-Z\d-]{1,63}(?:\.[a-zA-Z\d-]{1,63})*(?::[0-9]{1,5})*$')

_SERVICE_INSTANCES = [
    {
        'type': libtaxii.constants.SVC_DISCOVERY,
        'path': 'taxii-discovery-service'
    },
    {
        'type': libtaxii.constants.SVC_COLLECTION_MANAGEMENT,
        'path': 'taxii-collection-management-service'
    },
    {
        'type': libtaxii.constants.SVC_POLL,
        'path': 'taxii-poll-service'
    }
]


@BLUEPRINT.route('/taxii-discovery-service', methods=['POST'], feeds=True, read_write=False)
@taxii_check
def taxii_discovery_service():
    taxii_feeds = get_taxii_feeds()
    authorized = next(
        (tf for tf in taxii_feeds if current_user.check_feed(tf)),
        None
    )
    if authorized is None:
        return 'Unauthorized', 401

    server_host = config.get('TAXII_HOST', None)
    if server_host is None:
        server_host = request.headers.get('Host', None)
        if server_host is None:
            return 'Missing Host header', 400

        if HOST_RE.match(server_host) is None:
            return 'Invalid Host header', 400

    tm = libtaxii.messages_11.get_message_from_xml(request.data)
    if tm.message_type != libtaxii.constants.MSG_DISCOVERY_REQUEST:
        return 'Invalid message, invalid Message Type', 400

    dresp = libtaxii.messages_11.DiscoveryResponse(
        libtaxii.messages_11.generate_message_id(),
        tm.message_id
    )

    for si in _SERVICE_INSTANCES:
        sii = libtaxii.messages_11.ServiceInstance(
            si['type'],
            'urn:taxii.mitre.org:services:1.1',
            'urn:taxii.mitre.org:protocol:http:1.0',
            "https://{}/{}".format(server_host, si['path']),
            ['urn:taxii.mitre.org:message:xml:1.1'],
            available=True
        )
        dresp.service_instances.append(sii)

    return taxii_make_response(dresp)
