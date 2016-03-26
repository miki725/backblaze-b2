# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals
import json
from collections import namedtuple

import requests
from cached_property import cached_property

from .bucket import B2Bucket
from .exceptions import B2APIError, B2BucketNotFoundError
from .utils import format_pairs


ConnectionInfo = namedtuple('ConnectionInfo', [
    'api_url',
    'download_url',
    'authorization_token',
])


class B2Driver(object):
    AUTH_URL = 'https://api.backblaze.com/b2api/v1/b2_authorize_account'
    API_URL_FORMAT = '{api_url}/b2api/v1/{api_method}'
    DOWNLOAD_URL_FORMAT = '{download_url}/file/{bucket_name}/{file_name}'

    def __init__(self, account_id, application_id):
        self.use_versions = False
        self.account_id = account_id
        self.application_id = application_id

    @cached_property
    def _api_info(self):
        r = requests.get(
            self.AUTH_URL,
            auth=requests.auth.HTTPBasicAuth(
                self.account_id,
                self.application_id
            )
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
            'Authorization': self._api_info.authorization_token,
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
        return self._api_info.api_url

    @property
    def download_url(self):
        return self._api_info.download_url

    def get_api_method_url(self, api_method, base=None):
        return self.API_URL_FORMAT.format(
            api_url=base or self.api_url,
            api_method=api_method,
        )

    def make_request(self,
                     api_method=None,
                     params=None,
                     url=None,
                     data=None,
                     request_method='post',
                     headers=None,
                     connection=None):
        url = url or self.get_api_method_url(api_method)
        data = data or (json.dumps(params) if params else None)
        headers = headers or {
            'Content-Type': 'application/json',
        }

        method = getattr(connection or self.connection, request_method)
        response = method(url, data=data, headers=headers)

        if response.status_code != 200:
            try:
                response_data = response.json()
                raise B2APIError(
                    response_data['code'],
                    response_data['message'],
                    response.status_code,
                )
            except (ValueError, KeyError):
                raise B2APIError(
                    'error',
                    response.content,
                    response.status_code
                )

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

        raise B2BucketNotFoundError(name)

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
        return '<{klass}: {pairs}>'.format(
            klass=self.__class__.__name__,
            pairs=format_pairs(account_id=self.account_id),
        )
