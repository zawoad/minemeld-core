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
from .taxiiutils import taxii_check, taxii_make_response, get_taxii_feeds
from .aaa import MMBlueprint
from .logger import LOG


__all__ = ['BLUEPRINT']


HOST_RE = re.compile('^[a-zA-Z\d-]{1,63}(?:\.[a-zA-Z\d-]{1,63})*(?::[0-9]{1,5})*$')

BLUEPRINT = MMBlueprint('taxiicollmgmt', __name__, url_prefix='')


@BLUEPRINT.route('/taxii-collection-management-service', methods=['POST'], feeds=True, read_write=False)
@taxii_check
def taxii_collection_mgmt_service():
    taxii_feeds = get_taxii_feeds()
    authorized_feeds = filter(
        current_user.check_feed,
        taxii_feeds
    )
    if len(authorized_feeds) == 0:
        return 'Unauthorized', 401

    server_host = config.get('TAXII_HOST', None)
    if server_host is None:
        server_host = request.headers.get('Host', None)
        if server_host is None:
            return 'Missing Host header', 400

        if HOST_RE.match(server_host) is None:
            return 'Invalid Host header', 400

    tm = libtaxii.messages_11.get_message_from_xml(request.data)
    if tm.message_type != \
       libtaxii.constants.MSG_COLLECTION_INFORMATION_REQUEST:
        return 'Invalid message, invalid Message Type', 400

    cir = libtaxii.messages_11.CollectionInformationResponse(
        libtaxii.messages_11.generate_message_id(),
        tm.message_id
    )

    for feed in authorized_feeds:
        cii = libtaxii.messages_11.CollectionInformation(
            feed,
            '{} Data Feed'.format(feed),
            ['urn:stix.mitre.org:xml:1.1.1'],
            True
        )
        si = libtaxii.messages_11.PollingServiceInstance(
            'urn:taxii.mitre.org:protocol:http:1.0',
            'https://{}/taxii-poll-service'.format(server_host),
            ['urn:taxii.mitre.org:message:xml:1.1']
        )
        cii.polling_service_instances.append(si)
        cir.collection_informations.append(cii)

    return taxii_make_response(cir)
