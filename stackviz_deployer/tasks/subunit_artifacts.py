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

import datetime
import gzip
import json
import uuid

import requests

from StringIO import StringIO

from stackviz_deployer.db.models import ArtifactBlob
from stackviz_deployer.parser import subunit_parser


# the maximum allowed size for a subunit artifact that we will download
SUBUNIT_MAX_SIZE = 1024 * 1024 * 32  # 20 MiB


class ScrapeError(Exception):
    pass


def json_date_handler(o):
    if isinstance(o, (datetime.datetime, datetime.date)):
        return o.isoformat()

    return None


def collect_subunit(artifact):
    r = requests.get(artifact.abs_url())
    if int(r.headers.get('content-length')) > SUBUNIT_MAX_SIZE:
        raise ScrapeError('Subunit artifact too large.')

    subunit_content = StringIO(r.content)
    if r.headers.get('content-type') == 'application/x-gzip':
        with gzip.GzipFile(fileobj=subunit_content, mode='rb') as f:
            subunit_content = StringIO(f.read())

    data = subunit_parser.convert_stream(subunit_content,
                                         strip_details=True)
    compressed = StringIO()
    with gzip.GzipFile(fileobj=compressed, mode='wb') as f:
        json.dump(data, f, default=json_date_handler)

    compressed.seek(0)

    return ArtifactBlob(id=uuid.uuid4(),
                        artifact_name=artifact.name,
                        artifact_type='subunit',
                        content_type='application/json',
                        content_encoding='gzip',
                        data=compressed.read()), data


def collect_subunit_stats(artifact, raw_data):
    start = None
    end = None
    total_duration = 0
    failures = []
    skips = []

    for entry in raw_data:
        # find min/max dates
        entry_start, entry_end = entry['timestamps']
        if start is None or entry_start < start:
            start = entry_start

        if end is None or entry_end > end:
            end = entry_end

        total_duration += entry['duration']

        # find details for unsuccessful tests (fail or skip)
        if entry['status'] == 'fail':
            # if available, the error message will be the last non-empty line
            # of the traceback
            msg = None
            if 'traceback' in entry['details']:
                msg = entry['details']['traceback'].strip().splitlines()[-2:]
                if 'Details' not in msg[1]:
                    msg.remove(msg[0])

            failures.append({
                'name': entry['name'],
                'duration': entry['duration'],
                'details': msg
            })
        elif entry['status'] == 'skip':
            skips.append({
                'name': entry['name'],
                'duration': entry['duration'],
                'details': entry['details'].get('reason')
            })

    data = {
        'count': len(raw_data),
        'start': start,
        'end': end,
        'total_duration': total_duration,
        'failures': failures,
        'skips': skips
    }

    compressed = StringIO()
    with gzip.GzipFile(fileobj=compressed, mode='wb') as f:
        json.dump(data, f, default=json_date_handler)

    compressed.seek(0)

    return ArtifactBlob(id=uuid.uuid4(),
                        artifact_name=artifact.name,
                        artifact_type='subunit-stats',
                        content_type='application/json',
                        content_encoding='gzip',
                        data=compressed.read())


def collect_dstat(artifact):
    r = requests.get(artifact.abs_url(), stream=True)

    # reuse pre-gzipped data if possible
    if r.headers.get('content-encoding') == 'gzip':
        compressed = r.raw
    else:
        compressed = StringIO()
        with gzip.GzipFile(fileobj=compressed, mode='wb') as f:
            for chunk in r.iter_content():
                f.write(chunk)
        compressed.seek(0)

    return ArtifactBlob(id=uuid.uuid4(),
                        artifact_name=artifact.name,
                        artifact_type='dstat',
                        content_type='text/csv',
                        content_encoding='gzip',
                        data=compressed.read())


def scan_subunit(listing):
    dirs = [listing]
    if listing.has_directory('logs'):
        # if a 'logs' dir exists, scan it too
        dirs.append(listing.get_directory('logs').browse())

    found = []
    primary = 0

    for d in dirs:
        for artifact in d.get_files_glob('*.subunit', '*.subunit.gz'):
            blob, raw = collect_subunit(artifact)
            found.append(blob)
            primary += 1

            blob = collect_subunit_stats(artifact, raw)
            found.append(blob)

    return found, primary


def scan_dstat(listing):
    dirs = [listing]
    if listing.has_directory('logs'):
        # if a 'logs' dir exists, scan it too
        dirs.append(listing.get_directory('logs').browse())

    found = []
    for d in dirs:
        artifact = d.get_file('dstat-csv.txt', 'dstat-csv.txt.gz')
        if artifact:
            found.append(collect_dstat(artifact))

    # dstat is never a primary artifact, so always return [found], 0
    return found, 0


SCANNER_FUNCTIONS = [
    scan_subunit,
    scan_dstat
]
