import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

from unittest.mock import MagicMock, patch
import smtplib
import ssl
from smtp_connection import get_smtp_connection

def test_implicit_ssl_logic():
    print("Testing implicit SSL logic (Port 465)...")
    with patch("smtplib.SMTP_SSL") as mock_smtp_ssl:
        mock_server = MagicMock()
        mock_smtp_ssl.return_value = mock_server
        
        server, error = get_smtp_connection(
            "smtp.example.com", 465, "user", "pass", use_tls=False, use_ssl=False
        )
        
        assert server == mock_server
        assert error is None
        mock_smtp_ssl.assert_called_once()
        print("✅ Implicit SSL logic passed")

def test_tls_logic():
    print("Testing TLS logic (Port 587)...")
    with patch("smtplib.SMTP") as mock_smtp:
        mock_server = MagicMock()
        mock_server.has_extn.return_value = True
        mock_smtp.return_value = mock_server
        
        server, error = get_smtp_connection(
            "smtp.example.com", 587, "user", "pass", use_tls=True, use_ssl=False
        )
        
        assert server == mock_server
        assert error is None
        mock_server.starttls.assert_called_once()
        print("✅ TLS logic passed")

def test_wrong_version_error_handling():
    print("Testing WRONG_VERSION_NUMBER error handling...")
    with patch("smtplib.SMTP_SSL") as mock_smtp_ssl:
        mock_smtp_ssl.side_effect = ssl.SSLError("[SSL: WRONG_VERSION_NUMBER] wrong version number (_ssl.c:1032)")
        
        server, error = get_smtp_connection(
            "smtp.example.com", 465, "user", "pass", use_tls=False, use_ssl=True
        )
        
        assert server is None
        assert "SSL Protocol Mismatch" in error
        print("✅ Correctly caught and explained WRONG_VERSION_NUMBER error")

if __name__ == "__main__":
    try:
        test_implicit_ssl_logic()
        test_tls_logic()
        test_wrong_version_error_handling()
        print("\nAll verification tests passed!")
    except Exception as e:
        print(f"\nVerification FAILED: {str(e)}")
        sys.exit(1)
