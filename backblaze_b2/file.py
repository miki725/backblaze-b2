# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals
import datetime
import operator

import six

from .exceptions import B2FileNotFoundError
from .io import B2FileIO
from .utils import format_pairs


@six.python_2_unicode_compatible
class B2File(object):
    def __init__(self,
                 file_id=None,
                 name=None,
                 size=None,
                 content_type=None,
                 uploaded=None,
                 bucket=None):
        self._id = file_id
        self._name = name
        self._size = size
        self._content_type = content_type
        self.uploaded = uploaded
        self.bucket = bucket

    def _get_attribute(self, attr):
        if getattr(self, attr) is None:
            self.get_info()
        return getattr(self, attr)

    @property
    def driver(self):
        return self.bucket.driver

    @property
    def id(self):
        return self._get_attribute('_id')

    @property
    def name(self):
        return self._get_attribute('_name')

    @property
    def full_name(self):
        return '{}/{}'.format(self.bucket.name, self.name)

    @property
    def size(self):
        return self._get_attribute('_size')

    @property
    def content_type(self):
        return self._get_attribute('_content_type')

    @property
    def uploaded(self):
        return getattr(self, '_uploaded', None)

    @uploaded.setter
    def uploaded(self, value):
        if isinstance(value, six.integer_types):
            value = datetime.datetime.fromtimestamp(
                value / 1000,
                tz=datetime.timezone.utc
            )
        self._uploaded = value

    def get_info(self):
        if self._id:
            return self.get_info_by_id()
        else:
            return self.get_info_by_name()

    def get_info_by_id(self):
        response = self.driver.make_request(
            'b2_get_file_info',
            params={
                'fileId': self.id,
            },
        )
        data = response.json()
        self._name = data['fileName']
        self._size = data['contentLength']
        self._content_type = data['contentType']

    def get_info_by_name(self):
        versions = self.all_versions()

        try:
            latest = versions[0]
        except IndexError:
            raise B2FileNotFoundError(self.full_name)

        self._id = latest.id
        self._size = latest.size
        self._content_type = latest.content_type
        self.uploaded = latest.uploaded

    def get_info_from_headers(self, response):
        self._name = response.headers['X-Bz-File-Name'],
        self._size = int(response.headers['Content-Length']),
        self._content_type = response.headers['Content-Type'],

    def delete(self):
        self.driver.make_request(
            'b2_delete_file_version',
            params={
                'fileName': self.name,
                'fileId': self.id,
            },
        )

    def all_versions(self,
                     start_file_id=None,
                     versions_at_once=100,
                     reverse=True,
                     all_versions=True):
        params = self.bucket.get_parameters({
            'startFileName': self.name,
            'maxFileCount': versions_at_once,
        })
        if start_file_id:
            params.update({
                'startFileId': start_file_id,
            })

        response = self.driver.make_request(
            'b2_list_file_versions',
            params=params,
        )
        data = response.json()

        files = [
            B2File(
                file_id=file['fileId'],
                name=file['fileName'],
                size=file['size'],
                uploaded=file['uploadTimestamp'],
                bucket=self.bucket,
            )
            for file in data['files']
            if file['fileName'] == self.name and file['action'] == 'upload'
            ]

        if all([data['nextFileName'] == self.name,
                data['nextFileId'],
                all_versions]):
            return sorted(
                files + self.all_versions(
                    data['nextFileId'],
                    versions_at_once
                ),
                key=operator.attrgetter('uploaded'),
                reverse=reverse,
            )
        else:
            return sorted(
                files,
                key=operator.attrgetter('uploaded'),
                reverse=reverse
            )

    def download(self):
        if self._id:
            return self.download_by_id()
        else:
            return self.download_by_name()

    def download_by_name(self):
        response = self.driver.make_request(url=self.url, request_method='get')
        self.get_info_from_headers(response)
        return self._download_content_to_io(response)

    def download_by_id(self):
        response = self.driver.make_request(
            url=self.version_url,
            request_method='get',
        )
        self.get_info_from_headers(response)
        return self._download_content_to_io(response)

    @staticmethod
    def _download_content_to_io(response):
        return B2FileIO(
            content=response.content,
            size=int(response.headers['Content-Length']),
            name=response.headers['X-Bz-File-Name'],
            content_type=response.headers['Content-Type'],
            checksum=response.headers['X-Bz-Content-Sha1'],
        )

    @property
    def url(self):
        return self.driver.DOWNLOAD_URL_FORMAT.format(
            download_url=self.driver.download_url,
            bucket_name=self.bucket.name,
            file_name=self.name,
        )

    @property
    def version_url(self):
        return '{path}?fileId={file_id}'.format(
            path=self.driver.API_URL_FORMAT.format(
                api_url=self.driver.download_url,
                api_method='b2_download_file_by_id',
            ),
            file_id=self.id,
        )

    def __str__(self):
        return '{bucket}/{name}'.format(
            bucket=self.bucket,
            name=self.name,
        )

    def __repr__(self):
        return '<{klass}: {pairs}>'.format(
            klass=self.__class__.__name__,
            pairs=format_pairs(
                bucket=six.text_type(self.bucket),
                id=self._id,
                name=self._name,
                size=self._size,
                uploaded=self.uploaded,
            )
        )
