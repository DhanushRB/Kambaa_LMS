import smtplib
import ssl
import logging
import socket
import threading
from typing import Tuple, Optional, Any

logger = logging.getLogger(__name__)

class SMTPConnectionManager:
    """
    Manages persistent SMTP connections to avoid reconnection latency.
    Implements a singleton-like pattern with configuration tracking.
    """
    _connection = None
    _config_checksum = None
    _lock = threading.Lock()

    @classmethod
    def _get_config_checksum(cls, **config) -> str:
        """Generate a simple checksum of the configuration to detect changes."""
        config_str = "|".join(f"{k}:{v}" for k, v in sorted(config.items()))
        import hashlib
        return hashlib.md5(config_str.encode()).hexdigest()

    @classmethod
    def is_connected(cls) -> bool:
        """Check if the current connection is alive using HELP or NOOP."""
        if cls._connection is None:
            return False
        try:
            # NOOP is the standard way to check if connection is alive
            status = cls._connection.noop()[0]
            return status == 250
        except Exception:
            return False

    @classmethod
    def get_connection(
        cls,
        host: str,
        port: int,
        username: str,
        password: str,
        use_tls: bool = True,
        use_ssl: bool = False,
        timeout: int = 30
    ) -> Tuple[Optional[Any], Optional[str]]:
        """
        Gets an existing connection or creates a new one if needed.
        """
        config = {
            'host': host.strip(),
            'port': port,
            'username': username,
            'password': password,
            'use_tls': use_tls,
            'use_ssl': use_ssl
        }
        new_checksum = cls._get_config_checksum(**config)

        with cls._lock:
            # If config changed or connection is dead, reset
            if cls._config_checksum != new_checksum or not cls.is_connected():
                if cls._connection:
                    logger.info("SMTP configuration changed or connection lost. Resetting connection.")
                    try:
                        cls._connection.quit()
                    except:
                        pass
                    cls._connection = None
                
                # Create new connection
                logger.info(f"Creating new SMTP connection to {host}:{port}")
                server, error = cls._create_new_connection(**config, timeout=timeout)
                if error:
                    return None, error
                
                cls._connection = server
                cls._config_checksum = new_checksum
            else:
                logger.debug("Reusing existing SMTP connection")

            return cls._connection, None

    @classmethod
    def _create_new_connection(
        cls, host, port, username, password, use_tls, use_ssl, timeout
    ) -> Tuple[Optional[Any], Optional[str]]:
        """Low-level connection creation logic (extracted from original get_smtp_connection)"""
        server = None
        try:
            # Create SSL context for security
            context = ssl.create_default_context()
            
            # Determine connection method
            is_implicit_ssl = use_ssl or (port == 465)
            
            if is_implicit_ssl:
                server = smtplib.SMTP_SSL(host, port, timeout=timeout, context=context)
            else:
                server = smtplib.SMTP(host, port, timeout=timeout)
                
                try:
                    server.ehlo()
                except Exception:
                    pass
                    
                if use_tls:
                    if server.has_extn("STARTTLS"):
                        server.starttls(context=context)
                        server.ehlo()
            
            # Attempt Login
            server.login(username, password)
            return server, None
            
        except (smtplib.SMTPAuthenticationError, smtplib.SMTPConnectError, smtplib.SMTPException, 
                socket.timeout, socket.error, ssl.SSLError) as e:
            error_msg = str(e)
            if server:
                try:
                    server.quit()
                except:
                    pass
            return None, error_msg
        except Exception as e:
            if server:
                try:
                    server.quit()
                except:
                    pass
            return None, f"Unexpected error: {str(e)}"

def get_smtp_connection(
    host: str,
    port: int,
    username: str,
    password: str,
    use_tls: bool = True,
    use_ssl: bool = False,
    timeout: int = 30
) -> Tuple[Optional[Any], Optional[str]]:
    """
    Maintains backward compatibility by wrapping SMTPConnectionManager.
    """
    return SMTPConnectionManager.get_connection(
        host=host,
        port=port,
        username=username,
        password=password,
        use_tls=use_tls,
        use_ssl=use_ssl,
        timeout=timeout
    )
