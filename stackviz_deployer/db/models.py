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

import enum
from datetime import datetime

from sqlalchemy import (Column, ForeignKey,
                        Integer, String, DateTime)
from sqlalchemy.dialects.mysql import MEDIUMBLOB
from sqlalchemy.orm import relationship
from sqlalchemy_utils import UUIDType

from stackviz_deployer.db.database import Base


class ScrapeStatus(enum.Enum):
    new = 'new'
    success = 'success'
    error = 'error'


class ScrapeTask(Base):
    __tablename__ = 'scrape_tasks'
    __table_args__ = {'mysql_engine': 'InnoDB'}

    id = Column(UUIDType(binary=False), primary_key=True)
    status = Column(String(63), nullable=False, default='new')
    date = Column(DateTime, nullable=False, default=datetime.utcnow)

    change_id = Column(Integer, index=True)
    change_rev = Column(Integer)
    change_job = Column(String(127))
    change_project = Column(String(127))
    change_subject = Column(String(255))
    change_status = Column(String(63))
    change_ci_username = Column(String(127))
    change_ci_pipeline = Column(String(63))

    url = Column(String(255), index=True)

    artifacts = relationship('ArtifactBlob')


class ArtifactBlob(Base):
    __tablename__ = 'artifact_blobs'
    __table_args__ = {'mysql_engine': 'InnoDB'}

    id = Column(UUIDType(binary=False), primary_key=True)
    task_id = Column(UUIDType(binary=False),
                     ForeignKey('scrape_tasks.id'),
                     index=True)

    artifact_type = Column(String(63))
    content_type = Column(String(63))
    content_encoding = Column(String(63))

    data = Column(MEDIUMBLOB)
