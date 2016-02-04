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

import urlparse

import bs4
import requests


class InvalidArtifactError(Exception):
    """An error raised when an artifact is invalid."""
    pass


class Artifact:
    """A single artifact from a directory listing"""

    def __init__(self, base_url, rel_url, entry_type, name):
        self.base_url = base_url
        self.rel_url = rel_url
        self.entry_type = entry_type
        self.name = name

    def is_dir(self):
        return self.entry_type == '[DIR]'

    def abs_url(self):
        return urlparse.urljoin(self.base_url, self.rel_url)

    def browse(self):
        if not self.is_dir():
            raise InvalidArtifactError('Cannot browse a non-directory artifact.')

        return DirectoryListing(self.abs_url())

    def __repr__(self):
        return '%s(base_url=%s, rel_url=%s, entry_type=%s, name=%s)' % (
            self.__class__.__name__,
            "'%s'" % self.base_url,
            "'%s'" % self.rel_url,
            "'%s'" % self.entry_type,
            "'%s'" % self.name
        )


class DirectoryListing:
    """A navigator for Apache 2 directory listings."""

    def __init__(self, url):
        self.url = url

        self.files = []
        self.directories = []

        response = requests.get(url)
        response.raise_for_status()

        soup = bs4.BeautifulSoup(response.text)
        items = soup.select('tr td a')

        for item in items:
            rel_url = item.attrs['href']
            entry_type = item.parent.parent.select('td img')[0].attrs['alt']
            name = item.text

            artifact = Artifact(self.url, rel_url, entry_type, name)
            if artifact.is_dir():
                self.directories.append(artifact)
            else:
                self.files.append(artifact)

    def __repr__(self):
        return "%s(url='%s', directories=[%s], files=[%s])" % (
            self.__class__.__name__,
            self.url,
            ', '.join(map(lambda d: "'%s'" % d.name, self.directories)),
            ', '.join(map(lambda f: "'%s'" % f.name, self.files))
        )
