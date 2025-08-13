import csv
from pathlib import Path
import pytest

import delivery_update_method as mod


def test_run_happy_path_writes_report_and_closes_db(script_data, monkeypatch):
    # Arrange
    pers_records = [
        {"ENTITY_NUMBER": 101, "ACCTNBR": 9001, "ENTITY_TYPE": "pers", "CLOSE_DATE": "02-01-2025"},
    ]
    org_records = []
    successes = [(101, 9001, "pers", "02-01-2025", "Success")]
    fails = []

    monkeypatch.setattr(mod, "initialize", lambda apwx: script_data)
    monkeypatch.setattr(mod, "fetch_records", lambda sd: (pers_records, org_records))
    monkeypatch.setattr(mod, "process_records", lambda sd, p, o: (successes, fails))

    called = []
    monkeypatch.setattr(mod, "send_notification_email", lambda sd, f: called.append((sd, f)))

    # Act
    assert mod.run(script_data.apwx) is True

    # Assert
    assert called == [(script_data, fails)]

    out_path = Path(script_data.apwx.args.OUTPUT_FILE_PATH) / script_data.apwx.args.OUTPUT_FILE_NAME
    assert out_path.exists()

    with open(out_path, "r", newline="") as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["ENTITY_NBR", "ACCTNBR", "ENTITY_TYPE", "CLOSE_DATE", "RESULT"]
    assert rows[1] == ["101", "9001", "pers", "02-01-2025", "Success"]

    assert script_data.dbh.closed is True


def test_fetch_records_builds_sql_and_splits_types(script_data, monkeypatch):
    # Arrange
    returned = [
        {"ENTITY_NUMBER": 1, "ACCTNBR": 111, "ENTITY_TYPE": "pers", "CLOSE_DATE": "02-01-2025"},
        {"ENTITY_NUMBER": 2, "ACCTNBR": 222, "ENTITY_TYPE": "org", "CLOSE_DATE": "02-01-2025"},
    ]
    captured_sql = []

    def fake_exec(conn, sql, params=None):
        captured_sql.append(sql)
        return returned

    monkeypatch.setattr(mod, "execute_sql_select", fake_exec)

    # Act
    pers, org = mod.fetch_records(script_data)

    # Assert
    assert len(pers) == 1 and len(org) == 1
    assert "/* date-specific join for 02-01-2025 */" in captured_sql[0]


def test_fetch_records_param_conflict_raises(script_data):
    script_data.apwx.args.FULL_CLEANUP_YN = "Y"
    script_data.apwx.args.RUN_DATE = "02-01-2025"
    with pytest.raises(Exception):
        mod.fetch_records(script_data)


def test_fetch_records_missing_param_raises(script_data):
    script_data.apwx.args.FULL_CLEANUP_YN = "N"
    script_data.apwx.args.RUN_DATE = None
    with pytest.raises(Exception):
        mod.fetch_records(script_data)


def test_update_stdl_userfield_commits_when_rptonly_n(script_data):
    # Arrange
    script_data.apwx.args.RPTONLY_YN = "N"
    records = [
        {"ENTITY_NUMBER": 10, "ACCTNBR": 100, "ENTITY_TYPE": "pers", "CLOSE_DATE": "02-01-2025"},
        {"ENTITY_NUMBER": 11, "ACCTNBR": 101, "ENTITY_TYPE": "pers", "CLOSE_DATE": "02-01-2025"},
    ]

    # Act
    successes, fails = mod.update_stdl_userfield(script_data, records, table_name="persuserfield", col_name="persnbr")

    # Assert
    assert script_data.dbh.commits == 1
    assert script_data.dbh.rollbacks == 0
    assert len(successes) == len(records)
    assert fails == []


def test_update_stdl_userfield_rollbacks_when_rptonly_y(script_data_rptonly_y):
    records = [
        {"ENTITY_NUMBER": 20, "ACCTNBR": 200, "ENTITY_TYPE": "org", "CLOSE_DATE": "02-01-2025"},
    ]
    successes, fails = mod.update_stdl_userfield(script_data_rptonly_y, records, table_name="orguserfield", col_name="orgnbr")
    assert script_data_rptonly_y.dbh.commits == 0
    assert script_data_rptonly_y.dbh.rollbacks == 1
    assert len(successes) == len(records)
    assert fails == []


def test_write_report_file_writes_header_and_rows(script_data):
    out_path = Path(script_data.apwx.args.OUTPUT_FILE_PATH) / script_data.apwx.args.OUTPUT_FILE_NAME
    successes = [
        (101, 9001, "pers", "02-01-2025", "Success"),
        (102, 9002, "org", "02-01-2025", "Success"),
    ]

    # Act
    mod.write_report_file(script_data, successes, fails=[])

    # Assert
    with open(out_path, "r", newline="") as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["ENTITY_NBR", "ACCTNBR", "ENTITY_TYPE", "CLOSE_DATE", "RESULT"]
    assert rows[1] == ["101", "9001", "pers", "02-01-2025", "Success"]
    assert rows[2] == ["102", "9002", "org", "02-01-2025", "Success"]


def test_send_notification_email_with_recipients_calls_send_email(script_data, monkeypatch):
    fails = [(201, 9001, "pers", "02-01-2025", "Fail")]
    called = []

    def fake_send_email(sd, recipients):
        called.append(recipients)
        return True, "Email Sent"

    monkeypatch.setattr(mod, "send_email", fake_send_email)

    mod.send_notification_email(script_data, fails)

    assert called and called[0] == script_data.apwx.args.EMAIL_RECIPIENTS.split(",")


def test_send_email_success(script_data, monkeypatch):
    monkeypatch.setattr(mod, "is_local_environment", lambda: False)

    sent = []

    def fake_send_smtp(apwx, from_addr, to_addr, email_msg):
        sent.append((from_addr, to_addr))
        return None

    monkeypatch.setattr(mod, "send_smtp_request", fake_send_smtp)

    ok, msg = mod.send_email(script_data, ["ops@firsttechfed.com"]) 
    assert ok is True and msg == "Email Sent"
    assert sent[-1][1] == "ops@firsttechfed.com"

    # prefer TEST_EMAIL_ADDR when provided
    script_data.apwx.args.TEST_EMAIL_ADDR = "test_override@firsttechfed.com"
    ok, msg = mod.send_email(script_data, ["ops@firsttechfed.com"]) 
    assert ok is True
    assert sent[-1][1] == "test_override@firsttechfed.com"


def test_send_email_disabled_by_env_or_flag(script_data, monkeypatch):
    # disabled by local env
    monkeypatch.setattr(mod, "is_local_environment", lambda: True)
    ok, msg = mod.send_email(script_data, ["ops@firsttechfed.com"]) 
    assert ok is False and msg == "Email Send Disabled"

    # disabled by flag
    monkeypatch.setattr(mod, "is_local_environment", lambda: False)
    script_data.apwx.args.SEND_EMAIL_YN = "N"
    ok, msg = mod.send_email(script_data, ["ops@firsttechfed.com"]) 
    assert ok is False and msg == "Email Send Disabled"


def test_generate_email_message():
    msg = mod.generate_email_message("from@example.com", "to@example.com", "<p>Hello</p>")
    assert msg["Subject"] == "Statement Delivery Method Update Alert"
    assert "from@example.com" in msg["From"]
    assert msg["To"] == "to@example.com"


def test_send_email_no_recipients(script_data):
    ok, msg = mod.send_email(script_data, [])
    assert ok is False and msg == "No email recipients"


def test_send_email_enabled_helper(script_data):
    assert mod.send_email_enabled(script_data.apwx) is True
    script_data.apwx.args.SEND_EMAIL_YN = "N"
    assert mod.send_email_enabled(script_data.apwx) is False