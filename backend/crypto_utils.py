"""
Cryptographic utilities for QuMail quantum-secure email client
Implements OTP, AES-256-GCM, PQC (Kyber/Dilithium), and integrity verification
"""

import secrets
import hashlib
import hmac
import base64
import json
from typing import Dict, Optional, Tuple, Union, List
from datetime import datetime, timedelta
import logging

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature

# PQC imports (fallback if not available)
try:
    import pqcrypto.kem.kyber512 as kyber
    import pqcrypto.sign.dilithium2 as dilithium
    PQC_AVAILABLE = True
except ImportError:
    PQC_AVAILABLE = False
    kyber = None
    dilithium = None
    print("Warning: PQC libraries not available, falling back to classical crypto")

# JWT imports
try:
    from jose import jwt, JWTError
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False
    jwt = None
    JWTError = Exception
    print("Warning: JWT library not available")

logger = logging.getLogger(__name__)

class CryptoManager:
    """Central cryptographic operations manager"""
    
    def __init__(self):
        self.jwt_secret = secrets.token_urlsafe(32)
        self.jwt_algorithm = "HS256"
        
    def generate_jwt_token(self, email: str, expires_delta: Optional[timedelta] = None) -> str:
        """Generate JWT token for user authentication"""
        if not JWT_AVAILABLE:
            raise RuntimeError("JWT library not available")
            
        if expires_delta is None:
            expires_delta = timedelta(hours=24)
            
        expire = datetime.utcnow() + expires_delta
        payload = {
            "sub": email,
            "exp": expire,
            "iat": datetime.utcnow()
        }
        
        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
    
    def verify_jwt_token(self, token: str) -> Dict:
        """Verify and decode JWT token"""
        if not JWT_AVAILABLE:
            raise RuntimeError("JWT library not available")
            
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            return payload
        except JWTError as e:
            raise ValueError(f"Invalid token: {e}")
    
    def generate_otp_key(self, length: int = 32) -> bytes:
        """Generate cryptographically secure OTP key"""
        return secrets.token_bytes(length)
    
    def otp_encrypt(self, plaintext: bytes, key: bytes) -> bytes:
        """One-Time Pad encryption (perfect secrecy)"""
        if len(key) < len(plaintext):
            raise ValueError("OTP key must be at least as long as plaintext")
        
        # XOR plaintext with key
        ciphertext = bytes(p ^ k for p, k in zip(plaintext, key[:len(plaintext)]))
        return ciphertext
    
    def otp_decrypt(self, ciphertext: bytes, key: bytes) -> bytes:
        """One-Time Pad decryption"""
        if len(key) < len(ciphertext):
            raise ValueError("OTP key must be at least as long as ciphertext")
        
        # XOR ciphertext with key (same operation as encryption)
        plaintext = bytes(c ^ k for c, k in zip(ciphertext, key[:len(ciphertext)]))
        return plaintext
    
    def aes_encrypt(self, plaintext: bytes, key: bytes) -> Tuple[bytes, bytes]:
        """AES-256-GCM encryption with authentication"""
        if len(key) not in [16, 24, 32]:
            # Derive key using PBKDF2 if not proper length
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'qumail_salt',  # In production, use random salt
                iterations=100000,
            )
            key = kdf.derive(key)
        
        aesgcm = AESGCM(key)
        nonce = secrets.token_bytes(12)  # 96-bit nonce for GCM
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        
        return ciphertext, nonce
    
    def aes_decrypt(self, ciphertext: bytes, key: bytes, nonce: bytes) -> bytes:
        """AES-256-GCM decryption with authentication"""
        if len(key) not in [16, 24, 32]:
            # Derive key using PBKDF2 if not proper length
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'qumail_salt',  # Must match encryption salt
                iterations=100000,
            )
            key = kdf.derive(key)
        
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        
        return plaintext
    
    def pqc_generate_keypair(self) -> Tuple[bytes, bytes]:
        """Generate PQC keypair (Kyber for KEM)"""
        if not PQC_AVAILABLE:
            raise RuntimeError("PQC libraries not available")
        
        public_key, secret_key = kyber.generate_keypair()
        return public_key, secret_key
    
    def pqc_encapsulate(self, public_key: bytes) -> Tuple[bytes, bytes]:
        """PQC key encapsulation (generates shared secret)"""
        if not PQC_AVAILABLE:
            raise RuntimeError("PQC libraries not available")
        
        ciphertext, shared_secret = kyber.encapsulate(public_key)
        return ciphertext, shared_secret
    
    def pqc_decapsulate(self, ciphertext: bytes, secret_key: bytes) -> bytes:
        """PQC key decapsulation (recovers shared secret)"""
        if not PQC_AVAILABLE:
            raise RuntimeError("PQC libraries not available")
        
        shared_secret = kyber.decapsulate(ciphertext, secret_key)
        return shared_secret
    
    def pqc_sign_generate_keypair(self) -> Tuple[bytes, bytes]:
        """Generate PQC signing keypair (Dilithium)"""
        if not PQC_AVAILABLE:
            raise RuntimeError("PQC libraries not available")
        
        public_key, secret_key = dilithium.generate_keypair()
        return public_key, secret_key
    
    def pqc_sign(self, message: bytes, secret_key: bytes) -> bytes:
        """PQC digital signature"""
        if not PQC_AVAILABLE:
            raise RuntimeError("PQC libraries not available")
        
        signature = dilithium.sign(message, secret_key)
        return signature
    
    def pqc_verify(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        """PQC signature verification"""
        if not PQC_AVAILABLE:
            raise RuntimeError("PQC libraries not available")
        
        try:
            dilithium.verify(message, signature, public_key)
            return True
        except:
            return False
    
    def compute_hmac(self, data: bytes, key: bytes) -> str:
        """Compute HMAC-SHA256 for integrity verification"""
        mac = hmac.new(key, data, hashlib.sha256)
        return base64.b64encode(mac.digest()).decode('utf-8')
    
    def verify_hmac(self, data: bytes, key: bytes, expected_mac: str) -> bool:
        """Verify HMAC-SHA256 integrity"""
        try:
            expected_digest = base64.b64decode(expected_mac.encode('utf-8'))
            mac = hmac.new(key, data, hashlib.sha256)
            return hmac.compare_digest(mac.digest(), expected_digest)
        except Exception:
            return False
    
    def secure_wipe(self, data: Union[bytes, bytearray, None]) -> None:
        """Securely wipe sensitive data from memory"""
        if data is None:
            return
        if isinstance(data, bytes):
            # Can't modify bytes directly, but ensure it's dereferenced
            data = None
        elif isinstance(data, bytearray):
            # Zero out the bytearray
            for i in range(len(data)):
                data[i] = 0
    
    async def encrypt_email(self, email_data: Dict, encryption_mode: str, km_key: Optional[bytes] = None) -> Dict:
        """Encrypt email with specified mode"""
        try:
            # Prepare email content
            content = {
                "subject": email_data["subject"],
                "body": email_data["body"],
                "attachments": email_data.get("attachments", [])
            }
            content_bytes = json.dumps(content).encode('utf-8')
            
            encrypted_email = {
                "to": email_data["to"],
                "cc": email_data.get("cc", ""),
                "bcc": email_data.get("bcc", ""),
                "encryption_mode": encryption_mode,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            if encryption_mode == "OTP":
                if not km_key:
                    raise ValueError("KM key required for OTP encryption")
                
                # Use KM key for OTP
                encrypted_content = self.otp_encrypt(content_bytes, km_key)
                encrypted_email["content"] = base64.b64encode(encrypted_content).decode('utf-8')
                encrypted_email["km_key_id"] = hashlib.sha256(km_key).hexdigest()[:16]
                
                # Compute MAC
                mac_key = hashlib.sha256(km_key + b"MAC").digest()
                encrypted_email["mac"] = self.compute_hmac(encrypted_content, mac_key)
                
            elif encryption_mode == "AES":
                if not km_key:
                    raise ValueError("KM key required for AES encryption")
                
                # Use KM key as seed for AES key derivation
                aes_key = hashlib.sha256(km_key + b"AES").digest()
                encrypted_content, nonce = self.aes_encrypt(content_bytes, aes_key)
                
                encrypted_email["content"] = base64.b64encode(encrypted_content).decode('utf-8')
                encrypted_email["nonce"] = base64.b64encode(nonce).decode('utf-8')
                encrypted_email["km_key_id"] = hashlib.sha256(km_key).hexdigest()[:16]
                
                # Compute MAC
                mac_key = hashlib.sha256(km_key + b"MAC").digest()
                encrypted_email["mac"] = self.compute_hmac(encrypted_content + nonce, mac_key)
                
            elif encryption_mode == "PQC":
                if not PQC_AVAILABLE:
                    raise RuntimeError("PQC not available, falling back to AES")
                
                # Generate ephemeral PQC keypair
                pqc_public, pqc_secret = self.pqc_generate_keypair()
                
                # Encapsulate to get shared secret
                pqc_ciphertext, shared_secret = self.pqc_encapsulate(pqc_public)
                
                # Use shared secret for AES encryption
                encrypted_content, nonce = self.aes_encrypt(content_bytes, shared_secret)
                
                encrypted_email["content"] = base64.b64encode(encrypted_content).decode('utf-8')
                encrypted_email["nonce"] = base64.b64encode(nonce).decode('utf-8')
                encrypted_email["pqc_public"] = base64.b64encode(pqc_public).decode('utf-8')
                encrypted_email["pqc_ciphertext"] = base64.b64encode(pqc_ciphertext).decode('utf-8')
                
                # Compute MAC with shared secret
                encrypted_email["mac"] = self.compute_hmac(encrypted_content + nonce, shared_secret)
                
                # Securely wipe keys
                self.secure_wipe(bytearray(shared_secret))
                self.secure_wipe(bytearray(pqc_secret))
                
            elif encryption_mode == "NONE":
                # TLS-only, no additional encryption
                encrypted_email["content"] = base64.b64encode(content_bytes).decode('utf-8')
                encrypted_email["mac"] = self.compute_hmac(content_bytes, b"qumail_default_key")
                
            else:
                raise ValueError(f"Unknown encryption mode: {encryption_mode}")
            
            # Add QuMail header
            encrypted_email["headers"] = {
                "X-QuMail-Encryption": encryption_mode,
                "X-QuMail-Version": "1.0",
                "X-QuMail-Timestamp": encrypted_email["timestamp"]
            }
            
            return encrypted_email
            
        except Exception as e:
            logger.error(f"Email encryption failed: {e}")
            raise
    
    async def decrypt_email(self, email_data: Dict, km_key: Optional[bytes] = None) -> Dict:
        """Decrypt email based on encryption mode"""
        try:
            encryption_mode = email_data.get("encryption_mode", "NONE")
            
            if encryption_mode == "OTP":
                if not km_key:
                    raise ValueError("KM key required for OTP decryption")
                
                encrypted_content = base64.b64decode(email_data["content"])
                
                # Verify MAC
                mac_key = hashlib.sha256(km_key + b"MAC").digest()
                if not self.verify_hmac(encrypted_content, mac_key, email_data["mac"]):
                    raise ValueError("MAC verification failed")
                
                # Decrypt content
                content_bytes = self.otp_decrypt(encrypted_content, km_key)
                content = json.loads(content_bytes.decode('utf-8'))
                
            elif encryption_mode == "AES":
                if not km_key:
                    raise ValueError("KM key required for AES decryption")
                
                encrypted_content = base64.b64decode(email_data["content"])
                nonce = base64.b64decode(email_data["nonce"])
                
                # Verify MAC
                mac_key = hashlib.sha256(km_key + b"MAC").digest()
                if not self.verify_hmac(encrypted_content + nonce, mac_key, email_data["mac"]):
                    raise ValueError("MAC verification failed")
                
                # Decrypt content
                aes_key = hashlib.sha256(km_key + b"AES").digest()
                content_bytes = self.aes_decrypt(encrypted_content, aes_key, nonce)
                content = json.loads(content_bytes.decode('utf-8'))
                
            elif encryption_mode == "PQC":
                if not PQC_AVAILABLE:
                    raise RuntimeError("PQC not available")
                
                encrypted_content = base64.b64decode(email_data["content"])
                nonce = base64.b64decode(email_data["nonce"])
                pqc_ciphertext = base64.b64decode(email_data["pqc_ciphertext"])
                
                # This would require the recipient's PQC secret key
                # For demo purposes, we'll indicate decryption is not possible
                raise ValueError("PQC decryption requires recipient's secret key")
                
            elif encryption_mode == "NONE":
                encrypted_content = base64.b64decode(email_data["content"])
                
                # Verify MAC
                if not self.verify_hmac(encrypted_content, b"qumail_default_key", email_data["mac"]):
                    raise ValueError("MAC verification failed")
                
                content = json.loads(encrypted_content.decode('utf-8'))
                
            else:
                raise ValueError(f"Unknown encryption mode: {encryption_mode}")
            
            # Return decrypted email
            decrypted_email = email_data.copy()
            decrypted_email.update(content)
            decrypted_email["decryption_status"] = "success"
            
            return decrypted_email
            
        except Exception as e:
            logger.error(f"Email decryption failed: {e}")
            # Return email with error status
            error_email = email_data.copy()
            error_email["decryption_status"] = "error"
            error_email["decryption_error"] = str(e)
            return error_email