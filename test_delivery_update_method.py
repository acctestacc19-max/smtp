import csv
import os
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from delivery_update_method import (
    run,
    fetch_records,
    process_records,
    update_stdl_userfield,
    write_report_file,
    write_report,
    send_notification_email,
    send_email,
    generate_email_message,
    generate_email_content,
    send_smtp_request,
    is_local_environment,
    send_email_enabled,
    get_config,
    get_email_template,
    execute_sql_select,
    initialize,
    dna_db_connect,
)


# Get the module name since it is dynamically generated in CICD env
MODULE_NAME = os.path.basename(Path(os.path.dirname(__file__)).parent) if os.path.basename(Path(os.path.dirname(__file__)).parent) else "delivery_update_method"


class TestRun:
    """Test the main run function"""

    def test_run_success(self, script_data, mocker):
        """Test successful run execution"""
        # Mock all the functions called by run
        mock_initialize = mocker.patch(
            f"{MODULE_NAME}.initialize",
            return_value=script_data,
        )
        mock_fetch_records = mocker.patch(
            f"{MODULE_NAME}.fetch_records",
            return_value=([], []),  # empty person and org records
        )
        mock_process_records = mocker.patch(
            f"{MODULE_NAME}.process_records",
            return_value=([], []),  # empty successes and failures
        )
        mock_write_report = mocker.patch(f"{MODULE_NAME}.write_report_file")
        mock_send_notification = mocker.patch(f"{MODULE_NAME}.send_notification_email")
        mock_dbh_close = mocker.Mock()
        script_data.dbh = mock_dbh_close

        # Function under test
        result = run(script_data.apwx)

        # Validate
        assert result is True
        mock_initialize.assert_called_once()
        mock_fetch_records.assert_called_once()
        mock_process_records.assert_called_once()
        mock_write_report.assert_called_once()
        mock_send_notification.assert_called_once()
        mock_dbh_close.close.assert_called_once()


class TestFetchRecords:
    """Test the fetch_records function"""

    def test_fetch_records_with_run_date(self, script_data, sample_person_records, sample_org_records, mocker):
        """Test fetch_records with specific run date"""
        all_records = sample_person_records + sample_org_records
        mock_execute_sql = mocker.patch(
            f"{MODULE_NAME}.execute_sql_select",
            return_value=all_records,
        )

        pers_records, org_records = fetch_records(script_data)

        assert len(pers_records) == 2
        assert len(org_records) == 2
        assert all(r['ENTITY_TYPE'] == 'pers' for r in pers_records)
        assert all(r['ENTITY_TYPE'] == 'org' for r in org_records)
        mock_execute_sql.assert_called_once()

    def test_fetch_records_full_cleanup(self, script_data_full_cleanup, all_sample_records, mocker):
        """Test fetch_records with full cleanup mode"""
        mock_execute_sql = mocker.patch(
            f"{MODULE_NAME}.execute_sql_select",
            return_value=all_sample_records,
        )

        pers_records, org_records = fetch_records(script_data_full_cleanup)

        assert len(pers_records) == 2
        assert len(org_records) == 2
        mock_execute_sql.assert_called_once()

    def test_fetch_records_parameter_validation_error_both_provided(self, script_data, mocker):
        """Test parameter validation when both RUN_DATE and FULL_CLEANUP_YN are provided"""
        # Modify script_data to have both parameters
        script_data.apwx.args.RUN_DATE = "12-15-2025"
        script_data.apwx.args.FULL_CLEANUP_YN = "Y"

        with pytest.raises(Exception, match="Parameter error - IS_FULL_CLEANUP and RUN_DATE params are mutually exclusive"):
            fetch_records(script_data)

    def test_fetch_records_parameter_validation_error_neither_provided(self, script_data, mocker):
        """Test parameter validation when neither RUN_DATE nor FULL_CLEANUP_YN are provided"""
        # Modify script_data to have neither parameter
        script_data.apwx.args.RUN_DATE = None
        script_data.apwx.args.FULL_CLEANUP_YN = "N"

        with pytest.raises(Exception, match="Parameter error - no RUN_DATE parameter provided, and IS_FULL_CLEANUP not selected"):
            fetch_records(script_data)


class TestProcessRecords:
    """Test the process_records function"""

    def test_process_records_success(self, script_data, sample_person_records, sample_org_records, mocker):
        """Test successful record processing"""
        # Mock file existence check
        mocker.patch("pathlib.Path.exists", return_value=False)
        
        # Mock the update functions
        mock_update_pers = mocker.patch(
            f"{MODULE_NAME}.update_stdl_userfield",
            return_value=([(1001, 9351560090, 'pers', '12/15/2025', 'Success')], [])
        )
        mock_update_org = mocker.patch(
            f"{MODULE_NAME}.update_stdl_userfield",
            return_value=([(2001, 9344462412, 'org', '12/15/2025', 'Success')], [])
        )

        successes, fails = process_records(script_data, sample_person_records, sample_org_records)

        assert len(successes) == 2
        assert len(fails) == 0
        mock_update_pers.assert_called_once()
        mock_update_org.assert_called_once()

    def test_process_records_file_exists_error(self, script_data, sample_person_records, sample_org_records, mocker):
        """Test error when output file already exists"""
        # Mock file existence check to return True
        mocker.patch("pathlib.Path.exists", return_value=True)

        with pytest.raises(FileExistsError, match="Output file already exists"):
            process_records(script_data, sample_person_records, sample_org_records)


class TestUpdateStdlUserfield:
    """Test the update_stdl_userfield function"""

    def test_update_stdl_userfield_empty_records(self, script_data):
        """Test update_stdl_userfield with empty records"""
        successes, fails = update_stdl_userfield(script_data, [], 'persuserfield', 'persnbr')
        assert successes == []
        assert fails == []

    def test_update_stdl_userfield_success(self, script_data, sample_person_records, mocker):
        """Test successful update_stdl_userfield execution"""
        # Mock database cursor
        mock_cursor = Mock()
        mock_cursor.executemany = Mock()
        mock_cursor.getbatcherrors = Mock(return_value=[])
        mock_cursor.rowcount = 2
        mock_cursor.close = Mock()
        
        mock_dbh = Mock()
        mock_dbh.cursor = Mock(return_value=mock_cursor)
        mock_dbh.commit = Mock()
        mock_dbh.rollback = Mock()
        
        script_data.dbh = mock_dbh

        successes, fails = update_stdl_userfield(script_data, sample_person_records, 'persuserfield', 'persnbr')

        assert len(successes) == 2
        assert len(fails) == 0
        mock_cursor.executemany.assert_called_once()
        mock_dbh.commit.assert_called_once()

    def test_update_stdl_userfield_with_errors(self, script_data, sample_person_records, mocker):
        """Test update_stdl_userfield with batch errors"""
        # Mock batch error
        mock_error = Mock()
        mock_error.offset = 0
        mock_error.message = "Test error"
        
        mock_cursor = Mock()
        mock_cursor.executemany = Mock()
        mock_cursor.getbatcherrors = Mock(return_value=[mock_error])
        mock_cursor.rowcount = 1
        mock_cursor.close = Mock()
        
        mock_dbh = Mock()
        mock_dbh.cursor = Mock(return_value=mock_cursor)
        mock_dbh.commit = Mock()
        
        script_data.dbh = mock_dbh

        successes, fails = update_stdl_userfield(script_data, sample_person_records, 'persuserfield', 'persnbr')

        assert len(fails) == 1
        mock_cursor.executemany.assert_called_once()


class TestWriteReportFile:
    """Test the write_report_file function"""

    def test_write_report_file_with_successes_and_fails(self, script_data, mocker):
        """Test write_report_file with both successes and failures"""
        successes = [(1001, 9351560090, 'pers', '12/15/2025', 'Success')]
        fails = [(1002, 9351370359, 'pers', '12/15/2025', 'Fail')]
        
        mock_write_report = mocker.patch(f"{MODULE_NAME}.write_report")

        write_report_file(script_data, successes, fails)

        assert mock_write_report.call_count == 2

    def test_write_report_file_only_successes(self, script_data, mocker):
        """Test write_report_file with only successes"""
        successes = [(1001, 9351560090, 'pers', '12/15/2025', 'Success')]
        fails = []
        
        mock_write_report = mocker.patch(f"{MODULE_NAME}.write_report")

        write_report_file(script_data, successes, fails)

        mock_write_report.assert_called_once()


class TestSendNotificationEmail:
    """Test the send_notification_email function"""

    def test_send_notification_email_with_fails(self, script_data, mocker):
        """Test send_notification_email when there are failures"""
        fails = [(1001, 9351560090, 'pers', '12/15/2025', 'Fail')]
        
        mock_send_email = mocker.patch(
            f"{MODULE_NAME}.send_email",
            return_value=(True, "Email Sent")
        )

        send_notification_email(script_data, fails)

        mock_send_email.assert_called_once()

    def test_send_notification_email_no_fails(self, script_data, mocker):
        """Test send_notification_email when there are no failures"""
        fails = []
        
        mock_send_email = mocker.patch(f"{MODULE_NAME}.send_email")

        send_notification_email(script_data, fails)

        mock_send_email.assert_not_called()


class TestSendEmail:
    """Test the send_email function"""

    def test_send_email_success(self, script_data, mocker):
        """Test successful email sending"""
        recipients = ["test@firsttechfed.com"]
        
        mock_generate_content = mocker.patch(
            f"{MODULE_NAME}.generate_email_content",
            return_value="<html>Test email</html>"
        )
        mock_generate_message = mocker.patch(f"{MODULE_NAME}.generate_email_message")
        mock_send_smtp = mocker.patch(f"{MODULE_NAME}.send_smtp_request")
        mocker.patch(f"{MODULE_NAME}.is_local_environment", return_value=False)
        mocker.patch(f"{MODULE_NAME}.send_email_enabled", return_value=True)

        successful, message = send_email(script_data, recipients)

        assert successful is True
        assert message == "Email Sent"
        mock_send_smtp.assert_called_once()

    def test_send_email_disabled(self, script_data_send_email_n, mocker):
        """Test email sending when disabled"""
        recipients = ["test@firsttechfed.com"]
        
        mocker.patch(f"{MODULE_NAME}.generate_email_content", return_value="<html>Test</html>")
        mocker.patch(f"{MODULE_NAME}.generate_email_message")
        mocker.patch(f"{MODULE_NAME}.is_local_environment", return_value=False)

        successful, message = send_email(script_data_send_email_n, recipients)

        assert successful is False
        assert message == "Email Send Disabled"

    def test_send_email_no_recipients(self, script_data, mocker):
        """Test email sending with no recipients"""
        recipients = []

        successful, message = send_email(script_data, recipients)

        assert successful is False
        assert message == "No email recipients"


class TestEmailUtilities:
    """Test email utility functions"""

    def test_generate_email_message(self):
        """Test generate_email_message function"""
        from_addr = "test@firsttechfed.com"
        to_addr = "recipient@firsttechfed.com"
        content = "<html>Test content</html>"

        message = generate_email_message(from_addr, to_addr, content)

        assert message["Subject"] == "Statement Delivery Method Update Alert"
        assert message["From"] == f"First Tech Federal Credit Union <{from_addr}>"
        assert message["To"] == to_addr

    def test_generate_email_content(self, script_data):
        """Test generate_email_content function"""
        content = generate_email_content(script_data)
        
        assert "Statement Delivery Method Update Alert" in content
        assert "Run Date:" in content
        assert "Processing Time:" in content

    def test_send_email_enabled_true(self, script_data):
        """Test send_email_enabled returns True"""
        assert send_email_enabled(script_data.apwx) is True

    def test_send_email_enabled_false(self, script_data_send_email_n):
        """Test send_email_enabled returns False"""
        assert send_email_enabled(script_data_send_email_n.apwx) is False

    def test_is_local_environment_true(self, mocker):
        """Test is_local_environment returns True when AW_HOME not set"""
        mocker.patch.dict(os.environ, {}, clear=True)
        assert is_local_environment() is True

    def test_is_local_environment_false(self, mocker):
        """Test is_local_environment returns False when AW_HOME is set"""
        mocker.patch.dict(os.environ, {"AW_HOME": "/some/path"})
        assert is_local_environment() is False


class TestWriteReport:
    """Test the write_report function"""

    def test_write_report_create_new_file(self, tmp_path):
        """Test write_report creating a new file"""
        path = tmp_path / "test_output.csv"
        records = [(1001, 9351560090, 'pers', '12/15/2025', 'Success')]

        result = write_report(path, records, 'w')

        assert result is True
        assert path.exists()
        
        with open(path, 'r') as f:
            content = f.read()
            assert 'ENTITY_NBR' in content
            assert '1001' in content

    def test_write_report_append_to_file(self, tmp_path):
        """Test write_report appending to existing file"""
        path = tmp_path / "test_output.csv"
        
        # Create initial file
        records1 = [(1001, 9351560090, 'pers', '12/15/2025', 'Success')]
        write_report(path, records1, 'w')
        
        # Append to file
        records2 = [(1002, 9351370359, 'pers', '12/15/2025', 'Fail')]
        result = write_report(path, records2, 'a+')

        assert result is True
        
        with open(path, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 3  # header + 2 records


class TestDatabaseUtilities:
    """Test database utility functions"""

    def test_execute_sql_select_success(self, mocker):
        """Test successful SQL select execution"""
        # Mock database connection and cursor
        mock_cursor = Mock()
        mock_cursor.description = [("ENTITY_NUMBER",), ("ACCTNBR",)]
        mock_cursor.execute = Mock()
        mock_cursor.fetchall = Mock(return_value=[(1001, 9351560090)])
        
        mock_conn = Mock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=None)

        result = execute_sql_select(mock_conn, "SELECT * FROM test")

        assert len(result) == 1
        assert result[0]["ENTITY_NUMBER"] == 1001
        assert result[0]["ACCTNBR"] == 9351560090

    def test_execute_sql_select_with_params(self, mocker):
        """Test SQL select execution with parameters"""
        mock_cursor = Mock()
        mock_cursor.description = [("ENTITY_NUMBER",)]
        mock_cursor.execute = Mock()
        mock_cursor.fetchall = Mock(return_value=[(1001,)])
        
        mock_conn = Mock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=None)

        params = {"entity_id": 1001}
        result = execute_sql_select(mock_conn, "SELECT * FROM test WHERE id = :entity_id", params)

        mock_cursor.execute.assert_called_once_with("SELECT * FROM test WHERE id = :entity_id", params)

    def test_execute_sql_select_exception(self, mocker):
        """Test SQL select execution with exception"""
        mock_cursor = Mock()
        mock_cursor.execute = Mock(side_effect=Exception("Database error"))
        
        mock_conn = Mock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=None)

        with pytest.raises(Exception, match="SQL error = Database error"):
            execute_sql_select(mock_conn, "INVALID SQL")

    def test_dna_db_connect_rptonly_n(self, script_data, mocker):
        """Test database connection with RPTONLY_YN = 'N'"""
        mock_dbh = Mock()
        mock_apwx_db_connect = mocker.patch.object(script_data.apwx, 'db_connect', return_value=mock_dbh)
        
        script_data.apwx.args.RPTONLY_YN = 'N'

        result = dna_db_connect(script_data.apwx)

        assert result.autocommit is True
        mock_apwx_db_connect.assert_called_once_with(autocommit=False)

    def test_dna_db_connect_rptonly_y(self, script_data, mocker):
        """Test database connection with RPTONLY_YN = 'Y'"""
        mock_dbh = Mock()
        mock_apwx_db_connect = mocker.patch.object(script_data.apwx, 'db_connect', return_value=mock_dbh)
        
        script_data.apwx.args.RPTONLY_YN = 'Y'

        result = dna_db_connect(script_data.apwx)

        assert result.autocommit is False
        mock_apwx_db_connect.assert_called_once_with(autocommit=False)


class TestConfigurationUtilities:
    """Test configuration utility functions"""

    def test_get_config(self, script_data):
        """Test get_config function"""
        config = get_config(script_data.apwx)
        
        assert "sql_queries" in config
        assert "template_directory" in config
        assert "template_file" in config

    def test_get_email_template(self, script_data):
        """Test get_email_template function"""
        config = get_config(script_data.apwx)
        template = get_email_template(config)
        
        # Test that template can render with sample data
        rendered = template.render(run_date="12-15-2025", current_time="10:30:00")
        assert "12-15-2025" in rendered
        assert "10:30:00" in rendered


class TestInitialize:
    """Test the initialize function"""

    def test_initialize(self, script_data, mocker):
        """Test initialize function"""
        mock_get_config = mocker.patch(f"{MODULE_NAME}.get_config", return_value={"test": "config"})
        mock_dna_db_connect = mocker.patch(f"{MODULE_NAME}.dna_db_connect", return_value=Mock())
        mock_get_email_template = mocker.patch(f"{MODULE_NAME}.get_email_template", return_value=Mock())

        result = initialize(script_data.apwx)

        assert result.apwx == script_data.apwx
        assert result.dbh is not None
        assert result.config is not None
        assert result.email_template is not None
        
        mock_get_config.assert_called_once()
        mock_dna_db_connect.assert_called_once()
        mock_get_email_template.assert_called_once()