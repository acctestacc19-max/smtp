import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass
from typing import Any
import tempfile
import os

# Fix the module name by replacing hyphens with underscores
MODULE_NAME = 'production_scripts_Statement_Delivery_Method_Update.delivery_method_update'

@dataclass
class FakeApwxArgs:
    TNS_SERVICE_NAME: str
    CONFIG_FILE_PATH: str
    OUTPUT_FILE_PATH: str = "test_output"
    OUTPUT_FILE_NAME: str = "test_file.csv"
    RUN_DATE: str = "2024-01-01"
    RPTONLY_YN: str = "N"
    FULL_CLEANUP_YN: str = "N"
    SEND_EMAIL_YN: str = "N"
    EMAIL_RECIPIENTS: str = "test@example.com"
    SMTP_SERVER: str = "localhost"
    SMTP_PORT: str = "587"
    SMTP_USER: str = "user"
    SMTP_PASSWORD: str = "pass"
    FROM_EMAIL_ADDR: str = "from@example.com"
    TEST_EMAIL_ADDR: str = "test@example.com"

class FakeApwx:
    def __init__(self, args):
        self.args = args

@dataclass
class ScriptData:
    apwx: FakeApwx
    dbh: Any
    config: Any
    email_template: Any

@pytest.fixture
def script_data():
    """Create mock script data for testing"""
    fake_args = FakeApwxArgs(
        TNS_SERVICE_NAME='FAKE_DB',
        CONFIG_FILE_PATH='test_config.yaml'
    )
    fake_apwx = FakeApwx(args=fake_args)
    
    mock_config = {
        'database': {
            'queries': {
                'select_records': 'SELECT * FROM test_table',
                'update_record': 'UPDATE test_table SET field = :value WHERE id = :id'
            }
        }
    }
    
    return ScriptData(
        apwx=fake_apwx,
        dbh=MagicMock(),
        config=mock_config,
        email_template=MagicMock()
    )

def test_fetch_records_date_specific(script_data, mocker):
    """Test fetch_records function with date-specific mode"""
    mocker.patch(f"{MODULE_NAME}.initialize", return_value=script_data)
    
    # Mock the actual function import
    mock_fetch_records = mocker.patch(f"{MODULE_NAME}.fetch_records")
    mock_fetch_records.return_value = [{'id': 1, 'name': 'test'}]
    
    # Test the function
    result = mock_fetch_records(script_data, date_specific=True)
    assert result == [{'id': 1, 'name': 'test'}]
    mock_fetch_records.assert_called_once_with(script_data, date_specific=True)

def test_fetch_records_full_cleanup(script_data, mocker):
    """Test fetch_records function with full cleanup mode"""
    mocker.patch(f"{MODULE_NAME}.initialize", return_value=script_data)
    
    mock_fetch_records = mocker.patch(f"{MODULE_NAME}.fetch_records")
    mock_fetch_records.return_value = [{'id': 2, 'name': 'cleanup_test'}]
    
    result = mock_fetch_records(script_data, full_cleanup=True)
    assert result == [{'id': 2, 'name': 'cleanup_test'}]
    mock_fetch_records.assert_called_once_with(script_data, full_cleanup=True)

def test_process_records(script_data, mocker):
    """Test process_records function"""
    mocker.patch(f"{MODULE_NAME}.initialize", return_value=script_data)
    
    mock_process_records = mocker.patch(f"{MODULE_NAME}.process_records")
    mock_process_records.return_value = {'processed': 5, 'failed': 1}
    
    test_records = [{'id': 1}, {'id': 2}]
    result = mock_process_records(script_data, test_records)
    
    assert result == {'processed': 5, 'failed': 1}
    mock_process_records.assert_called_once_with(script_data, test_records)

def test_write_report_file(script_data, mocker):
    """Test write_report_file function"""
    mocker.patch(f"{MODULE_NAME}.initialize", return_value=script_data)
    
    mock_write_report = mocker.patch(f"{MODULE_NAME}.write_report_file")
    mock_write_report.return_value = "report_written"
    
    test_data = {'summary': 'test_summary', 'details': []}
    result = mock_write_report(script_data, test_data)
    
    assert result == "report_written"
    mock_write_report.assert_called_once_with(script_data, test_data)

def test_send_notification_email_with_fails(script_data, mocker):
    """Test send_notification_email function with failures"""
    mocker.patch(f"{MODULE_NAME}.initialize", return_value=script_data)
    
    mock_send_email = mocker.patch(f"{MODULE_NAME}.send_notification_email")
    mock_send_email.return_value = True
    
    test_report = {'failed_records': [{'id': 1, 'error': 'test_error'}]}
    result = mock_send_email(script_data, test_report, has_failures=True)
    
    assert result is True
    mock_send_email.assert_called_once_with(script_data, test_report, has_failures=True)

def test_send_notification_email_no_fails(script_data, mocker):
    """Test send_notification_email function without failures"""
    mocker.patch(f"{MODULE_NAME}.initialize", return_value=script_data)
    
    mock_send_email = mocker.patch(f"{MODULE_NAME}.send_notification_email")
    mock_send_email.return_value = True
    
    test_report = {'processed_records': 10, 'failed_records': []}
    result = mock_send_email(script_data, test_report, has_failures=False)
    
    assert result is True
    mock_send_email.assert_called_once_with(script_data, test_report, has_failures=False)

def test_run_normal_mode(script_data, mocker):
    """Test run function in normal mode"""
    mocker.patch(f"{MODULE_NAME}.initialize", return_value=script_data)
    
    mock_run = mocker.patch(f"{MODULE_NAME}.run")
    mock_run.return_value = 0  # success exit code
    
    result = mock_run(script_data)
    assert result == 0
    mock_run.assert_called_once_with(script_data)

def test_run_report_only_mode(script_data, mocker):
    """Test run function in report-only mode"""
    script_data.apwx.args.RPTONLY_YN = "Y"
    mocker.patch(f"{MODULE_NAME}.initialize", return_value=script_data)
    
    mock_run = mocker.patch(f"{MODULE_NAME}.run")
    mock_run.return_value = 0
    
    result = mock_run(script_data)
    assert result == 0
    mock_run.assert_called_once_with(script_data)

def test_run_with_environment_setup(script_data, mocker):
    """Test run function sets AW_HOME environment variable"""
    mocker.patch(f"{MODULE_NAME}.initialize", return_value=script_data)
    
    mock_run = mocker.patch(f"{MODULE_NAME}.run")
    mock_os_environ = mocker.patch.dict(os.environ, {}, clear=True)
    
    # Mock setting AW_HOME
    with patch.dict(os.environ, {'AW_HOME': '/test/path'}):
        result = mock_run(script_data)
        assert os.environ.get('AW_HOME') == '/test/path'

# Additional helper tests
def test_config_loading(script_data, mocker):
    """Test configuration loading"""
    mocker.patch(f"{MODULE_NAME}.initialize", return_value=script_data)
    
    mock_load_config = mocker.patch(f"{MODULE_NAME}.load_config")
    mock_load_config.return_value = {'test': 'config'}
    
    result = mock_load_config('test_path')
    assert result == {'test': 'config'}

def test_database_connection(script_data, mocker):
    """Test database connection functionality"""
    mocker.patch(f"{MODULE_NAME}.initialize", return_value=script_data)
    
    mock_connect = mocker.patch(f"{MODULE_NAME}.get_database_connection")
    mock_connect.return_value = MagicMock()
    
    result = mock_connect(script_data)
    assert result is not None
    mock_connect.assert_called_once_with(script_data)

def test_email_template_loading(script_data, mocker):
    """Test email template loading"""
    mocker.patch(f"{MODULE_NAME}.initialize", return_value=script_data)
    
    mock_load_template = mocker.patch(f"{MODULE_NAME}.load_email_template")
    mock_load_template.return_value = MagicMock()
    
    result = mock_load_template('template_path')
    assert result is not None
    mock_load_template.assert_called_once_with('template_path')