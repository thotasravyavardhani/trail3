"""
Email service for IMAP/SMTP operations with Gmail/Outlook support
"""

import imaplib
import smtplib
import email
import json
import base64
import asyncio
from typing import List, Dict, Optional, Tuple
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.utils import make_msgid, formatdate
from email import encoders
from datetime import datetime
import logging

from models import User, Email as EmailModel
from logger import setup_logger

logger = setup_logger()

class EmailService:
    """Email service for IMAP/SMTP operations"""
    
    def __init__(self):
        self.imap_connections = {}
        self.smtp_connections = {}
    
    async def validate_credentials(self, email_addr: str, password: str, 
                                 imap_server: str, smtp_server: str,
                                 imap_port: int = 993, smtp_port: int = 587) -> bool:
        """Validate email credentials with IMAP/SMTP servers"""
        try:
            # Test IMAP connection
            imap = imaplib.IMAP4_SSL(imap_server, imap_port)
            imap.login(email_addr, password)
            imap.select('INBOX')
            imap.logout()
            
            # Test SMTP connection
            smtp = smtplib.SMTP(smtp_server, smtp_port)
            smtp.starttls()
            smtp.login(email_addr, password)
            smtp.quit()
            
            logger.info(f"Email credentials validated for {email_addr}")
            return True
            
        except Exception as e:
            logger.error(f"Email credential validation failed for {email_addr}: {e}")
            return False
    
    def _get_imap_connection(self, user: User) -> imaplib.IMAP4_SSL:
        """Get or create IMAP connection for user"""
        user_key = f"{user.email}:{user.imap_server}:{user.imap_port}"
        
        if user_key in self.imap_connections:
            try:
                # Test existing connection
                conn = self.imap_connections[user_key]
                conn.noop()
                return conn
            except:
                # Connection dead, remove it
                del self.imap_connections[user_key]
        
        # Create new connection
        try:
            conn = imaplib.IMAP4_SSL(user.imap_server, user.imap_port)
            # Note: In production, store encrypted passwords
            conn.login(user.email, "app_password")  # User needs to provide this
            self.imap_connections[user_key] = conn
            return conn
        except Exception as e:
            logger.error(f"Failed to create IMAP connection for {user.email}: {e}")
            raise
    
    def _get_smtp_connection(self, user: User) -> smtplib.SMTP:
        """Get or create SMTP connection for user"""
        user_key = f"{user.email}:{user.smtp_server}:{user.smtp_port}"
        
        try:
            conn = smtplib.SMTP(user.smtp_server, user.smtp_port)
            conn.starttls()
            # Note: In production, store encrypted passwords
            conn.login(user.email, "app_password")  # User needs to provide this
            return conn
        except Exception as e:
            logger.error(f"Failed to create SMTP connection for {user.email}: {e}")
            raise
    
    async def fetch_inbox(self, user: User, limit: int = 50) -> List[Dict]:
        """Fetch emails from INBOX via IMAP"""
        try:
            conn = self._get_imap_connection(user)
            conn.select('INBOX')
            
            # Search for recent emails
            status, messages = conn.search(None, 'ALL')
            if status != 'OK':
                raise Exception("Failed to search INBOX")
            
            message_nums = messages[0].split()
            recent_messages = message_nums[-limit:] if len(message_nums) > limit else message_nums
            
            emails = []
            for num in reversed(recent_messages):  # Newest first
                try:
                    # Fetch email
                    status, msg_data = conn.fetch(num, '(RFC822 UID)')
                    if status != 'OK':
                        continue
                    
                    # Parse email
                    email_body = msg_data[0][1]
                    email_message = email.message_from_bytes(email_body)
                    
                    # Get UID
                    uid_data = msg_data[1].decode() if len(msg_data) > 1 else ""
                    uid = None
                    if 'UID' in uid_data:
                        uid = uid_data.split('UID ')[1].split(')')[0]
                    
                    # Extract email data
                    email_data = self._parse_email_message(email_message, uid)
                    emails.append(email_data)
                    
                except Exception as e:
                    logger.error(f"Failed to fetch email {num}: {e}")
                    continue
            
            logger.info(f"Fetched {len(emails)} emails from {user.email} inbox")
            return emails
            
        except Exception as e:
            logger.error(f"Failed to fetch inbox for {user.email}: {e}")
            return []
    
    async def fetch_sent(self, user: User, limit: int = 50) -> List[Dict]:
        """Fetch sent emails from SENT folder"""
        try:
            conn = self._get_imap_connection(user)
            
            # Try different sent folder names
            sent_folders = ['SENT', 'Sent', '[Gmail]/Sent Mail', 'INBOX.Sent']
            sent_folder = None
            
            for folder in sent_folders:
                try:
                    conn.select(folder)
                    sent_folder = folder
                    break
                except:
                    continue
            
            if not sent_folder:
                logger.warning(f"No sent folder found for {user.email}")
                return []
            
            # Search for recent emails
            status, messages = conn.search(None, 'ALL')
            if status != 'OK':
                return []
            
            message_nums = messages[0].split()
            recent_messages = message_nums[-limit:] if len(message_nums) > limit else message_nums
            
            emails = []
            for num in reversed(recent_messages):
                try:
                    status, msg_data = conn.fetch(num, '(RFC822 UID)')
                    if status != 'OK':
                        continue
                    
                    email_body = msg_data[0][1]
                    email_message = email.message_from_bytes(email_body)
                    
                    # Get UID
                    uid_data = msg_data[1].decode() if len(msg_data) > 1 else ""
                    uid = None
                    if 'UID' in uid_data:
                        uid = uid_data.split('UID ')[1].split(')')[0]
                    
                    email_data = self._parse_email_message(email_message, uid)
                    email_data["folder"] = "SENT"
                    emails.append(email_data)
                    
                except Exception as e:
                    logger.error(f"Failed to fetch sent email {num}: {e}")
                    continue
            
            logger.info(f"Fetched {len(emails)} sent emails from {user.email}")
            return emails
            
        except Exception as e:
            logger.error(f"Failed to fetch sent emails for {user.email}: {e}")
            return []
    
    def _parse_email_message(self, email_message: email.message.EmailMessage, uid: str = None) -> Dict:
        """Parse email message into QuMail format"""
        try:
            # Basic headers
            email_data = {
                "uid": uid,
                "message_id": email_message.get("Message-ID", ""),
                "sender": email_message.get("From", ""),
                "to": email_message.get("To", ""),
                "cc": email_message.get("Cc", ""),
                "bcc": email_message.get("Bcc", ""),
                "subject": email_message.get("Subject", ""),
                "date": email_message.get("Date", ""),
                "headers": dict(email_message.items())
            }
            
            # Check for QuMail encryption headers
            encryption_mode = email_message.get("X-QuMail-Encryption", "NONE")
            email_data["encryption_mode"] = encryption_mode
            
            # Extract body
            body = ""
            if email_message.is_multipart():
                for part in email_message.walk():
                    if part.get_content_type() == "text/plain":
                        try:
                            body = part.get_payload(decode=True).decode('utf-8')
                            break
                        except:
                            body = str(part.get_payload())
                            break
            else:
                try:
                    body = email_message.get_payload(decode=True).decode('utf-8')
                except:
                    body = str(email_message.get_payload())
            
            email_data["body"] = body
            
            # Extract QuMail encryption metadata if present
            if encryption_mode != "NONE":
                # Check for QuMail encrypted content
                if "X-QuMail-Content" in email_message:
                    email_data["content"] = email_message["X-QuMail-Content"]
                if "X-QuMail-Nonce" in email_message:
                    email_data["nonce"] = email_message["X-QuMail-Nonce"]
                if "X-QuMail-MAC" in email_message:
                    email_data["mac"] = email_message["X-QuMail-MAC"]
                if "X-QuMail-KM-Key-ID" in email_message:
                    email_data["km_key_id"] = email_message["X-QuMail-KM-Key-ID"]
            
            # Handle attachments
            attachments = []
            if email_message.is_multipart():
                for part in email_message.walk():
                    if part.get_content_disposition() == 'attachment':
                        attachments.append({
                            "filename": part.get_filename() or "attachment",
                            "content_type": part.get_content_type(),
                            "size": len(part.get_payload(decode=True) or b"")
                        })
            
            email_data["attachments"] = attachments
            
            return email_data
            
        except Exception as e:
            logger.error(f"Failed to parse email message: {e}")
            return {
                "uid": uid,
                "sender": "unknown",
                "subject": "Parse Error",
                "body": "Failed to parse email",
                "encryption_mode": "NONE",
                "error": str(e)
            }
    
    async def send_email(self, user: User, email_data: Dict) -> bool:
        """Send encrypted email via SMTP"""
        try:
            # Create MIME message
            msg = MIMEMultipart()
            msg['From'] = user.email
            msg['To'] = email_data["to"]
            if email_data.get("cc"):
                msg['Cc'] = email_data["cc"]
            
            # Subject (encrypted if not NONE mode)
            if email_data["encryption_mode"] == "NONE":
                msg['Subject'] = email_data.get("subject", "")
            else:
                msg['Subject'] = f"[QuMail Encrypted - {email_data['encryption_mode']}]"
            
            msg['Date'] = formatdate(localtime=True)
            msg['Message-ID'] = make_msgid()
            
            # Add QuMail headers
            msg['X-QuMail-Encryption'] = email_data["encryption_mode"]
            msg['X-QuMail-Version'] = "1.0"
            
            if email_data.get("content"):
                msg['X-QuMail-Content'] = email_data["content"]
            if email_data.get("nonce"):
                msg['X-QuMail-Nonce'] = email_data["nonce"]
            if email_data.get("mac"):
                msg['X-QuMail-MAC'] = email_data["mac"]
            if email_data.get("km_key_id"):
                msg['X-QuMail-KM-Key-ID'] = email_data["km_key_id"]
            
            # Body
            if email_data["encryption_mode"] == "NONE":
                body_text = email_data.get("body", "")
            else:
                body_text = f"""
This is a QuMail encrypted message using {email_data['encryption_mode']} encryption.
Use QuMail client to decrypt and view the content.

Encryption Mode: {email_data['encryption_mode']}
Timestamp: {email_data.get('timestamp', datetime.now().isoformat())}
                """.strip()
            
            msg.attach(MIMEText(body_text, 'plain'))
            
            # Handle attachments
            for attachment in email_data.get("attachments", []):
                if isinstance(attachment, dict) and "content" in attachment:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment["content"])
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {attachment["filename"]}'
                    )
                    msg.attach(part)
            
            # Send via SMTP
            smtp = self._get_smtp_connection(user)
            
            # Build recipient list
            recipients = [email_data["to"]]
            if email_data.get("cc"):
                recipients.extend([addr.strip() for addr in email_data["cc"].split(",")])
            if email_data.get("bcc"):
                recipients.extend([addr.strip() for addr in email_data["bcc"].split(",")])
            
            smtp.send_message(msg, to_addrs=recipients)
            smtp.quit()
            
            logger.info(f"Email sent from {user.email} to {email_data['to']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email from {user.email}: {e}")
            return False
    
    async def save_to_sent(self, user: User, email_data: Dict) -> bool:
        """Save email to SENT folder via IMAP APPEND"""
        try:
            conn = self._get_imap_connection(user)
            
            # Create email message for SENT folder
            msg = MIMEMultipart()
            msg['From'] = user.email
            msg['To'] = email_data["to"]
            if email_data.get("cc"):
                msg['Cc'] = email_data["cc"]
            msg['Subject'] = email_data.get("subject", "[QuMail Encrypted]")
            msg['Date'] = formatdate(localtime=True)
            
            # Add QuMail headers
            msg['X-QuMail-Encryption'] = email_data["encryption_mode"]
            if email_data.get("content"):
                msg['X-QuMail-Content'] = email_data["content"]
            if email_data.get("mac"):
                msg['X-QuMail-MAC'] = email_data["mac"]
            
            body_text = email_data.get("body", "QuMail encrypted content")
            msg.attach(MIMEText(body_text, 'plain'))
            
            # Try to append to sent folder
            sent_folders = ['SENT', 'Sent', '[Gmail]/Sent Mail', 'INBOX.Sent']
            
            for folder in sent_folders:
                try:
                    conn.append(folder, None, None, msg.as_bytes())
                    logger.info(f"Email saved to {folder} for {user.email}")
                    return True
                except Exception as e:
                    logger.debug(f"Failed to append to {folder}: {e}")
                    continue
            
            logger.warning(f"Failed to save to any sent folder for {user.email}")
            return False
            
        except Exception as e:
            logger.error(f"Failed to save to sent folder for {user.email}: {e}")
            return False
    
    def close_connections(self, user_email: str):
        """Close connections for a user"""
        # Close IMAP connections
        for key in list(self.imap_connections.keys()):
            if key.startswith(user_email):
                try:
                    self.imap_connections[key].logout()
                    del self.imap_connections[key]
                except:
                    pass
        
        logger.info(f"Closed connections for {user_email}")
    
    def __del__(self):
        """Cleanup connections on destruction"""
        for conn in self.imap_connections.values():
            try:
                conn.logout()
            except:
                pass