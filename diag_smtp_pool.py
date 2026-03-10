import logging
import sys
import os
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from smtp_connection import SMTPConnectionManager

# Setup basic logging to see what's happening
logging.basicConfig(level=logging.DEBUG)

def run_diagnostic():
    print("--- SMTP Connection Pool Diagnostic ---")
    
    # Reset state
    SMTPConnectionManager._connection = None
    SMTPConnectionManager._config_checksum = None
    
    with patch('smtplib.SMTP') as mock_smtp:
        with patch('smtplib.SMTP_SSL') as mock_smtp_ssl:
            mock_instance = mock_smtp.return_value
            mock_instance.noop.return_value = (250, b'OK')
            
            params = {
                'host': 'smtp.diag.com',
                'port': 587,
                'username': 'diag_user',
                'password': 'diag_password',
                'use_tls': True
            }
            
            print("1. First connection attempt...")
            conn1, error = SMTPConnectionManager.get_connection(**params)
            
            checksum1 = SMTPConnectionManager._config_checksum
            print(f"   - Connection 1: {conn1}")
            print(f"   - Checksum 1: {checksum1}")
            
            if conn1 is None:
                print(f"FAILED: Connection is None. Error: {error}")
                return

            print("2. Second connection attempt (same params)...")
            conn2, error = SMTPConnectionManager.get_connection(**params)
            
            checksum2 = SMTPConnectionManager._config_checksum
            print(f"   - Connection 2: {conn2}")
            print(f"   - Checksum 2: {checksum2}")
            
            if conn1 is conn2 and checksum1 == checksum2:
                print("SUCCESS: Connection and Checksum reused!")
            else:
                print("FAILED: Connection or Checksum mismatch")

            print("3. Third connection attempt (different params)...")
            params['port'] = 465
            conn3, error = SMTPConnectionManager.get_connection(**params)
            
            checksum3 = SMTPConnectionManager._config_checksum
            print(f"   - Connection 3: {conn3}")
            print(f"   - Checksum 3: {checksum3}")
            
            if conn3 is not conn1 and checksum3 != checksum1:
                print("SUCCESS: New connection and checksum for different params!")
            else:
                print("FAILED: Failed to create new connection for different params")

if __name__ == "__main__":
    run_diagnostic()
