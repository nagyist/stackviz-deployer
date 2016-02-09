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
import requests
import uuid

from StringIO import StringIO
from urlparse import urlparse

from celery import Celery

from stackviz_deployer.db import database
from stackviz_deployer.db.models import ScrapeTask, ArtifactBlob
from stackviz_deployer.parser import subunit_parser
from stackviz_deployer.scraper import url_matcher, artifacts_list


ARTIFACT_MAX_SIZE = 1024 * 1024 * 32  # 20 MiB

app = Celery('tasks', broker='redis://localhost:6379/0')
app.conf.CELERY_TASK_SERIALIZER = 'json'
app.conf.CELERY_RESULT_SERIALIZER = 'json'


class ScrapeError(Exception):
    pass


def json_date_handler(o):
    if isinstance(o, (datetime.datetime, datetime.date)):
        return o.isoformat()

    return None


def collect_subunit(artifact):
    r = requests.get(artifact.abs_url())
    if int(r.headers.get('content-length')) > ARTIFACT_MAX_SIZE:
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
                        artifact_type='subunit',
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
                        artifact_type='dstat',
                        content_type='text/csv',
                        content_encoding='gzip',
                        data=compressed.read())


@app.task
def request_scrape(task_id):
    task_id = uuid.UUID(task_id)
    db_task = database.session.query(ScrapeTask).filter_by(id=task_id).first()
    if not db_task:
        # shouldn't happen...
        return

    # TODO validate input (check url, etc...)

    db_task.status = 'pending'
    database.session.add(db_task)
    database.session.commit()

    try:
        artifacts = artifacts_list.DirectoryListing(db_task.url)
        if artifacts.has_directory('logs'):
            # if a 'logs' dir exists, scan it instead
            artifacts = artifacts.get_directory('logs').browse()

        artifact = artifacts.get_file('testrepository.subunit',
                                      'testrepository.subunit.gz')
        if artifact:
            blob = collect_subunit(artifact)
            blob.task_id = db_task.id
            database.session.add(blob)

        artifact = artifacts.get_file('dstat-csv.txt', 'dstat-csv.txt.gz')
        if artifact:
            blob = collect_dstat(artifact)
            blob.task_id = db_task.id
            database.session.add(blob)
    except (ScrapeError, requests.HTTPError) as e:
        print e
        db_task.status = 'error'

    db_task.status = 'finished'
    database.session.commit()
