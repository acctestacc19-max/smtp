import os
import pathlib
import pytest
from dataclasses import dataclass
from unittest.mock import MagicMock

from delivery_update_method import (
    AppWorxEnum,
    get_config,
    ScriptData,
)


@dataclass
class FakeApwxArgs:
    TNS_SERVICE_NAME: str
    CONFIG_FILE_PATH: str
    OUTPUT_FILE_PATH: str
    OUTPUT_FILE_NAME: str
    RUN_DATE: str
    RPTONLY_YN: str
    FULL_CLEANUP_YN: str
    SEND_EMAIL_YN: str
    EMAIL_RECIPIENTS: str
    SMTP_SERVER: str
    SMTP_PORT: int
    SMTP_USER: str
    SMTP_PASSWORD: str
    FROM_EMAIL_ADDR: str
    TEST_EMAIL_ADDR: str


@dataclass
class FakeApwx:
    args: FakeApwxArgs


TEST_BASE_PATH = pathlib.Path(os.path.dirname(__file__))
CONFIG_PATH = TEST_BASE_PATH / "config" / "config.yaml"


SCRIPT_ARGUMENTS = {
    str(AppWorxEnum.TNS_SERVICE_NAME): "FAKE_DB",
    str(AppWorxEnum.CONFIG_FILE_PATH): str(CONFIG_PATH),
    str(AppWorxEnum.OUTPUT_FILE_PATH): str(TEST_BASE_PATH),
    str(AppWorxEnum.OUTPUT_FILE_NAME): "delivery_update_report.csv",
    str(AppWorxEnum.RUN_DATE): "01-01-2025",
    str(AppWorxEnum.RPTONLY_YN): "N",
    str(AppWorxEnum.FULL_CLEANUP_YN): "N",
    str(AppWorxEnum.SEND_EMAIL_YN): "Y",
    str(AppWorxEnum.EMAIL_RECIPIENTS): "test@firsttechfed.com",
    str(AppWorxEnum.SMTP_SERVER): "smtp.test.com",
    str(AppWorxEnum.SMTP_PORT): 587,
    str(AppWorxEnum.SMTP_USER): "test_user",
    str(AppWorxEnum.SMTP_PASSWORD): "test_password",
    str(AppWorxEnum.FROM_EMAIL_ADDR): "AM_PROD@firsttechfed.com",
    str(AppWorxEnum.TEST_EMAIL_ADDR): "test@firsttechfed.com",
}

SCRIPT_ARGUMENTS_REPORT_ONLY = {
    **SCRIPT_ARGUMENTS,
    str(AppWorxEnum.OUTPUT_FILE_NAME): "delivery_update_report_report_only.csv",
    str(AppWorxEnum.RPTONLY_YN): "Y",
    str(AppWorxEnum.SEND_EMAIL_YN): "N",
}

SCRIPT_ARGUMENTS_FULL_CLEANUP = {
    **SCRIPT_ARGUMENTS,
    str(AppWorxEnum.OUTPUT_FILE_NAME): "delivery_update_report_full_cleanup.csv",
    str(AppWorxEnum.RUN_DATE): None,
    str(AppWorxEnum.FULL_CLEANUP_YN): "Y",
}


def new_fake_apwx(script_args: dict) -> FakeApwx:
    return FakeApwx(
        args=FakeApwxArgs(
            TNS_SERVICE_NAME=script_args[str(AppWorxEnum.TNS_SERVICE_NAME)],
            CONFIG_FILE_PATH=script_args[str(AppWorxEnum.CONFIG_FILE_PATH)],
            OUTPUT_FILE_PATH=script_args[str(AppWorxEnum.OUTPUT_FILE_PATH)],
            OUTPUT_FILE_NAME=script_args[str(AppWorxEnum.OUTPUT_FILE_NAME)],
            RUN_DATE=script_args.get(str(AppWorxEnum.RUN_DATE)),
            RPTONLY_YN=script_args[str(AppWorxEnum.RPTONLY_YN)],
            FULL_CLEANUP_YN=script_args[str(AppWorxEnum.FULL_CLEANUP_YN)],
            SEND_EMAIL_YN=script_args[str(AppWorxEnum.SEND_EMAIL_YN)],
            EMAIL_RECIPIENTS=script_args[str(AppWorxEnum.EMAIL_RECIPIENTS)],
            SMTP_SERVER=script_args[str(AppWorxEnum.SMTP_SERVER)],
            SMTP_PORT=script_args[str(AppWorxEnum.SMTP_PORT)],
            SMTP_USER=script_args[str(AppWorxEnum.SMTP_USER)],
            SMTP_PASSWORD=script_args[str(AppWorxEnum.SMTP_PASSWORD)],
            FROM_EMAIL_ADDR=script_args[str(AppWorxEnum.FROM_EMAIL_ADDR)],
            TEST_EMAIL_ADDR=script_args.get(str(AppWorxEnum.TEST_EMAIL_ADDR)),
        )
    )


@pytest.fixture(scope="module")
def mock_config():
    return {
        "sql_queries": {
            "get_records": "SELECT * FROM test_table {{close_date_join}}",
            "update_pers_stdl": "MERGE INTO persuserfield",
            "update_org_stdl": "MERGE INTO orguserfield"
        },
        "join_fragments": {
            "date_specific": "WHERE close_date = '{{run_date}}'",
            "full_cleanup": "WHERE close_date IS NOT NULL"
        },
        "template_directory": "templates",
        "template_file": "email_template.html"
    }


@pytest.fixture(scope="module")
def script_data(mock_config):
    apwx = new_fake_apwx(SCRIPT_ARGUMENTS)
    dbh = MagicMock()
    email_template = MagicMock()
    return ScriptData(apwx=apwx, dbh=dbh, config=mock_config, email_template=email_template)


@pytest.fixture(scope="module")
def script_data_report_only(mock_config):
    apwx = new_fake_apwx(SCRIPT_ARGUMENTS_REPORT_ONLY)
    dbh = MagicMock()
    email_template = MagicMock()
    return ScriptData(apwx=apwx, dbh=dbh, config=mock_config, email_template=email_template)


@pytest.fixture(scope="module")
def script_data_full_cleanup(mock_config):
    apwx = new_fake_apwx(SCRIPT_ARGUMENTS_FULL_CLEANUP)
    dbh = MagicMock()
    email_template = MagicMock()
    return ScriptData(apwx=apwx, dbh=dbh, config=mock_config, email_template=email_template)