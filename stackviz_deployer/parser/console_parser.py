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
import re

from jenkins_jobs.builder import Builder


# Regex to match Jenkins builder scripts, and extract name + command
REGEX_SCRIPT = re.compile(r'^\[(?P<job>[a-z\-]+)\] \$ (?P<command>.*)$')

# Regex to match SCP lines
REGEX_SCP = re.compile(r'^\[SCP\] .+$')

# Regex to match '{param}' in JJB job template names
REGEX_JJB_TOKEN = re.compile(r'\{.+\}')

REGEX_STATUS = re.compile('^Finished: (\w+)$')

# Path to scan for project-config JJB yaml files
JJB_YAML_PATH = os.environ.get('JJB_YAML_PATH', 'project-config/jenkins/jobs')


# Hack: we want to use Builder's file loading code, but we don't need a
# Jenkins instance. (And using dummy params spams the console)
# We'll just steal the method we need and give it default params
class HackBuilder:
    load_files = Builder.__dict__['load_files']

    def __init__(self):
        self.global_config = None
        self.plugins_list = []
        self.parser = None

builder = HackBuilder()
builder.load_files([JJB_YAML_PATH])


def job_name_matches_template(job_name, template):
    """
    Checks if the job name matches the job template string. For example, a job
    named 'gate-stackviz-npm-run-test' will match a template string
    'gate-{name}-npm-run-{command}'.

    :param job_name: the job name to check
    :param template: the job name template to compare against
    :return: True if the name matches the template string, otherwise False
    """
    # convert template to a regex
    regex = re.sub(r'\{[\w\-]+\}', r'[\w\-]*', template)

    return re.match(regex, job_name) is not None


def get_builders_from_template(template):
    """
    Given a parsed JJB template, extract a list of builder name strings.
    Builders that accept parameters (written as dicts) will have parameters
    discarded and only the names will be included.

    :param template: the template to read
    :return: a list of builder strings
    """
    scripts = []

    for b in template['builders']:
        if isinstance(b, dict):
            scripts.append(b.keys()[0])
        else:
            scripts.append(b)

    return scripts


def get_job_builders(job_name):
    """
    Given a job name, return a list of JJB builder name strings defined for
    the job's template.

    :param job_name: the job name to look up
    :return: a list of builder names, or None if not match is found
    """
    templates = builder.parser.data['job-template']

    # tuples of (template, wildcard count)
    matches = []

    for name, template in templates.iteritems():
        if job_name_matches_template(job_name, name):
            count = len(re.findall(r'\{[\w\-]+\}', name))
            matches.append((template, count))

    if not matches:
        return None

    # since we don't know the actual variable names/values, we need to guess
    # which match is correct
    # minimizing the number of wildcards used ('{....}' groups) seems to
    # eliminate a lot of otherwise incorrect choices
    best = sorted(matches, key=lambda e: e[1])
    return get_builders_from_template(best[0][0])


def parse_console(text):
    script_names = None
    scripts = []

    scp_found = False
    current_script = {'name': 'setup', 'lines': []}
    scripts.append(current_script)

    status = None

    for raw_line in text.splitlines():
        if ' | ' not in raw_line:
            continue

        date_str, line = raw_line.split(' | ', 1)

        # if this line is a script run, start a new script section
        m = REGEX_SCRIPT.match(line)
        if m:
            if script_names is None:
                script_names = get_job_builders(m.group('job'))

            current_script = {
                'name': script_names.pop(0) if script_names else None,
                'lines': []
            }
            scripts.append(current_script)

        # similarly, for the first scp line, start the scp section
        if not scp_found:
            m = REGEX_SCP.match(line)
            if m:
                scp_found = True
                current_script = {'name': 'scp', 'lines': []}
                scripts.append(current_script)

        m = REGEX_STATUS.match(line)
        if m:
            status = m.group(1)
            break

        current_script['lines'].append({
            'date': date_str,
            'line': line
        })

    return {
        'status': status,
        'scripts': scripts,
        'remaining': script_names
    }


