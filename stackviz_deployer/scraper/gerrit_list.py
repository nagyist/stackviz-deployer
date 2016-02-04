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

import collections
import re

import requests
import simplejson

import artifacts_list


API_BASE = 'https://review.openstack.org/'
API_CHANGES = API_BASE + 'changes/'

#: A list of (id, username) tuples of CI accounts we can parse messages for
CI_ACCOUNT_IDS = [(3, 'jenkins')]

REGEX_VERIFIED = re.compile(r'^Patch Set (\d+): Verified([+-])(\d+)$')
REGEX_PIPELINE = re.compile(r'^Build (\w+) \((\w+) pipeline\).*$')
REGEX_JOB = re.compile(r'^- (\S+) (\S+) : (\w+) in (.*)$')


def is_ci_account(author):
    """Determines if the given author block matches a known CI account.

    The author's _account_id is checked against a known list of CI accounts,
    as defined in CI_ACCOUNT_IDS.

    :param author: the Gerrit API AccountInfo entity to check
    :return: True if the author is a known CI account, otherwise False
    """
    for account_id, name in CI_ACCOUNT_IDS:
        if author['_account_id'] == account_id:
            return True

    return False


class InvalidMessageError(Exception):
    """An error raised when a message cannot be parsed."""
    pass


class CIJob:
    """A CI job result, with an associated name and artifact URL."""

    def __init__(self, name, url, status, duration):
        self.name = name
        self.url = url
        self.status = status
        self.duration = duration

    def browse(self):
        """Fetch the directory listing for this job's artifact output URL."""
        return artifacts_list.DirectoryListing(self.url)

    def __repr__(self):
        return "%s(name='%r', url='%r', status='%r', duration='%r')" % (
            self.__class__.__name__,
            self.name,
            self.url,
            self.status,
            self.duration
        )


class CIMessage:
    def __init__(self, message):
        self.author = message['author']
        self.date = message['date']
        self.revision = message['_revision_number']

        lines = message['message'].splitlines()

        verified = REGEX_VERIFIED.match(lines[0])
        if not verified:
            raise InvalidMessageError()

        self.vote = int(verified.group(3))
        if verified.group(2) == '-':
            self.vote *= -1

        pipeline = REGEX_PIPELINE.match(lines[2])
        if not pipeline:
            raise InvalidMessageError()

        self.build_status = pipeline.group(1)
        self.pipeline = pipeline.group(2)

        self.jobs = {}
        for job_line in lines[4:]:
            job = REGEX_JOB.match(job_line)

            self.jobs[job.group(1)] = CIJob(
                job.group(1),
                job.group(2),
                job.group(3),
                job.group(4))

    def __repr__(self):
        return "%s(author='%s', vote=%d, pipeline='%s', jobs={%s})" % (
            self.__class__.__name__,
            self.author['username'],
            self.vote,
            self.pipeline,
            ', '.join(map(lambda k: "'%s'" % k, self.jobs.keys()))
        )


class GerritListing:
    """Extracts Jenkins build artifact URLs from Gerrit comments."""

    def __init__(self, change_id):
        self.change_id = change_id

        self.revisions = collections.OrderedDict()

        response = requests.get(API_CHANGES + str(change_id) + '/detail')
        response.raise_for_status()

        # gerrit API outputs junk on first line to prevent XSSI, remove it
        raw_json = '\n'.join(response.text.splitlines()[1:])

        change = simplejson.loads(raw_json)
        self.change_project = change['project']
        self.change_subject = change['subject']

        for message in change['messages']:
            # ignore author-less CI messages ("change has been merged", etc)
            if 'author' not in message:
                continue

            if is_ci_account(message['author']):
                rev = message['_revision_number']
                if rev not in self.revisions:
                    self.revisions[rev] = []

                try:
                    self.revisions[rev].append(CIMessage(message))
                except InvalidMessageError:
                    pass
    
    def iter_jobs(self):
        """Iterate over all jobs in this Gerrit listing.

        :rtype: collections.Iterable[CIJob]
        """
        for _, messages in self.revisions.iteritems():
            for message in messages:
                for job in message.jobs.values():
                    yield job

    def get_job_by_url(self, url):
        """Attempt to locate a particular job among all messages by URL.
        
        :param url: the job URL to match against
        :return: a CIJob or None
        """
        for job in self.iter_jobs():
            if job.url == url:
                return job

        return None

    def __repr__(self):
        return '%s(change_id=%s, revisions={%s})' % (
            self.__class__.__name__,
            self.change_id,
            ', '.join(map(str, self.revisions.keys()))
        )
