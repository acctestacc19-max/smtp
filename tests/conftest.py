import os
import sys
import types
import builtins
import pytest
from dataclasses import dataclass
from typing import Optional

# Ensure project root is importable
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Provide globals that the target module incorrectly references
if not hasattr(builtins, "_name_"):
    builtins._name_ = "__not_main__"
if not hasattr(builtins, "_file_"):
    builtins._file_ = __file__

# Stub external modules that are not available in the test environment
if "oracledb" not in sys.modules:
    oracledb_stub = types.ModuleType("oracledb")
    # Provide a placeholder Connection type
    class _Connection:  # noqa: N801 (match expected name style)
        pass
    oracledb_stub.Connection = _Connection
    sys.modules["oracledb"] = oracledb_stub

if "ftfcu_appworx" not in sys.modules:
    appworx_stub = types.ModuleType("ftfcu_appworx")

    class _Apwx:
        def __init__(self, *args, **kwargs):
            self.args = None
            self.parser = None
        def db_connect(self, autocommit=False):
            return None
    class _JobTime:
        def print_start(self):
            pass
        def print_end(self):
            pass
    appworx_stub.Apwx = _Apwx
    appworx_stub.JobTime = _JobTime
    sys.modules["ftfcu_appworx"] = appworx_stub

if "jinja2" not in sys.modules:
    jinja2_stub = types.ModuleType("jinja2")
    class _Environment:
        def __init__(self, loader=None):
            self.loader = loader
        def get_template(self, name):
            class _T:
                def render(self, **kwargs):
                    return ""
            return _T()
    class _FileSystemLoader:
        def __init__(self, path):
            self.path = path
    jinja2_stub.Environment = _Environment
    jinja2_stub.FileSystemLoader = _FileSystemLoader
    sys.modules["jinja2"] = jinja2_stub

from delivery_update_method import AppWorxEnum, ScriptData


class DummyTemplate:
    def render(self, **kwargs) -> str:
        run_date = kwargs.get("run_date", "")
        current_time = kwargs.get("current_time", "")
        return f"Run Date: {run_date}, Time: {current_time}"


class FakeBatchError:
    def __init__(self, offset: int, message: str = "Batch error"):
        self.offset = offset
        self.message = message


class FakeCursor:
    def __init__(self, batch_errors=None):
        self._batch_errors = list(batch_errors or [])
        self._last_sql = None
        self._seq = None
        self.rowcount = 0
        self.description = []
        self.rowfactory = None

    def executemany(self, sql, seq_of_params, batcherrors=False):
        self._last_sql = sql
        self._seq = list(seq_of_params)
        self.rowcount = len(self._seq)

    def getbatcherrors(self):
        return self._batch_errors

    def execute(self, sql, params=None):
        self._last_sql = sql
        # minimal shape to emulate a select cursor description
        self.description = [("ENTITY_NUMBER",), ("ACCTNBR",), ("ENTITY_TYPE",), ("CLOSE_DATE",)]

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeDb:
    def __init__(self, batch_errors=None):
        self.autocommit = False
        self._cursor = FakeCursor(batch_errors=batch_errors)
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


@dataclass
class FakeApwxArgs:
    TNS_SERVICE_NAME: str
    CONFIG_FILE_PATH: str
    OUTPUT_FILE_PATH: str
    OUTPUT_FILE_NAME: str
    RUN_DATE: Optional[str]
    RPTONLY_YN: str
    FULL_CLEANUP_YN: str
    SEND_EMAIL_YN: str
    EMAIL_RECIPIENTS: Optional[str]
    SMTP_SERVER: str
    SMTP_PORT: int
    SMTP_USER: str
    SMTP_PASSWORD: str
    FROM_EMAIL_ADDR: str
    TEST_EMAIL_ADDR: Optional[str]


class FakeApwx:
    def __init__(self, args: FakeApwxArgs):
        self.args = args
        self.parser = None

    def db_connect(self, autocommit: bool = False):
        db = FakeDb()
        db.autocommit = autocommit
        return db


def build_default_config():
    return {
        "sql_queries": {
            "get_records": "SELECT * FROM some_table {{close_date_join}}",
            "update_pers_stdl": "merge into persuserfield ...",
            "update_org_stdl": "merge into orguserfield ...",
        },
        "join_fragments": {
            "date_specific": "/* date-specific join for {{run_date}} */",
            "full_cleanup": "/* full cleanup join */",
        },
        "template_directory": ".",
        "template_file": "dummy.html",
    }


@pytest.fixture()
def script_data(tmp_path):
    args = FakeApwxArgs(
        TNS_SERVICE_NAME="NON_EXISTING_DB",
        CONFIG_FILE_PATH=str(tmp_path / "config.yaml"),
        OUTPUT_FILE_PATH=str(tmp_path),
        OUTPUT_FILE_NAME="delivery_update_report.csv",
        RUN_DATE="02-01-2025",
        RPTONLY_YN="N",
        FULL_CLEANUP_YN="N",
        SEND_EMAIL_YN="Y",
        EMAIL_RECIPIENTS="test1@firsttechfed.com,test2@firsttechfed.com",
        SMTP_SERVER="smtp.local",
        SMTP_PORT=587,
        SMTP_USER="user",
        SMTP_PASSWORD="pass",
        FROM_EMAIL_ADDR="noreply@firsttechfed.com",
        TEST_EMAIL_ADDR=None,
    )
    apwx = FakeApwx(args)
    config = build_default_config()
    dbh = FakeDb()
    return ScriptData(apwx=apwx, dbh=dbh, config=config, email_template=DummyTemplate())


@pytest.fixture()
def script_data_rptonly_y(script_data):
    script_data.apwx.args.RPTONLY_YN = "Y"
    return script_data


@pytest.fixture()
def fake_db_with_errors():
    # one batch error at offset 1
    return FakeDb(batch_errors=[FakeBatchError(offset=1, message="Test merge error")])