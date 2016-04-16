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

import os
import requests
import uuid

from celery import Celery

from stackviz_deployer.db import database
from stackviz_deployer.db.models import ScrapeTask
from stackviz_deployer.scraper import artifacts_list
from stackviz_deployer.tasks import subunit_artifacts


# connection settings for redis (as needed by celery), using docker-style ENV
# when available
REDIS_HOST = os.environ.get('REDIS_PORT_6379_TCP_ADDR', 'localhost')
REDIS_PORT = os.environ.get('REDIS_PORT_6379_TCP_PORT', '6379')

app = Celery('tasks', broker='redis://{}:{}/0'.format(REDIS_HOST, REDIS_PORT))
app.conf.CELERY_TASK_SERIALIZER = 'json'
app.conf.CELERY_RESULT_SERIALIZER = 'json'

# a list of all available scanner functions (to be extended later)
SCANNER_FUNCTIONS = subunit_artifacts.SCANNER_FUNCTIONS

# TODO: should also have a list of validator functions (of which >= 1 must
# return True)


@app.task
def request_scrape(task_id):
    task_id = uuid.UUID(task_id)
    db_task = database.session.query(ScrapeTask).filter_by(id=task_id).first()
    if not db_task:
        # shouldn't happen...
        return

    # TODO validate input (check url, etc...)

    # mark the task as pending so clients can see some degree of feedback
    db_task.status = 'pending'
    database.session.add(db_task)
    database.session.commit()

    try:
        artifacts = artifacts_list.DirectoryListing(db_task.url)

        # all blobs found by the crawler
        found_blobs = []

        # run all scanner functions to scrape this directory listing
        for func in SCANNER_FUNCTIONS:
            found_blobs.extend(func(artifacts))

        # of found_blobs, the # that are actually useful as standalone data
        # (e.g., if we only find dstat, we should error regardless since that
        # is uninteresting by itself)
        primary_blob_count = sum(map(lambda b: 1 if b.primary else 0,
                                     found_blobs))

        # make sure we found at least 1 primary artifact, otherwise fail the
        # job (i.e. 'nothing to see here' error)
        if primary_blob_count > 0:
            for blob in found_blobs:
                blob.task_id = db_task.id
                database.session.add(blob)
        else:
            db_task.status = 'error'
            db_task.message = 'no supported artifacts could be found'
    except Exception as e:
        print e
        db_task.status = 'error'
        db_task.message = str(e)

    if db_task.status != 'error':
        db_task.status = 'finished'

    database.session.add(db_task)
    database.session.commit()
