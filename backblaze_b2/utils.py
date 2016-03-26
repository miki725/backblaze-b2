# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals


def format_pairs(**kwargs):
    return ' '.join(
        '{key}={value!r}'.format(key=k, value=v)
        for k, v in sorted(kwargs.items())
    )
