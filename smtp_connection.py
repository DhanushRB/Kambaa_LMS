import smtplib
import ssl
import logging
import socket
from typing import Tuple, Optional, Any

logger = logging.getLogger(__name__)

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
    Creates a robust SMTP connection with proper SSL/TLS handling.
    
    Args:
        host: SMTP server hostname
        port: SMTP server port
        username: SMTP username
        password: SMTP password
        use_tls: Whether to use STARTTLS (typically for port 587)
        use_ssl: Whether to use implicit SSL (typically for port 465)
        timeout: Connection timeout in seconds
        
    Returns:
        Tuple of (connection object or None, error message or None)
    """
    server = None
    try:
        host = host.strip()
        
        # Test DNS resolution
        try:
            socket.gethostbyname(host)
        except socket.gaierror as dns_error:
            logger.warning(f"DNS resolution warning for '{host}': {str(dns_error)}")
            # We continue anyway as some systems might resolve it differently during connection
            
        # Create SSL context for security
        context = ssl.create_default_context()
        
        # Determine connection method
        # Port 465 is almost always implicit SSL
        is_implicit_ssl = use_ssl or (port == 465)
        
        if is_implicit_ssl:
            logger.info(f"Connecting to {host}:{port} via SMTP_SSL")
            server = smtplib.SMTP_SSL(host, port, timeout=timeout, context=context)
        else:
            logger.info(f"Connecting to {host}:{port} via SMTP")
            server = smtplib.SMTP(host, port, timeout=timeout)
            
            # Use EHLO before STARTTLS if possible
            try:
                server.ehlo()
            except Exception:
                pass
                
            if use_tls:
                if server.has_extn("STARTTLS"):
                    logger.info("Starting TLS...")
                    server.starttls(context=context)
                    # Re-identify after STARTTLS
                    server.ehlo()
                else:
                    logger.warning("STARTTLS requested but not supported by server")
        
        # Set command timeout on the socket
        if hasattr(server, 'sock') and server.sock:
            server.sock.settimeout(timeout)
            
        # Attempt Login
        logger.info(f"Attempting login for {username}")
        server.login(username, password)
        
        return server, None
        
    except (smtplib.SMTPAuthenticationError, smtplib.SMTPConnectError, smtplib.SMTPException, 
            socket.timeout, socket.error, ssl.SSLError) as e:
        error_msg = str(e)
        logger.error(f"SMTP connection error: {error_msg}")
        
        # Clean up if partially connected
        if server:
            try:
                server.quit()
            except:
                pass
                
        # Handle specific common SSL errors
        if "WRONG_VERSION_NUMBER" in error_msg:
            return None, "SSL Protocol Mismatch: The server might not support SSL on this port. Try port 587 with TLS."
        
        return None, error_msg
    except Exception as e:
        logger.error(f"Unexpected SMTP error: {str(e)}")
        if server:
            try:
                server.quit()
            except:
                pass
        return None, f"Unexpected error: {str(e)}"
