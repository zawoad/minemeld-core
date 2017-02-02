#  Copyright 2015 Palo Alto Networks, Inc
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

from __future__ import absolute_import

import logging
import os
import yaml
import netaddr
import netaddr.core
import pan.afapi
import ujson
import re

from . import basepoller

LOG = logging.getLogger(__name__)

DOMAIN_RE = re.compile('^[a-zA-Z\d-]{,63}(\.[a-zA-Z\d-]{,63})*$')


class ExportList(basepoller.BasePollerFT):
    def configure(self):
        super(ExportList, self).configure()

        self.api_key = None
        self.label = None

        self.hostname = self.config.get('autofocus_hostname', None)
        self.verify_cert = self.config.get('verify_cert', None)

        self.side_config_path = self.config.get('side_config', None)
        if self.side_config_path is None:
            self.side_config_path = os.path.join(
                os.environ['MM_CONFIG_DIR'],
                '%s_side_config.yml' % self.name
            )

        self._load_side_config()

    def _load_side_config(self):
        try:
            with open(self.side_config_path, 'r') as f:
                sconfig = yaml.safe_load(f)

        except Exception as e:
            LOG.error('%s - Error loading side config: %s', self.name, str(e))
            return

        self.api_key = sconfig.get('api_key', None)
        if self.api_key is not None:
            LOG.info('%s - api key set', self.name)

        self.label = sconfig.get('label', None)

    def _process_item(self, row):
        indicator = row

        result = {}
        result['type'] = self._type_of_indicator(indicator)
        result['autofocus_label'] = self.label

        return [[indicator, result]]

    def _check_for_ip(self, indicator):
        if '-' in indicator:
            # check for address range
            a1, a2 = indicator.split('-', 1)

            try:
                a1 = netaddr.IPAddress(a1)
                a2 = netaddr.IPAddress(a2)

                if a1.version == a2.version:
                    if a1.version == 6:
                        return 'IPv6'
                    if a1.version == 4:
                        return 'IPv4'

            except:
                return None

            return None

        if '/' in indicator:
            # check for network
            try:
                ip = netaddr.IPNetwork(indicator)

            except:
                return None

            if ip.version == 4:
                return 'IPv4'
            if ip.version == 6:
                return 'IPv6'

            return None

        try:
            ip = netaddr.IPAddress(indicator)
        except:
            return None

        if ip.version == 4:
            return 'IPv4'
        if ip.version == 6:
            return 'IPv6'

        return None

    def _type_of_indicator(self, indicator):
        ipversion = self._check_for_ip(indicator)
        if ipversion is not None:
            return ipversion

        if DOMAIN_RE.match(indicator):
            return 'domain'

        return 'URL'

    def _build_iterator(self, now):
        if self.api_key is None or self.label is None:
            raise RuntimeError(
                '%s - api_key or label not set, poll not performed' % self.name
            )

        body = {
            'label': self.label,
            'panosFormatted': True
        }

        af = pan.afapi.PanAFapi(
            hostname=self.hostname,
            verify_cert=self.verify_cert,
            api_key=self.api_key
        )

        r = af.export(data=ujson.dumps(body))
        r.raise_for_status()

        return r.json.get('export_list', [])

    def hup(self, source=None):
        LOG.info('%s - hup received, reload side config', self.name)
        self._load_side_config()
        super(ExportList, self).hup(source=source)

    @staticmethod
    def gc(name, config=None):
        basepoller.BasePollerFT.gc(name, config=config)

        side_config_path = None
        if config is not None:
            side_config_path = config.get('side_config', None)
        if side_config_path is None:
            side_config_path = os.path.join(
                os.environ['MM_CONFIG_DIR'],
                '{}_side_config.yml'.format(name)
            )

        try:
            os.remove(side_config_path)
        except:
            pass
