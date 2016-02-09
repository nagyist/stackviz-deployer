===============================
stackviz-deployer
===============================

An on-demand deployment web service for StackViz.

* Free software: Apache license
* Documentation: http://docs.openstack.org/developer/stackviz-deployer
* Source: http://git.openstack.org/cgit/openstack/stackviz-deployer
* Bugs: http://bugs.launchpad.net/stackviz

Goals
-----
This project aims to provide a easy-to-use UI for generating StackViz sites. Users should be able to paste in a URL, select a list of matches, and then have a StackViz site generated on demand. The actual contents of the generated site should depend on what artifacts can be scraped from the job output (e.g. subunit, dstat, possibly more in the future).

Current State
-------------
This project is currently working towards a working proof-of-concept. Components are making varying degrees of progress toward this:

* API: mostly feature-complete, still needs input validation and cleanup jobs
* Workers: mostly feature-complete, still needs input validation
* Frontend: WIP, nothing ready to show yet
* StackViz support: WIP

Usage - Server
--------------
The server implementation is currently incomplete and very much in flux. Right now it uses MySQL for persistent storage with a Celery task queue (using Redis as a broker). In production the web UI (static HTML) and API server (python+flask) should be run behind Nginx or Apache.

The current requirements are as follows:

* MySQL server on localhost, with empty database :code:`stackviz`, user :code:`stackviz`, password :code:`stackviz`
* Redis server on localhost, default port, no authentication (will use db #0)
* A celery worker: :code:`celery -A stackviz_deployer.tasks.tasks worker`
* The API server: :code:`PYTHONPATH="." python -mstackviz_deployer.api.api`

Note that the MySQL database could get large relatively fast as gzipped artifacts are stored as blobs for the moment. That said, there should be no harm in purging records after some relatively short time limit (e.g. 7 days). Even so, one processed dataset (gzipped in the database, without logging) should be around 250 KB.

Usage - Frontend
----------------
The frontend is currently a WIP, this section will be updated when it is added to the repository.

Usage - API
-----------

Examples using `HTTPie <https://github.com/jkbrzt/httpie>`_  and `jq <https://stedolan.github.io/jq/>`_ with the dev server:

* List the latest Jenkins results for a Gerrit change (one entry per job)::

    $ http post localhost:5000/list q=271726
    HTTP/1.0 200 OK
    Content-Length: 2379
    Content-Type: application/json
    Date: Tue, 09 Feb 2016 02:39:10 GMT
    Server: Werkzeug/0.10.4 Python/2.7.8

    { "results": [
        {
            "change_id": 271726,
            "change_project": "openstack/stackviz",
            "change_subject": "Add nprogress progress bars to timeline and test-details.",
            "ci_username": "jenkins",
            "name": "gate-stackviz-pep8",
            "pipeline": "check",
            "revision": 2,
            "status": "SUCCESS",
            "url": "http://logs.openstack.org/26/271726/2/check/gate-stackviz-pep8/7c374a7/"
        },
    ], ... }

* List Jenkins jobs for a specific Gerrit revision::

    $ http post localhost:5000/list q=271726,1

* List jobs from a Gerrit URL (with or without a revision or fragment)::

    $ http post localhost:5000/list q='https://review.openstack.org/#/c/271726/'

* List a job directly from the artifact URL (will parse and look up Gerrit details when possible)::

    $ http post localhost:5000/list q='http://logs.openstack.org/26/271726/2/gate/gate-stackviz-python27/937cf7b/'
    HTTP/1.0 200 OK
    Content-Length: 423
    Content-Type: application/json
    Date: Tue, 09 Feb 2016 02:45:30 GMT
    Server: Werkzeug/0.10.4 Python/2.7.8
    {
        "results": [
            {
                "change_id": 271726,
                "change_project": "openstack/stackviz",
                "change_subject": "Add nprogress progress bars to timeline and test-details.",
                "ci_username": null,
                "name": "gate-stackviz-python27",
                "pipeline": "gate",
                "revision": 2,
                "status": "SUCCESS",
                "url": "http://logs.openstack.org/26/271726/2/gate/gate-stackviz-python27/937cf7b/"
            }
        ]
    }

* Request a scrape of some artifact listing from :code:`/list`::

    $ http post localhost:5000/list q=269624 | jq '.results[2]' | http post localhost:5000/scrape
    HTTP/1.0 202 ACCEPTED
    Content-Length: 74
    Content-Type: application/json
    Date: Tue, 09 Feb 2016 03:33:23 GMT
    Server: Werkzeug/0.10.4 Python/2.7.8

    {
        "status": "queued",
        "uuid": "f223e63b-6ac0-4236-9c1c-4dec769310aa"
    }

* Get the status of a scrape::

    $ http post localhost:5000/status q=f223e63b-6ac0-4236-9c1c-4dec769310aa
    HTTP/1.0 200 OK
    Content-Length: 76
    Content-Type: application/json
    Date: Tue, 09 Feb 2016 03:34:44 GMT
    Server: Werkzeug/0.10.4 Python/2.7.8

    {
        "status": "finished",
        "uuid": "f223e63b-6ac0-4236-9c1c-4dec769310aa"
    }

* Get the results of a scrape::

    http post localhost:5000/task q=f223e63b-6ac0-4236-9c1c-4dec769310aa
    HTTP/1.0 200 OK
    Content-Length: 761
    Content-Type: application/json
    Date: Tue, 09 Feb 2016 03:35:39 GMT
    Server: Werkzeug/0.10.4 Python/2.7.8

    {
        "artifacts": [
            {
                "artifact_type": "dstat",
                "content_encoding": "gzip",
                "content_type": "text/csv",
                "id": "09890181-4149-4cb2-82e3-c27f8301db03"
            },
            {
                "artifact_type": "subunit",
                "content_encoding": "gzip",
                "content_type": "application/json",
                "id": "79f81039-d51c-46af-a8cb-13e31efe1a57"
            }
        ],
        "change_id": 269624,
        "change_project": "openstack/cinder",
        "change_subject": "Support for consistency groups in ScaleIO driver",
        "ci_username": "jenkins",
        "id": "f223e63b-6ac0-4236-9c1c-4dec769310aa",
        "name": "gate-tempest-dsvm-full",
        "pipeline": "check",
        "revision": 19,
        "status": "SUCCESS",
        "url": "http://logs.openstack.org/24/269624/19/check/gate-tempest-dsvm-full/84f9b4a/"
    }

* Fetch an artifact blob (will have encoding and content type set appropriately)::

    $ http get localhost:5000/blob/09890181-4149-4cb2-82e3-c27f8301db03 --headers
    HTTP/1.0 200 OK
    Content-Encoding: gzip
    Content-Length: 187744
    Content-Type: text/csv
    Date: Tue, 09 Feb 2016 03:36:57 GMT
    Server: Werkzeug/0.10.4 Python/2.7.8

Note that all API endpoints accept and produce JSON, except :code:`/blob`.
