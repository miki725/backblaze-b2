# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals
import datetime
import json
import operator
from collections import namedtuple
from enum import Enum

import requests
import six
from cached_property import cached_property


ConnectionInfo = namedtuple('ConnectionInfo', [
    'api_url',
    'download_url',
    'authorization_token',
])


def format_pairs(**kwargs):
    return ' '.join(
        '{key}={value!r}'.format(key=k, value=v)
        for k, v in sorted(kwargs.items())
    )


class B2Exception(Exception):
    pass


@six.python_2_unicode_compatible
class B2APIError(B2Exception, requests.RequestException):
    def __init__(self, code, message, status_code):
        self.code = code
        self.message = message
        self.status_code = status_code

    def __repr__(self):
        return (
            '<{klass}: '
            'status_code={status_code!r} '
            'code={code!r} '
            'message={message!r}'
            '>'
            ''.format(klass=self.__class__.__name__,
                      status_code=self.status_code,
                      code=self.code,
                      message=self.message)
        )

    def __str__(self):
        return (
            'status_code={status_code!r} '
            'code={code!r} '
            'message={message!r}'
            ''.format(status_code=self.status_code,
                      code=self.code,
                      message=self.message)
        )


class B2FileNotFoundError(B2Exception):
    pass


class B2InvalidBucketError(B2Exception):
    def __init__(self, bucket_name):
        self.bucket_name = bucket_name


class B2PrivateBucketError(B2Exception):
    pass


class B2FileIO(six.BytesIO):
    def __init__(self, content, size, name, content_type, checksum):
        super(B2FileIO, self).__init__(content)
        self.size = size
        self.name = name
        self.content_type = content_type
        self.checksum = checksum


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
            value = datetime.datetime.fromtimestamp(value / 1000, tz=datetime.timezone.utc)
        self._uploaded = value

    def get_info(self):
        if self._id:
            return self.get_info_by_id()
        else:
            return self.get_info_by_name()

    def get_info_by_id(self):
        print('getting info by id')
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

        self._id = latest._id
        self._size = latest._size
        self._content_type = latest._content_type
        self.uploaded = latest.uploaded

    def get_info_from_headers(self, response):
        self._name = response.headers['X-Bz-File-Name'],
        self._size = int(response.headers['Content-Length']),
        self._content_type = response.headers['Content-Type'],

    def all_versions(self, start_file_id=None, versions_at_once=100, reverse=True, all_versions=True):
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
                files + self.all_versions(data['nextFileId'], versions_at_once),
                key=operator.attrgetter('uploaded'),
                reverse=reverse,
                )
        else:
            return sorted(files, key=operator.attrgetter('uploaded'), reverse=reverse)

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
        response = self.driver.make_request(url=self.version_url, request_method='get')
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

    def all_files(self, start_filename=None):
        params = self.get_parameters({
            'maxFileCount': 1000,
        })
        if start_filename:
            params.update({
                'startFileName': start_filename,
            })

        response = self.driver.make_request('b2_list_file_names', self.get_parameters())
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

    def upload_file(self, fid, name, content_type='b2/x-auto'):
        raise NotImplementedError

    def __str__(self):
        return self.name or 'None'

    def __repr__(self):
        return '<{klass}: id={id!r} name={name!r}>'.format(
            klass=self.__class__.__name__,
            id=self.id,
            name=self.name,
        )


class B2Driver(object):
    AUTH_URL = 'https://api.backblaze.com/b2api/v1/b2_authorize_account'
    API_URL_FORMAT = '{api_url}/b2api/v1/{api_method}'
    DOWNLOAD_URL_FORMAT = '{download_url}/file/{bucket_name}/{file_name}'

    def __init__(self, account_id, application_id):
        self.use_versions = False
        self.account_id = account_id
        self.application_id = application_id

    @cached_property
    def _connection(self):
        r = requests.get(
            self.AUTH_URL,
            auth=requests.auth.HTTPBasicAuth(self.account_id, self.application_id)
        )
        data = r.json()

        return ConnectionInfo(
            data['apiUrl'],
            data['downloadUrl'],
            data['authorizationToken'],
        )

    @cached_property
    def connection(self):
        session = requests.Session()
        session.headers.update({
            'Authorization': self._connection.authorization_token,
        })
        return session

    def get_parameters(self, data=None):
        params = {
            'accountId': self.account_id,
        }
        params.update(data or {})
        return params

    @property
    def api_url(self):
        return self._connection.api_url

    @property
    def download_url(self):
        return self._connection.download_url

    def get_api_method_url(self, api_method, base=None):
        return self.API_URL_FORMAT.format(
            api_url=base or self.api_url,
            api_method=api_method,
        )

    def make_request(self, api_method=None, params=None, url=None, request_method='post'):
        url = url or self.get_api_method_url(api_method)
        data = json.dumps(params) if params else None
        headers = {
            'Content-Type': 'application/json',
        }

        method = getattr(self.connection, request_method)
        response = method(url, data=data, headers=headers)

        if response.status_code != 200:
            try:
                data = response.json()
                raise B2APIError(data['code'], data['message'], response.status_code)
            except (ValueError, KeyError):
                raise B2APIError('error', response.content, response.status_code)

        return response

    def get_bucket(self, bucket_id, name=None):
        return B2Bucket(
            bucket_id=bucket_id,
            name=name,
            driver=self,
        )

    def get_bucket_by_name(self, name):
        buckets = self.all_buckets()

        for bucket in buckets:
            if bucket.name == name:
                return bucket

        raise B2InvalidBucketError(name)

    def create_bucket(self, name, bucket_type):
        bucket_type = B2Bucket.TYPES(bucket_type).value
        response = self.make_request('b2_create_bucket', self.get_parameters({
            'bucketName': name,
            'bucketType': bucket_type.value,
        }))
        data = response.json()
        return B2Bucket(
            bucket_id=data['bucketId'],
            name=name,
            bucket_type=bucket_type,
            driver=self,
        )

    def all_buckets(self):
        response = self.make_request('b2_list_buckets', self.get_parameters())
        data = response.json()
        return [
            B2Bucket(
                bucket_id=i['bucketId'],
                name=i['bucketName'],
                bucket_type=i['bucketType'],
                driver=self,
            )
            for i in data['buckets']
            ]

    def __repr__(self):
        return '<{klass}: account_id={id!r}>'.format(
            klass=self.__class__.__name__,
            id=self.account_id,
        )
