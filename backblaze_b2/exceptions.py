# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import requests
import six

from .utils import format_pairs


class B2Exception(Exception):
    pass


@six.python_2_unicode_compatible
class B2APIError(B2Exception, requests.RequestException):
    def __init__(self, code, message, status_code):
        self.code = code
        self.message = message
        self.status_code = status_code

    def __repr__(self):
        return '<{klass}: {pairs}>'.format(
            klass=self.__class__.__name__,
            pairs=format_pairs(
                status_code=self.status_code,
                code=self.code,
                message=self.message,
            )
        )

    def __str__(self):
        return format_pairs(
            status_code=self.status_code,
            code=self.code,
            message=self.message,
        )


class B2FileNotFoundError(B2Exception):
    pass


class B2BucketNotFoundError(B2Exception):
    def __init__(self, bucket_name):
        self.bucket_name = bucket_name


class B2PrivateBucketError(B2Exception):
    pass
