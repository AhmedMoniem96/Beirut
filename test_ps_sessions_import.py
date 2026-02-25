import unittest
from unittest.mock import patch

from beirut_pos.services.ps_sessions import load_ps_session_from_db


class _FakeCursor:
    def execute(self, *_args, **_kwargs):
        return None

    def fetchone(self):
        return None


class _FakeConn:
    def cursor(self):
        return _FakeCursor()

    def close(self):
        return None


class PsSessionsImportSmokeTest(unittest.TestCase):
    def test_load_ps_session_from_db_import_and_call(self):
        with patch("beirut_pos.core.db.get_conn", return_value=_FakeConn()):
            result = load_ps_session_from_db("T1")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
