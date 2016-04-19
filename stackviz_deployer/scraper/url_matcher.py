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

import re
import urlparse

import requests

import gerrit_list


REGEX_GERRIT_CHANGE = re.compile(r'^(\d+)$')
REGEX_GERRIT_REVISION = re.compile(r'^(\d+)[,/](\d+)$')
REGEX_GERRIT_FRAGMENT = re.compile(r'/c/(\d+)(?:/(\d*))?')

GERRIT_ALLOWED_HOSTS = ['review.openstack.org']
LOGS_ALLOWED_HOSTS = ['logs.openstack.org']


def _create_empty_message():
    return {
        'index': 0,
        'status': None,
        'ci_username': None,
        'pipeline': None,
        'change_id': None,
        'revision': None,
        'change_project': None,
        'change_subject': None,
        'jobs': []
    }


def _create_job(name=None, url=None, status=None):
    return {
        'name': name,
        'url': url,
        'status': status
    }


def _gerrit_urls_filtered(change_id, revision=None):
    listing = gerrit_list.GerritListing(change_id)

    if revision is None:
        # default to the most recent revision
        revision = listing.revisions.keys()[-1]
    if revision not in listing.revisions:
        return []

    ret = []
    for message in listing.revisions[revision]:
        m = _create_empty_message()
        m.update({
            'index': message.index,
            'status': message.build_status,
            'ci_username': message.author['username'],
            'pipeline': message.pipeline,
            'change_id': change_id,
            'revision': revision,
            'change_project': listing.change_project,
            'change_subject': listing.change_subject
        })

        for job in message.jobs.values():
            m['jobs'].append(_create_job(job.name, job.url, job.status))

        ret.append(m)

    return ret


def _parse_fragment(fragment):
    regex = REGEX_GERRIT_FRAGMENT.match(fragment)
    if regex:
        change_id = regex.group(1)
        rev = regex.group(2)

        return int(change_id), int(rev) if rev else None
    else:
        return None, None


def _parse_logs_path(path):
    """Extract job information from a logs.openstack.org URL."""
    tokens = [token for token in path.split('/') if len(token) > 0]
    artifact = {}
    job = {}

    if tokens[0].startswith('periodic'):
        if len(tokens) >= 3:
            artifact['pipeline'] = tokens[0]
            job['name'] = tokens[1]
    else:
        if len(tokens) >= 2:
            artifact['change_id'] = int(tokens[1])

        if len(tokens) >= 3:
            artifact['revision'] = int(tokens[2])

        if len(tokens) >= 4:
            artifact['pipeline'] = tokens[3]

        if len(tokens) >= 5:
            job['name'] = tokens[4]

    return artifact, job


def get_matching_artifact_urls(user_input):
    """
    Find all matching artifact URLs for the given input string, and return a
    list of dicts containing details about each artifact source. Inputs are
    validated against a list of allowed hosts. Returned URLs should be
    suitable for use with artifacts_list.

    :param user_input: the input text to attempt to match
    :return: a list of artifact URL dicts
    """
    # short link to gerrit change id
    regex = REGEX_GERRIT_CHANGE.match(user_input)
    if regex:
        return _gerrit_urls_filtered(int(regex.group(1)))

    # short link to gerrit change id and specific revision
    regex = REGEX_GERRIT_REVISION.match(user_input)
    if regex:
        return _gerrit_urls_filtered(int(regex.group(1)), int(regex.group(2)))

    # full gerrit url
    parsed = urlparse.urlparse(user_input)
    if parsed.hostname in GERRIT_ALLOWED_HOSTS:
        if len(parsed.path) > 1:
            try:
                return _gerrit_urls_filtered(int(parsed.path[1:]))
            except ValueError:
                pass

        if parsed.fragment:
            change_id, revision = _parse_fragment(parsed.fragment)
            if change_id:
                return _gerrit_urls_filtered(change_id, revision)

    # direct link to job output
    if parsed.hostname in LOGS_ALLOWED_HOSTS:
        artifact_info = _create_empty_message()
        artifact_job = _create_job('direct-link', user_input)
        artifact_info['jobs'].append(artifact_job)

        parsed_artifact_info, parsed_job_info = _parse_logs_path(parsed.path)
        artifact_info.update(parsed_artifact_info)
        artifact_job.update(parsed_job_info)

        if 'change_id' in parsed_artifact_info:
            # try to fetch the gerrit change to fill in missing details
            try:
                listing = gerrit_list.GerritListing(
                    parsed_artifact_info['change_id'])
                artifact_info['change_project'] = listing.change_project
                artifact_info['change_subject'] = listing.change_subject

                job = listing.get_job_by_url(user_input)
                if job:
                    artifact_info['status'] = job.status
                    artifact_job['status'] = job.status
            except requests.HTTPError:
                pass

        return [artifact_info]

    return []
