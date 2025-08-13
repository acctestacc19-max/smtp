import unittest
from unittest.mock import Mock, patch, MagicMock, mock_open
import datetime
import os
import sys
from pathlib import Path

# Mock external dependencies before importing the main module
sys.modules['ftfcu_appworx'] = Mock()
sys.modules['oracledb'] = Mock()
sys.modules['jinja2'] = Mock()
sys.modules['yaml'] = Mock()

# Mock the specific classes and functions we need
mock_apwx = Mock()
mock_jobtime = Mock()
mock_connection = Mock()
mock_environment = Mock()
mock_filesystemloader = Mock()

# Set up the mocked modules
sys.modules['ftfcu_appworx'].Apwx = Mock(return_value=mock_apwx)
sys.modules['ftfcu_appworx'].JobTime = Mock(return_value=mock_jobtime)
sys.modules['oracledb'].Connection = mock_connection
sys.modules['jinja2'].Environment = mock_environment
sys.modules['jinja2'].FileSystemLoader = mock_filesystemloader
sys.modules['yaml'].safe_load = Mock()

# Now import the module under test
import delivery_update_method as dum
from delivery_update_method import AppWorxEnum, ScriptData


class TestDeliveryUpdateMethod(unittest.TestCase):
    """Test cases for delivery_update_method.py"""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.mock_apwx = Mock()
        self.mock_dbh = Mock()
        self.mock_config = {
            "sql_queries": {
                "get_records": "SELECT * FROM table {{close_date_join}}",
                "update_pers_stdl": "UPDATE persuserfield SET field=value WHERE persnbr=:1",
                "update_org_stdl": "UPDATE orguserfield SET field=value WHERE orgnbr=:1"
            },
            "join_fragments": {
                "date_specific": "WHERE close_date = '{{run_date}}'",
                "full_cleanup": "WHERE 1=1"
            },
            "template_directory": "templates",
            "template_file": "email_template.html"
        }
        self.mock_email_template = Mock()
        
        # Set up proper argument values to avoid format validation errors
        self.mock_apwx.args = Mock()
        self.mock_apwx.args.TNS_SERVICE_NAME = "production_db"
        self.mock_apwx.args.CONFIG_FILE_PATH = "/path/to/config.yml"
        self.mock_apwx.args.OUTPUT_FILE_PATH = "/path/to/output"
        self.mock_apwx.args.OUTPUT_FILE_NAME = "report.csv"
        self.mock_apwx.args.RUN_DATE = "12-25-2023"
        self.mock_apwx.args.RPTONLY_YN = "Y"
        self.mock_apwx.args.FULL_CLEANUP_YN = "N"
        self.mock_apwx.args.SEND_EMAIL_YN = "Y"
        self.mock_apwx.args.EMAIL_RECIPIENTS = "test@firsttechfed.com"
        self.mock_apwx.args.SMTP_SERVER = "smtp.server.com"
        self.mock_apwx.args.SMTP_PORT = 587
        self.mock_apwx.args.SMTP_USER = "smtp_user"
        self.mock_apwx.args.SMTP_PASSWORD = "password"
        self.mock_apwx.args.FROM_EMAIL_ADDR = "sender@firsttechfed.com"
        self.mock_apwx.args.TEST_EMAIL_ADDR = "test@firsttechfed.com"

    def test_fetch_records_date_specific(self):
        """Test fetch_records with a specific run date"""
        script_data = ScriptData(
            apwx=self.mock_apwx,
            dbh=self.mock_dbh,
            config=self.mock_config,
            email_template=self.mock_email_template
        )
        
        # Set up for date-specific run
        self.mock_apwx.args.FULL_CLEANUP_YN = "N"
        self.mock_apwx.args.RUN_DATE = "12-25-2023"
        
        mock_records = [
            {'ENTITY_TYPE': 'pers', 'ENTITY_NUMBER': 1},
            {'ENTITY_TYPE': 'org', 'ENTITY_NUMBER': 2}
        ]
        
        with patch('delivery_update_method.execute_sql_select', return_value=mock_records):
            pers_records, org_records = dum.fetch_records(script_data)
            
        self.assertEqual(len(pers_records), 1)
        self.assertEqual(len(org_records), 1)

    def test_fetch_records_full_cleanup(self):
        """Test fetch_records with full cleanup mode"""
        script_data = ScriptData(
            apwx=self.mock_apwx,
            dbh=self.mock_dbh,
            config=self.mock_config,
            email_template=self.mock_email_template
        )
        
        # Set up for full cleanup
        self.mock_apwx.args.FULL_CLEANUP_YN = "Y"
        self.mock_apwx.args.RUN_DATE = None
        
        mock_records = [
            {'ENTITY_TYPE': 'pers', 'ENTITY_NUMBER': 1},
            {'ENTITY_TYPE': 'org', 'ENTITY_NUMBER': 2}
        ]
        
        with patch('delivery_update_method.execute_sql_select', return_value=mock_records):
            pers_records, org_records = dum.fetch_records(script_data)
            
        self.assertEqual(len(pers_records), 1)
        self.assertEqual(len(org_records), 1)

    def test_fetch_records_parameter_validation_errors(self):
        """Test parameter validation in fetch_records"""
        script_data = ScriptData(
            apwx=self.mock_apwx,
            dbh=self.mock_dbh,
            config=self.mock_config,
            email_template=self.mock_email_template
        )
        
        # Test mutually exclusive parameters
        self.mock_apwx.args.FULL_CLEANUP_YN = "Y"
        self.mock_apwx.args.RUN_DATE = "12-25-2023"
        
        with self.assertRaises(Exception) as context:
            dum.fetch_records(script_data)
        
        self.assertIn("mutually exclusive", str(context.exception))
        
        # Test missing parameters
        self.mock_apwx.args.FULL_CLEANUP_YN = "N"
        self.mock_apwx.args.RUN_DATE = None
        
        with self.assertRaises(Exception) as context:
            dum.fetch_records(script_data)
        
        self.assertIn("no RUN_DATE parameter", str(context.exception))

    def test_process_records(self):
        """Test process_records function"""
        script_data = ScriptData(
            apwx=self.mock_apwx,
            dbh=self.mock_dbh,
            config=self.mock_config,
            email_template=self.mock_email_template
        )
        
        pers_records = [{'ENTITY_NUMBER': 1, 'ACCTNBR': '123', 'ENTITY_TYPE': 'pers', 'CLOSE_DATE': '2023-12-25'}]
        org_records = [{'ENTITY_NUMBER': 2, 'ACCTNBR': '456', 'ENTITY_TYPE': 'org', 'CLOSE_DATE': '2023-12-25'}]
        
        with patch('pathlib.Path.exists', return_value=False), \
             patch('delivery_update_method.update_stdl_userfield', return_value=([], [])):
            successes, fails = dum.process_records(script_data, pers_records, org_records)
            
        self.assertIsInstance(successes, list)
        self.assertIsInstance(fails, list)

    def test_process_records_file_exists_error(self):
        """Test process_records when output file already exists"""
        script_data = ScriptData(
            apwx=self.mock_apwx,
            dbh=self.mock_dbh,
            config=self.mock_config,
            email_template=self.mock_email_template
        )
        
        pers_records = []
        org_records = []
        
        with patch('pathlib.Path.exists', return_value=True):
            with self.assertRaises(FileExistsError):
                dum.process_records(script_data, pers_records, org_records)

    def test_update_stdl_userfield_with_errors(self):
        """Test update_stdl_userfield with batch errors"""
        script_data = ScriptData(
            apwx=self.mock_apwx,
            dbh=self.mock_dbh,
            config=self.mock_config,
            email_template=self.mock_email_template
        )
        
        records = [{'ENTITY_NUMBER': 123, 'ACCTNBR': '456', 'ENTITY_TYPE': 'pers', 'CLOSE_DATE': '2023-12-25'}]
        
        # Mock cursor with batch errors
        mock_cursor = Mock()
        mock_error = Mock()
        mock_error.offset = 0
        mock_error.message = "Test error"
        mock_cursor.getbatcherrors.return_value = [mock_error]
        mock_cursor.rowcount = 0
        
        self.mock_dbh.cursor.return_value = mock_cursor
        self.mock_apwx.args.RPTONLY_YN = "Y"
        
        successes, fails = dum.update_stdl_userfield(script_data, records, 'persuserfield', 'persnbr')
        
        self.assertIsInstance(successes, list)
        self.assertIsInstance(fails, list)
        self.assertEqual(len(fails), 1)  # Should now properly detect the failure

    def test_update_stdl_userfield_empty_records(self):
        """Test update_stdl_userfield with empty records"""
        script_data = ScriptData(
            apwx=self.mock_apwx,
            dbh=self.mock_dbh,
            config=self.mock_config,
            email_template=self.mock_email_template
        )
        
        successes, fails = dum.update_stdl_userfield(script_data, [], 'persuserfield', 'persnbr')
        
        self.assertEqual(successes, [])
        self.assertEqual(fails, [])

    def test_send_notification_email_with_fails(self):
        """Test send_notification_email when there are failures"""
        script_data = ScriptData(
            apwx=self.mock_apwx,
            dbh=self.mock_dbh,
            config=self.mock_config,
            email_template=self.mock_email_template
        )
        
        fails = [('123', '456', 'pers', '2023-12-25', 'Fail')]
        self.mock_apwx.args.EMAIL_RECIPIENTS = "test@firsttechfed.com"
        
        with patch('delivery_update_method.send_email', return_value=(True, "Email sent")):
            # This should not raise an exception
            dum.send_notification_email(script_data, fails)

    def test_send_notification_email_with_errors(self):
        """Test send_notification_email with various error conditions"""
        script_data = ScriptData(
            apwx=self.mock_apwx,
            dbh=self.mock_dbh,
            config=self.mock_config,
            email_template=self.mock_email_template
        )
        
        fails = [('123', '456', 'pers', '2023-12-25', 'Fail')]
        
        # Test with no email recipients
        self.mock_apwx.args.EMAIL_RECIPIENTS = None
        self.mock_apwx.args.SEND_EMAIL_YN = "Y"
        
        with patch('delivery_update_method.send_email_enabled', return_value=True):
            # Should not raise an exception
            dum.send_notification_email(script_data, fails)

    def test_write_report_file(self):
        """Test write_report_file function"""
        script_data = ScriptData(
            apwx=self.mock_apwx,
            dbh=self.mock_dbh,
            config=self.mock_config,
            email_template=self.mock_email_template
        )
        
        successes = [('123', '456', 'pers', '2023-12-25', 'Success')]
        fails = [('789', '012', 'org', '2023-12-25', 'Fail')]
        
        with patch('delivery_update_method.write_report') as mock_write:
            dum.write_report_file(script_data, successes, fails)
            # Should be called twice - once for successes, once for fails
            self.assertEqual(mock_write.call_count, 2)

    def test_run_normal_mode(self):
        """Test the main run function with environment setup"""
        with patch('delivery_update_method.initialize') as mock_init, \
             patch('delivery_update_method.fetch_records') as mock_fetch, \
             patch('delivery_update_method.process_records') as mock_process, \
             patch('delivery_update_method.write_report_file') as mock_write, \
             patch('delivery_update_method.send_notification_email') as mock_email:
            
            script_data = ScriptData(
                apwx=self.mock_apwx,
                dbh=self.mock_dbh,
                config=self.mock_config,
                email_template=self.mock_email_template
            )
            
            mock_init.return_value = script_data
            mock_fetch.return_value = ([], [])
            mock_process.return_value = ([], [])
            
            result = dum.run(self.mock_apwx)
            
            self.assertTrue(result)
            # Verify AW_HOME environment variable is set
            self.assertEqual(os.environ.get("AW_HOME"), "sai")

    def test_parse_args_with_valid_values(self):
        """Test parse_args with valid parameter values"""
        mock_apwx = Mock()
        mock_parser = Mock()
        mock_apwx.parser = mock_parser
        
        # Test that parse_args configures the parser correctly
        result = dum.parse_args(mock_apwx)
        
        # Verify parser.add_arg was called for all required parameters
        self.assertTrue(mock_parser.add_arg.called)
        # Verify parse_args was called
        self.assertTrue(mock_apwx.parse_args.called)

    def test_dna_db_connect(self):
        """Test database connection setup"""
        self.mock_apwx.db_connect.return_value = self.mock_dbh
        
        # Test report-only mode
        self.mock_apwx.args.RPTONLY_YN = "Y"
        dbh = dum.dna_db_connect(self.mock_apwx)
        self.assertFalse(dbh.autocommit)
        
        # Test update mode
        self.mock_apwx.args.RPTONLY_YN = "N"
        dbh = dum.dna_db_connect(self.mock_apwx)
        self.assertTrue(dbh.autocommit)

    def test_get_config(self):
        """Test configuration file loading"""
        mock_yaml_content = {"test": "config"}
        
        with patch('builtins.open', mock_open(read_data="test: config")), \
             patch('yaml.safe_load', return_value=mock_yaml_content):
            config = dum.get_config(self.mock_apwx)
            self.assertEqual(config, mock_yaml_content)

    def test_get_email_template(self):
        """Test email template loading"""
        mock_template = Mock()
        
        with patch('os.path.dirname'), \
             patch('os.path.abspath'), \
             patch('os.path.join'), \
             patch('delivery_update_method.FileSystemLoader'), \
             patch('delivery_update_method.Environment') as mock_env:
            
            mock_env_instance = Mock()
            mock_env_instance.get_template.return_value = mock_template
            mock_env.return_value = mock_env_instance
            
            template = dum.get_email_template(self.mock_config)
            self.assertEqual(template, mock_template)

    def test_execute_sql_select(self):
        """Test SQL execution function"""
        mock_cursor = Mock()
        mock_cursor.description = [('COL1',), ('COL2',)]
        mock_cursor.fetchall.return_value = [('val1', 'val2')]
        
        # Set up context manager properly
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_cursor)
        mock_context.__exit__ = Mock(return_value=None)
        self.mock_dbh.cursor.return_value = mock_context
        
        result = dum.execute_sql_select(self.mock_dbh, "SELECT * FROM table")
        
        self.assertIsInstance(result, list)
        mock_cursor.execute.assert_called_once()

    def test_execute_sql_select_with_exception(self):
        """Test SQL execution with exception"""
        mock_cursor = Mock()
        mock_cursor.execute.side_effect = Exception("SQL error")
        
        # Set up context manager properly
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_cursor)
        mock_context.__exit__ = Mock(return_value=None)
        self.mock_dbh.cursor.return_value = mock_context
        
        with self.assertRaises(Exception) as context:
            dum.execute_sql_select(self.mock_dbh, "SELECT * FROM table")
        
        self.assertIn("SQL error", str(context.exception))

    def test_send_email_local_environment(self):
        """Test email sending in local environment"""
        script_data = ScriptData(
            apwx=self.mock_apwx,
            dbh=self.mock_dbh,
            config=self.mock_config,
            email_template=self.mock_email_template
        )
        
        # Mock email template to return a string
        self.mock_email_template.render.return_value = "Test email content"
        
        with patch('delivery_update_method.is_local_environment', return_value=True):
            success, message = dum.send_email(script_data, ["test@firsttechfed.com"])
            self.assertFalse(success)
            self.assertEqual(message, "Email Send Disabled")

    def test_send_email_no_recipients(self):
        """Test email sending with no recipients"""
        script_data = ScriptData(
            apwx=self.mock_apwx,
            dbh=self.mock_dbh,
            config=self.mock_config,
            email_template=self.mock_email_template
        )
        
        # Mock email template to return a string
        self.mock_email_template.render.return_value = "Test email content"
        
        success, message = dum.send_email(script_data, [])
        self.assertFalse(success)
        self.assertEqual(message, "No email recipients")

    def test_generate_email_content(self):
        """Test email content generation"""
        script_data = ScriptData(
            apwx=self.mock_apwx,
            dbh=self.mock_dbh,
            config=self.mock_config,
            email_template=self.mock_email_template
        )
        
        self.mock_email_template.render.return_value = "Test email content"
        
        content = dum.generate_email_content(script_data)
        
        self.assertEqual(content, "Test email content")
        self.mock_email_template.render.assert_called_once()

    def test_generate_email_message(self):
        """Test email message generation"""
        from_addr = "sender@firsttechfed.com"
        to_addr = "recipient@firsttechfed.com"
        content = "Test email content"
        
        message = dum.generate_email_message(from_addr, to_addr, content)
        
        self.assertEqual(message["Subject"], "Statement Delivery Method Update Alert")
        self.assertEqual(message["From"], f"First Tech Federal Credit Union <{from_addr}>")
        self.assertEqual(message["To"], to_addr)

    def test_is_local_environment(self):
        """Test local environment detection"""
        # Test when AW_HOME is not set
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(dum.is_local_environment())
        
        # Test when AW_HOME is set
        with patch.dict(os.environ, {'AW_HOME': 'some_value'}):
            self.assertFalse(dum.is_local_environment())

    def test_send_email_enabled(self):
        """Test email sending enablement check"""
        self.mock_apwx.args.SEND_EMAIL_YN = "Y"
        self.assertTrue(dum.send_email_enabled(self.mock_apwx))
        
        self.mock_apwx.args.SEND_EMAIL_YN = "N"
        self.assertFalse(dum.send_email_enabled(self.mock_apwx))

    def test_write_report(self):
        """Test write_report function"""
        test_path = "/tmp/test_report.csv"
        records = [
            ('123', '456', 'pers', '2023-12-25', 'Success'),
            ('789', '012', 'org', '2023-12-25', 'Fail')
        ]
        
        with patch('builtins.open', mock_open()) as mock_file:
            result = dum.write_report(test_path, records, 'w')
            self.assertTrue(result)
            # Verify the file was opened with correct parameters
            mock_file.assert_called_once_with(test_path, 'w', newline='')


if __name__ == '__main__':
    unittest.main()