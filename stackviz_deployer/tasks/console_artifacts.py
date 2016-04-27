# Copyright 2016 Hewlett-Packard Development Company, L.P.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import gzip
import json
import uuid

import requests

from bs4 import BeautifulSoup
from StringIO import StringIO

from stackviz_deployer.db.models import ArtifactBlob
from stackviz_deployer.parser import console_parser

# the maximum allowed size for a console artifact that we will download
CONSOLE_MAX_SIZE = 1024 * 1024 * 20  # 20 MiB


class ConsoleScrapeError(Exception):
    pass


def collect_console(artifact):
    r = requests.get(artifact.abs_url())
    if 'content-length' in r.headers:
        if int(r.headers.get('content-length')) > CONSOLE_MAX_SIZE:
            raise ConsoleScrapeError('Console artifact too large.')

    soup = BeautifulSoup(r.text, 'lxml')
    element = soup.select('pre')
    if not element:
        raise ConsoleScrapeError('Could not find console output in artifact')

    data = console_parser.parse_console(element[0].text)

    compressed = StringIO()
    with gzip.GzipFile(fileobj=compressed, mode='wb') as f:
        json.dump(data, f)

    compressed.seek(0)

    return ArtifactBlob(id=uuid.uuid4(),
                        artifact_name=artifact.name,
                        artifact_type='console',
                        content_type='application/json',
                        content_encoding='gzip',
                        primary=True,
                        data=compressed.read())


def scan_console(listing):
    artifact = listing.get_file('console.html', 'console.html.gz')
    if artifact:
        return [collect_console(artifact)]

    return None


SCANNER_FUNCTIONS = [
    scan_console
]