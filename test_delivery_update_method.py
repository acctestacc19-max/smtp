import datetime
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

from delivery_update_method import (
    fetch_records,
    process_records,
    update_stdl_userfield,
    write_report_file,
    send_notification_email,
    generate_email_content,
    generate_email_message,
    send_email_enabled,
    is_local_environment,
    run,
)

MODULE_NAME = os.path.basename(Path(os.path.dirname(__file__)).parent)

TEST_RECORDS = [
    {
        "ENTITY_NUMBER": "1001",
        "ACCTNBR": "12345",
        "ENTITY_TYPE": "pers",
        "CLOSE_DATE": "2025-01-01",
    },
    {
        "ENTITY_NUMBER": "1002",
        "ACCTNBR": "12346",
        "ENTITY_TYPE": "org",
        "CLOSE_DATE": "2025-01-01",
    },
    {
        "ENTITY_NUMBER": "1003",
        "ACCTNBR": "12347",
        "ENTITY_TYPE": "pers",
        "CLOSE_DATE": "2025-01-01",
    },
]


def test_fetch_records_date_specific(script_data, mocker):
    """Test fetch_records with a specific run date"""
    mock_execute = mocker.patch(f"{MODULE_NAME}.delivery_update_method.execute_sql_select", return_value=TEST_RECORDS)
    
    pers_records, org_records = fetch_records(script_data)
    
    assert len(pers_records) == 2
    assert len(org_records) == 1
    assert pers_records[0]["ENTITY_TYPE"] == "pers"
    assert org_records[0]["ENTITY_TYPE"] == "org"
    mock_execute.assert_called_once()


def test_fetch_records_full_cleanup(script_data_full_cleanup, mocker):
    """Test fetch_records with full cleanup mode"""
    mock_execute = mocker.patch(f"{MODULE_NAME}.delivery_update_method.execute_sql_select", return_value=TEST_RECORDS)
    
    pers_records, org_records = fetch_records(script_data_full_cleanup)
    
    assert len(pers_records) == 2
    assert len(org_records) == 1
    mock_execute.assert_called_once()


def test_fetch_records_parameter_validation_error(script_data, mocker):
    """Test fetch_records with conflicting parameters"""
    script_data.apwx.args.RUN_DATE = "01-01-2025"
    script_data.apwx.args.FULL_CLEANUP_YN = "Y"
    
    try:
        fetch_records(script_data)
        assert False, "Should have raised an exception"
    except Exception as e:
        assert "mutually exclusive" in str(e)


def test_fetch_records_no_parameters_error(script_data, mocker):
    """Test fetch_records with no valid parameters"""
    script_data.apwx.args.RUN_DATE = None
    script_data.apwx.args.FULL_CLEANUP_YN = "N"
    
    try:
        fetch_records(script_data)
        assert False, "Should have raised an exception"
    except Exception as e:
        assert "no RUN_DATE parameter provided" in str(e)


def test_process_records(script_data, mocker):
    """Test process_records function"""
    pers_records = [r for r in TEST_RECORDS if r["ENTITY_TYPE"] == "pers"]
    org_records = [r for r in TEST_RECORDS if r["ENTITY_TYPE"] == "org"]
    
    mock_update_pers = mocker.patch(f"{MODULE_NAME}.delivery_update_method.update_stdl_userfield", 
                                   side_effect=[([("1001", "12345", "pers", "2025-01-01", "Success")], []),
                                              ([("1002", "12346", "org", "2025-01-01", "Success")], [])])
    
    # Mock file existence check
    mocker.patch("pathlib.Path.exists", return_value=False)
    
    successes, fails = process_records(script_data, pers_records, org_records)
    
    assert len(successes) == 2
    assert len(fails) == 0
    assert mock_update_pers.call_count == 2


def test_process_records_file_exists_error(script_data, mocker):
    """Test process_records when output file already exists"""
    pers_records = [r for r in TEST_RECORDS if r["ENTITY_TYPE"] == "pers"]
    org_records = [r for r in TEST_RECORDS if r["ENTITY_TYPE"] == "org"]
    
    # Mock file exists
    mocker.patch("pathlib.Path.exists", return_value=True)
    
    try:
        process_records(script_data, pers_records, org_records)
        assert False, "Should have raised FileExistsError"
    except FileExistsError as e:
        assert "Output file already exists" in str(e)


def test_update_stdl_userfield_success(script_data, mocker):
    """Test update_stdl_userfield with successful updates"""
    records = [TEST_RECORDS[0]]
    
    # Mock cursor
    mock_cursor = MagicMock()
    mock_cursor.getbatcherrors.return_value = []
    mock_cursor.rowcount = 1
    script_data.dbh.cursor.return_value = mock_cursor
    
    successes, fails = update_stdl_userfield(script_data, records, "persuserfield", "persnbr")
    
    assert len(successes) == 1
    assert len(fails) == 0
    assert successes[0][4] == "Success"


def test_update_stdl_userfield_with_errors(script_data, mocker):
    """Test update_stdl_userfield with batch errors"""
    records = [TEST_RECORDS[0]]
    
    # Mock cursor with batch errors
    mock_cursor = MagicMock()
    mock_error = MagicMock()
    mock_error.offset = 0
    mock_error.message = "Test error"
    mock_cursor.getbatcherrors.return_value = [mock_error]
    mock_cursor.rowcount = 0
    script_data.dbh.cursor.return_value = mock_cursor
    
    successes, fails = update_stdl_userfield(script_data, records, "persuserfield", "persnbr")
    
    assert len(successes) == 0
    assert len(fails) == 1
    assert fails[0][4] == "Fail"


def test_update_stdl_userfield_empty_records(script_data):
    """Test update_stdl_userfield with empty records"""
    successes, fails = update_stdl_userfield(script_data, [], "persuserfield", "persnbr")
    
    assert len(successes) == 0
    assert len(fails) == 0


def test_write_report_file(script_data, mocker):
    """Test write_report_file function"""
    successes = [("1001", "12345", "pers", "2025-01-01", "Success")]
    fails = [("1002", "12346", "org", "2025-01-01", "Fail")]
    
    mock_write = mocker.patch(f"{MODULE_NAME}.delivery_update_method.write_report", return_value=True)
    
    write_report_file(script_data, successes, fails)
    
    assert mock_write.call_count == 2


def test_send_notification_email_with_fails(script_data, mocker):
    """Test send_notification_email when there are failures"""
    fails = [("1001", "12345", "pers", "2025-01-01", "Fail")]
    
    mock_send = mocker.patch(f"{MODULE_NAME}.delivery_update_method.send_email", return_value=(True, "Email Sent"))
    
    send_notification_email(script_data, fails)
    
    mock_send.assert_called_once()


def test_send_notification_email_no_fails(script_data, mocker):
    """Test send_notification_email when there are no failures"""
    fails = []
    
    mock_send = mocker.patch(f"{MODULE_NAME}.delivery_update_method.send_email")
    
    send_notification_email(script_data, fails)
    
    mock_send.assert_not_called()


def test_generate_email_content(script_data):
    """Test generate_email_content function"""
    script_data.email_template.render.return_value = "Test email content"
    
    content = generate_email_content(script_data)
    
    assert content == "Test email content"
    script_data.email_template.render.assert_called_once()


def test_generate_email_message():
    """Test generate_email_message function"""
    from_addr = "test@firsttechfed.com"
    to_addr = "recipient@firsttechfed.com"
    content = "Test email content"
    
    message = generate_email_message(from_addr, to_addr, content)
    
    assert message["Subject"] == "Statement Delivery Method Update Alert"
    assert message["From"] == f"First Tech Federal Credit Union <{from_addr}>"
    assert message["To"] == to_addr


def test_send_email_enabled_true(script_data):
    """Test send_email_enabled returns True when SEND_EMAIL_YN is Y"""
    script_data.apwx.args.SEND_EMAIL_YN = "Y"
    
    result = send_email_enabled(script_data.apwx)
    
    assert result is True


def test_send_email_enabled_false(script_data):
    """Test send_email_enabled returns False when SEND_EMAIL_YN is N"""
    script_data.apwx.args.SEND_EMAIL_YN = "N"
    
    result = send_email_enabled(script_data.apwx)
    
    assert result is False


def test_is_local_environment_true(mocker):
    """Test is_local_environment returns True when AW_HOME is not set"""
    mocker.patch.dict(os.environ, {}, clear=True)
    
    result = is_local_environment()
    
    assert result is True


def test_is_local_environment_false(mocker):
    """Test is_local_environment returns False when AW_HOME is set"""
    mocker.patch.dict(os.environ, {"AW_HOME": "/some/path"})
    
    result = is_local_environment()
    
    assert result is False


def test_run_normal_mode(script_data, mocker):
    """Test run function in normal mode"""
    mocker.patch(f"{MODULE_NAME}.delivery_update_method.initialize", return_value=script_data)
    mocker.patch(f"{MODULE_NAME}.delivery_update_method.fetch_records", 
                return_value=([TEST_RECORDS[0]], [TEST_RECORDS[1]]))
    mocker.patch(f"{MODULE_NAME}.delivery_update_method.process_records", 
                return_value=(["success"], []))
    mock_write_report = mocker.patch(f"{MODULE_NAME}.delivery_update_method.write_report_file")
    mock_send_email = mocker.patch(f"{MODULE_NAME}.delivery_update_method.send_notification_email")
    
    result = run(script_data.apwx)
    
    assert result is True
    mock_write_report.assert_called_once()
    mock_send_email.assert_called_once()
    script_data.dbh.close.assert_called_once()


def test_run_report_only_mode(script_data_report_only, mocker):
    """Test run function in report-only mode"""
    mocker.patch(f"{MODULE_NAME}.delivery_update_method.initialize", return_value=script_data_report_only)
    mocker.patch(f"{MODULE_NAME}.delivery_update_method.fetch_records", 
                return_value=([], []))
    mocker.patch(f"{MODULE_NAME}.delivery_update_method.process_records", 
                return_value=([], []))
    mock_write_report = mocker.patch(f"{MODULE_NAME}.delivery_update_method.write_report_file")
    mock_send_email = mocker.patch(f"{MODULE_NAME}.delivery_update_method.send_notification_email")
    
    result = run(script_data_report_only.apwx)
    
    assert result is True
    mock_write_report.assert_called_once()
    mock_send_email.assert_called_once()
    script_data_report_only.dbh.close.assert_called_once()


def test_run_with_environment_setup(script_data, mocker):
    """Test run function sets AW_HOME environment variable"""
    mocker.patch(f"{MODULE_NAME}.delivery_update_method.initialize", return_value=script_data)
    mocker.patch(f"{MODULE_NAME}.delivery_update_method.fetch_records", return_value=([], []))
    mocker.patch(f"{MODULE_NAME}.delivery_update_method.process_records", return_value=([], []))
    mocker.patch(f"{MODULE_NAME}.delivery_update_method.write_report_file")
    mocker.patch(f"{MODULE_NAME}.delivery_update_method.send_notification_email")
    
    with patch.dict(os.environ, {}, clear=True):
        run(script_data.apwx)
        assert os.environ["AW_HOME"] == "sai"