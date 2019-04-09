# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import vcr
from backblaze_b2 import B2Driver
from requests import Session


ACCOUNT_ID = 'ee11fbe710b2'
APP_ID = '0010f89f434d2f793e836bb494a6f694c10c510544'
AUTH_TOKEN = (
    '3_20160326225123_62ee482598f65ccc9b9755fb_9d88'
    'fe68fcfad798ec8b62f891926a77cc48bc1e_001_acct'
)


class TestB2Driver(object):
    @vcr.use_cassette('fixtures/vcr_cassettes/driver.yaml')
    def setup_method(self, method):
        self.driver = B2Driver(ACCOUNT_ID, APP_ID)

    @vcr.use_cassette('fixtures/vcr_cassettes/driver.yaml')
    def test__api_info(self):
        info = self.driver._api_info

        assert info.api_url == 'https://api001.backblaze.com'
        assert info.download_url == 'https://f001.backblaze.com'
        assert info.authorization_token == AUTH_TOKEN

    @vcr.use_cassette('fixtures/vcr_cassettes/driver.yaml')
    def test_connection(self):
        connection = self.driver.connection

        assert isinstance(connection, Session)
        assert connection.headers['Authorization'] == AUTH_TOKEN

    @vcr.use_cassette('fixtures/vcr_cassettes/driver.yaml')
    def test_api_url(self):
        assert self.driver.api_url == 'https://api001.backblaze.com'

    @vcr.use_cassette('fixtures/vcr_cassettes/driver.yaml')
    def test_download_url(self):
        assert self.driver.download_url == 'https://f001.backblaze.com'

    def test_get_parameters(self):
        params = self.driver.get_parameters({'foo': 'bar'})

        assert params == {
            'accountId': ACCOUNT_ID,
            'foo': 'bar'
        }
