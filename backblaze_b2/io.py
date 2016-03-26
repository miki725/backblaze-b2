# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import six


class B2FileIO(six.BytesIO):
    def __init__(self, content, size, name, content_type, checksum):
        super(B2FileIO, self).__init__(content)
        self.size = size
        self.name = name
        self.content_type = content_type
        self.checksum = checksum
