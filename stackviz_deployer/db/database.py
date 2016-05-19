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

from sqlalchemy import create_engine
from sqlalchemy.engine.url import URL
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base


# override using environment variables if available
url = URL('mysql+pymysql',
          username=os.environ.get('MYSQL_ENV_MYSQL_USER', 'stackviz'),
          password=os.environ.get('MYSQL_ENV_MYSQL_PASSWORD', 'stackviz'),
          host=os.environ.get('MYSQL_PORT_3306_TCP_ADDR', 'localhost'),
          port=int(os.environ.get('MYSQL_PORT_3306_TCP_PORT', '3306')),
          database=os.environ.get('MYSQL_ENV_MYSQL_DATABASE', 'stackviz'))

engine = create_engine(url, pool_recycle=3600)

session = scoped_session(sessionmaker(autocommit=False,
                                      autoflush=False,
                                      bind=engine))

Base = declarative_base()
Base.query = session.query_property()


def init_db():
    # noinspection PyUnresolvedReferences
    import stackviz_deployer.db.models

    Base.metadata.create_all(bind=engine)
