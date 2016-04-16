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

import uuid

from flask import Flask, jsonify, request

from stackviz_deployer.db import database
from stackviz_deployer.db.models import ScrapeTask, ArtifactBlob
from stackviz_deployer.scraper import url_matcher
from stackviz_deployer.tasks import tasks

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 8192

database.init_db()


@app.route('/scrape', methods=['POST'])
def request_scrape():
    # TODO check for existing scrapes & validate input
    listing_info = request.get_json()

    task_id = uuid.uuid4()
    db_task = ScrapeTask(id=task_id,
                         status='new',
                         url=listing_info['url'],
                         change_id=listing_info.get('change_id'),
                         change_rev=listing_info.get('revision'),
                         change_job=listing_info.get('name'),
                         change_project=listing_info.get('change_project'),
                         change_subject=listing_info.get('change_subject'),
                         change_status=listing_info.get('status'),
                         change_ci_username=listing_info.get('ci_username'),
                         change_ci_pipeline=listing_info.get('pipeline'))

    database.session.add(db_task)
    database.session.commit()

    tasks.request_scrape.delay(str(task_id))

    return jsonify({
        'status': 'queued',
        'uuid': task_id
    }), 202


@app.route('/status', methods=['POST'])
def request_status():
    json = request.get_json()

    task_id = uuid.UUID(json['q'])
    db_task = database.session.query(ScrapeTask).filter_by(id=task_id).first()

    if db_task:
        return jsonify({
            'uuid': str(db_task.id),
            'status': db_task.status,
            'message': db_task.message
        })
    else:
        return jsonify({'error': 'not found'}), 404


@app.route('/task', methods=['POST'])
def request_task():
    json = request.get_json()

    task_id = uuid.UUID(json['q'])
    db_task = database.session.query(ScrapeTask).filter_by(id=task_id).first()
    if db_task:
        if db_task.status == 'finished':
            ret = {
                'id': str(db_task.id),
                'name': db_task.change_job,
                'url': db_task.url,
                'status': db_task.change_status,
                'ci_username': db_task.change_ci_username,
                'pipeline': db_task.change_ci_pipeline,
                'change_id': db_task.change_id,
                'revision': db_task.change_rev,
                'change_project': db_task.change_project,
                'change_subject': db_task.change_subject,
                'artifacts': []
            }

            for artifact in db_task.artifacts:
                ret['artifacts'].append({
                    'id': artifact.id,
                    'artifact_name': artifact.artifact_name,
                    'artifact_type': artifact.artifact_type,
                    'content_type': artifact.content_type,
                    'content_encoding': artifact.content_encoding,
                })

            return jsonify(ret), 200
        elif db_task.status == 'error':
            return jsonify({
                'error': 'scrape task failed',
                'message': db_task.message
            })
        else:
            return jsonify({'error': 'not ready yet'}), 202
    else:
        return jsonify({'error': 'not found'}), 404


@app.route('/list', methods=['POST'])
def request_list():
    json = request.get_json()

    matches = url_matcher.get_matching_artifact_urls(json['q'])
    return jsonify(results=matches)


@app.route('/blob/<string:uuid_str>', methods=['GET'])
def request_blob(uuid_str):
    blob_id = uuid.UUID(uuid_str)

    q = database.session.query(ArtifactBlob).filter_by(id=blob_id)
    blob = q.one_or_none()

    if blob:
        headers = {'Content-Type': blob.content_type}
        if blob.content_encoding:
            headers['Content-Encoding'] = blob.content_encoding

        return blob.data, 200, headers
    else:
        return jsonify({'error': 'not found'}), 404


@app.teardown_appcontext
def shutdown_session(exception=None):
    database.session.remove()


if __name__ == '__main__':
    app.run(debug=True)
