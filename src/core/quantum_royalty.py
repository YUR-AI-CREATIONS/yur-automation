"""
Post-Quantum Cryptography (PQC) Layer — Kyber + Dilithium
Replaces HMAC/TLS with quantum-resistant signatures and key encapsulation
"""

import base64
import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Tuple, Optional, Dict
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to import liboqs-python (if installed)
try:
    from oqs import Signature, KeyEncapsulation
    PQC_AVAILABLE = True
except ImportError:
    PQC_AVAILABLE = False
    logger.warning("liboqs-python not installed. Using fallback HMAC mode.")


@dataclass
class PQCKeyPair:
    """Post-Quantum key pair"""
    public_key: bytes
    private_key: bytes  # Should be kept secret
    algorithm: str
    created_at: str


@dataclass
class PQCSignature:
    """Post-Quantum signature"""
    signature: bytes
    message_hash: str
    algorithm: str
    signed_at: str


class QuantumRoyalty:
    """
    Post-Quantum Cryptography engine for Trinity.
    
    Uses:
    - Dilithium3 for digital signatures (replaces HMAC)
    - Kyber768 for key encapsulation (replaces TLS)
    - Lattice-based algorithms (secure against quantum computers)
    """

    def __init__(self, use_pqc: bool = True):
        self.use_pqc = use_pqc and PQC_AVAILABLE
        self.sig_algo = "Dilithium3" if self.use_pqc else "HMAC"
        self.kem_algo = "Kyber768" if self.use_pqc else "TLS"
        
        # Key storage (in production, use HSM)
        self.signing_keys: Dict[str, PQCKeyPair] = {}
        self.public_keys: Dict[str, bytes] = {}
        
        logger.info(f"QuantumRoyalty initialized: {self.sig_algo}+{self.kem_algo}")

    def generate_keypair(self, key_id: str) -> Tuple[bool, str, Optional[PQCKeyPair]]:
        """
        Generate a post-quantum key pair.
        
        Args:
            key_id: Identifier for the key (e.g., "trinity-spine-001")
        
        Returns:
            (success, message, keypair)
        """
        if key_id in self.signing_keys:
            return False, f"Key {key_id} already exists", None
        
        try:
            if self.use_pqc:
                sig = Signature(self.sig_algo)
                public_key = sig.generate_keypair()
                private_key = sig.export_secret_key()
            else:
                # Fallback: generate keys using HMAC
                public_key = hashlib.sha256(f"{key_id}:public".encode()).digest()
                private_key = hashlib.sha256(f"{key_id}:private".encode()).digest()
            
            keypair = PQCKeyPair(
                public_key=public_key,
                private_key=private_key,
                algorithm=self.sig_algo,
                created_at=datetime.utcnow().isoformat(),
            )
            
            self.signing_keys[key_id] = keypair
            self.public_keys[key_id] = public_key
            
            logger.info(f"✅ Generated {self.sig_algo} keypair: {key_id}")
            return True, f"Keypair generated", keypair
        
        except Exception as e:
            logger.error(f"Keypair generation failed: {e}")
            return False, f"Keypair generation failed: {e}", None

    def sign_mission(
        self,
        mission_data: Dict,
        key_id: str,
    ) -> Tuple[bool, str, Optional[PQCSignature]]:
        """
        Sign a mission with PQC signature.
        
        Args:
            mission_data: Mission dict to sign
            key_id: ID of the signing key
        
        Returns:
            (success, message, signature)
        """
        if key_id not in self.signing_keys:
            return False, f"Key {key_id} not found", None
        
        try:
            # Serialize mission data deterministically
            mission_json = json.dumps(mission_data, sort_keys=True)
            message_hash = hashlib.sha256(mission_json.encode()).hexdigest()
            
            if self.use_pqc:
                sig = Signature(self.sig_algo)
                # Load private key
                sig.secret_key = self.signing_keys[key_id].private_key
                signature = sig.sign(mission_json.encode())
            else:
                # Fallback: HMAC signature
                signature = hashlib.sha256(
                    mission_json.encode() + self.signing_keys[key_id].private_key
                ).digest()
            
            pqc_sig = PQCSignature(
                signature=signature,
                message_hash=message_hash,
                algorithm=self.sig_algo,
                signed_at=datetime.utcnow().isoformat(),
            )
            
            logger.info(f"✅ Mission signed with {self.sig_algo}: {message_hash[:16]}")
            return True, f"Mission signed", pqc_sig
        
        except Exception as e:
            logger.error(f"Signing failed: {e}")
            return False, f"Signing failed: {e}", None

    def verify_signature(
        self,
        mission_data: Dict,
        signature_bytes: bytes,
        key_id: str,
    ) -> Tuple[bool, str]:
        """
        Verify a PQC signature.
        
        Args:
            mission_data: Original mission data
            signature_bytes: Signature to verify
            key_id: ID of the public key
        
        Returns:
            (valid, message)
        """
        if key_id not in self.public_keys:
            return False, f"Public key {key_id} not found"
        
        try:
            mission_json = json.dumps(mission_data, sort_keys=True)
            
            if self.use_pqc:
                sig = Signature(self.sig_algo)
                sig.public_key = self.public_keys[key_id]
                is_valid = sig.verify(mission_json.encode(), signature_bytes)
            else:
                # Fallback: HMAC verification
                expected_sig = hashlib.sha256(
                    mission_json.encode() + self.signing_keys[key_id].private_key
                ).digest()
                is_valid = signature_bytes == expected_sig
            
            if is_valid:
                logger.info(f"✅ Signature verified with {key_id}")
                return True, "Signature valid"
            else:
                logger.warning(f"❌ Signature verification failed for {key_id}")
                return False, "Signature invalid"
        
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return False, f"Verification failed: {e}"

    def encapsulate(self, key_id: str) -> Tuple[bool, str, Optional[Tuple[bytes, bytes]]]:
        """
        Kyber key encapsulation (generate shared secret).
        
        Args:
            key_id: ID of the recipient's public key
        
        Returns:
            (success, message, (ciphertext, shared_secret))
        """
        if key_id not in self.public_keys:
            return False, f"Public key {key_id} not found", None
        
        try:
            if self.use_pqc:
                kem = KeyEncapsulation(self.kem_algo)
                kem.public_key = self.public_keys[key_id]
                ciphertext = kem.encap_secret()
                shared_secret = kem.get_shared_secret()
            else:
                # Fallback: simple HKDF
                import hmac
                shared_secret = hmac.new(
                    self.public_keys[key_id],
                    b"shared_secret",
                    hashlib.sha256,
                ).digest()
                ciphertext = shared_secret  # Simplified
            
            logger.info(f"✅ Key encapsulation for {key_id}")
            return True, "Key encapsulated", (ciphertext, shared_secret)
        
        except Exception as e:
            logger.error(f"Encapsulation failed: {e}")
            return False, f"Encapsulation failed: {e}", None

    def decapsulate(
        self,
        ciphertext: bytes,
        key_id: str,
    ) -> Tuple[bool, str, Optional[bytes]]:
        """
        Kyber key decapsulation (recover shared secret).
        
        Args:
            ciphertext: Ciphertext from encapsulation
            key_id: ID of the private key
        
        Returns:
            (success, message, shared_secret)
        """
        if key_id not in self.signing_keys:
            return False, f"Private key {key_id} not found", None
        
        try:
            if self.use_pqc:
                kem = KeyEncapsulation(self.kem_algo)
                kem.secret_key = self.signing_keys[key_id].private_key
                shared_secret = kem.decap_secret(ciphertext)
            else:
                # Fallback
                shared_secret = ciphertext
            
            logger.info(f"✅ Key decapsulation for {key_id}")
            return True, "Key decapsulated", shared_secret
        
        except Exception as e:
            logger.error(f"Decapsulation failed: {e}")
            return False, f"Decapsulation failed: {e}", None

    def get_pqc_status(self) -> Dict:
        """Get PQC configuration and key inventory"""
        return {
            "pqc_available": self.use_pqc,
            "signature_algorithm": self.sig_algo,
            "kem_algorithm": self.kem_algo,
            "keypairs_in_store": len(self.signing_keys),
            "keypair_ids": list(self.signing_keys.keys()),
            "fallback_mode": not self.use_pqc,
        }

    def export_public_key(self, key_id: str, format: str = "base64") -> Optional[str]:
        """Export a public key for distribution"""
        if key_id not in self.public_keys:
            return None
        
        if format == "base64":
            return base64.b64encode(self.public_keys[key_id]).decode()
        elif format == "hex":
            return self.public_keys[key_id].hex()
        else:
            return None


# Global instance
quantum_royalty = QuantumRoyalty(use_pqc=PQC_AVAILABLE)
