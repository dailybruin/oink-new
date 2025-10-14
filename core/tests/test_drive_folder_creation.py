import os
import json
import pytest
from django.test import TestCase
from django.conf import settings
from core.drive import create_drive_folder


class DummyService:
    def __init__(self):
        self._created = []

    class Files:
        def __init__(self, outer):
            self.outer = outer
        def create(self, body=None, fields=None):
            class Exec:
                def __init__(self, outer, body):
                    self.outer = outer
                    self.body = body
                def execute(self):
                    # Simulate returning an id
                    self.outer._created.append(self.body)
                    return {'id': 'fake-folder-id'}
            return Exec(self.outer, body)

    class Permissions:
        def __init__(self):
            pass
        def create(self, fileId=None, body=None, fields=None):
            class Exec:
                def execute(self):
                    return {'id': 'perm-id'}
            return Exec()

    def files(self):
        return DummyService.Files(self)
    def permissions(self):
        return DummyService.Permissions()


def test_create_drive_folder_env_json(monkeypatch):
    # Provide service account JSON via env var
    info = {"type": "service_account", "project_id": "x", "private_key_id": "id", "private_key": "-----BEGIN PRIVATE KEY-----\nMIIB\n-----END PRIVATE KEY-----\n", "client_email": "svc@example.com", "client_id": "1", "token_uri": "https://oauth2.googleapis.com/token"}
    monkeypatch.setenv('GOOGLE_SERVICE_ACCOUNT_FILE', json.dumps(info))

    # Patch google modules used inside create_drive_folder
    import core.drive as d

    class DummyCreds:
        def with_subject(self, subj):
            return self

    def from_info(i, scopes=None):
        return DummyCreds()

    def build_mock(api, ver, credentials=None, cache_discovery=False):
        return DummyService()

    monkeypatch.setattr(d.service_account.Credentials, 'from_service_account_info', staticmethod(from_info), raising=True)
    monkeypatch.setattr(d, 'build', build_mock, raising=True)

    res = create_drive_folder('hello')
    assert isinstance(res, dict)
    assert res.get('id') == 'fake-folder-id'
    assert res.get('url') == 'https://drive.google.com/drive/folders/fake-folder-id'
