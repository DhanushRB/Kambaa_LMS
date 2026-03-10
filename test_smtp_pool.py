import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from smtp_connection import SMTPConnectionManager

class TestSMTPReuse(unittest.TestCase):
    def setUp(self):
        # Reset the singleton state before each test
        SMTPConnectionManager._connection = None
        SMTPConnectionManager._config_checksum = None

    def test_connection_reuse(self):
        with patch.object(SMTPConnectionManager, '_create_new_connection') as mock_create:
            # Setup mock
            mock_server = MagicMock()
            mock_server.noop.return_value = (250, b'OK')
            mock_create.return_value = (mock_server, None)
            
            # Define connection params
            params = {
                'host': 'smtp.example.com',
                'port': 587,
                'username': 'user',
                'password': 'pass',
                'use_tls': True
            }
            
            # First call - should create new connection
            conn1, error = SMTPConnectionManager.get_connection(**params)
            self.assertIsNone(error)
            self.assertEqual(mock_create.call_count, 1)
            
            # Second call with same params - should reuse
            conn2, error = SMTPConnectionManager.get_connection(**params)
            self.assertIsNone(error)
            self.assertEqual(mock_create.call_count, 1) # Still 1
            self.assertEqual(conn1, conn2)
            
            # Third call with different params - should create new
            params['port'] = 465
            conn3, error = SMTPConnectionManager.get_connection(**params)
            self.assertIsNone(error)
            self.assertEqual(mock_create.call_count, 2)
            self.assertNotEqual(conn1, conn3)

    def test_reconnection_on_failure(self):
        with patch.object(SMTPConnectionManager, '_create_new_connection') as mock_create:
            # Setup mock
            mock_server = MagicMock()
            mock_server.noop.return_value = (250, b'OK')
            mock_create.return_value = (mock_server, None)
            
            params = {
                'host': 'smtp.example.com',
                'port': 587,
                'username': 'user',
                'password': 'pass'
            }
            
            # Connect first
            SMTPConnectionManager.get_connection(**params)
            self.assertEqual(mock_create.call_count, 1)
            
            # Simulate connection loss
            mock_server.noop.side_effect = Exception("Connection lost")
            
            # Next call should reconnect
            SMTPConnectionManager.get_connection(**params)
            self.assertEqual(mock_create.call_count, 2)

if __name__ == '__main__':
    unittest.main()
