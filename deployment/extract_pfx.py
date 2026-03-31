import sys
import getpass
from pathlib import Path
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.primitives import serialization

def extract_pfx(pfx_path, password, cert_out_path, key_out_path):
    with open(pfx_path, "rb") as f:
        pfx_data = f.read()

    try:
        private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(
            pfx_data, password.encode() if password else None
        )
    except ValueError as e:
        print(f"[ERROR] Incorrect password or invalid PFX file: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Failed to load PFX: {e}")
        sys.exit(1)
        
    if not private_key or not certificate:
        print("[ERROR] PFX file does not contain both a private key and a certificate.")
        sys.exit(1)

    # Ensure output directory exists
    Path(key_out_path).parent.mkdir(parents=True, exist_ok=True)

    # Write Private Key (no password protection on the output file)
    with open(key_out_path, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))
        
    # Write Main Certificate
    with open(cert_out_path, "wb") as f:
        f.write(certificate.public_bytes(serialization.Encoding.PEM))
        # Write any intermediate certificates included in the PFX
        if additional_certificates:
            for add_cert in additional_certificates:
                f.write(add_cert.public_bytes(serialization.Encoding.PEM))

    print(f"\n[SUCCESS] Extracted key to: {key_out_path}")
    print(f"[SUCCESS] Extracted cert to: {cert_out_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_pfx.py <path_to_pfx_file>")
        sys.exit(1)
    
    pfx_file = sys.argv[1]
    password = getpass.getpass(prompt="Enter PFX password: ")
    
    # Paths configured specifically for start_native.cmd
    cert_path = "certs/lexchat.crt"
    key_path = "certs/lexchat.key"
    
    print(f"\nExtracting {pfx_file}...")
    extract_pfx(pfx_file, password, cert_path, key_path)
