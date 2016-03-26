# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals
import hashlib
from collections import namedtuple
from enum import Enum

import requests
import six
from cached_property import cached_property

from .file import B2File
from .utils import format_pairs


UploadInfo = namedtuple('UploadInfo', [
    'upload_url',
    'authorization_token',
])


@six.python_2_unicode_compatible
class B2Bucket(object):
    class TYPES(Enum):
        public = 'allPublic'
        private = 'allPrivate'

    def __init__(self, bucket_id, driver, name=None, bucket_type=None):
        self.id = bucket_id
        self.driver = driver
        self.name = name
        self.type = self.TYPES(bucket_type)

    @cached_property
    def _upload_info(self):
        response = self.driver.make_request(
            'b2_get_upload_url',
            self.get_parameters(),
        )
        data = response.json()
        return UploadInfo(
            upload_url=data['uploadUrl'],
            authorization_token=data['authorizationToken'],
        )

    @cached_property
    def upload_connection(self):
        session = requests.Session()
        session.headers.update({
            'Authorization': self._upload_info.authorization_token,
        })
        return session

    @property
    def upload_url(self):
        return self._upload_info.upload_url

    def get_parameters(self, data=None):
        params = {
            'bucketId': self.id,
        }
        params.update(data or {})
        return params

    def update(self, bucket_type):
        bucket_type = self.TYPES(bucket_type).value
        self.driver.make_request(
            'b2_update_bucket',
            self.get_parameters(self.driver.get_parameters({
                'bucketType': bucket_type,
            })),
        )
        self.type = bucket_type

    def delete(self):
        self.driver.make_request(
            'b2_delete_bucket',
            self.get_parameters(self.driver.get_parameters())
        )

    def get_file_by_name(self, name):
        file = B2File(name=name, bucket=self)
        # raises exception when file not found
        file.get_info()
        return file

    def all_files(self, start_filename=None):
        params = self.get_parameters({
            'maxFileCount': 1000,
        })
        if start_filename:
            params.update({
                'startFileName': start_filename,
            })

        response = self.driver.make_request(
            'b2_list_file_names',
            self.get_parameters(),
        )
        data = response.json()

        files = [
            B2File(
                file_id=i['fileId'],
                name=i['fileName'],
                size=i['size'],
                uploaded=i['uploadTimestamp'],
                bucket=self,
            )
            for i in data['files']
        ]

        if data['nextFileName']:
            return files + self.all_files(data['nextFileName'])

        return files

    def upload_file(self,
                    fid,
                    name,
                    content_type='b2/x-auto',
                    overwrite_file=False):
        if overwrite_file:
            file = B2File(name=name, bucket=self)
            for version in file.all_versions():
                version.delete()

        data = fid.read()

        assert isinstance(data, six.binary_type), (
            'Must pass file object opened in binary mode'
        )

        fid.seek(0)

        headers = {
            'X-Bz-File-Name': name,
            'Content-Type': content_type,
            'X-Bz-Content-Sha1': hashlib.sha1(data).hexdigest(),
        }

        response = self.driver.make_request(
            connection=self.upload_connection,
            url=self.upload_url,
            headers=headers,
            data=data,
        )

        response_data = response.json()

        return B2File(
            file_id=response_data['fileId'],
            name=response_data['fileName'],
            size=response_data['contentLength'],
            content_type=response_data['contentType'],
            bucket=self,
        )

    def __str__(self):
        return self.name or 'None'

    def __repr__(self):
        return '<{klass}: {pairs}>'.format(
            klass=self.__class__.__name__,
            pairs=format_pairs(
                id=self.id,
                name=self.name,
            )
        )
