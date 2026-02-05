from passlib.context import CryptContext
import logging

logging.basicConfig(level=logging.DEBUG)

try:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    print("Hashing 'admin'...")
    h = pwd_context.hash("admin")
    print(f"Hash: {h}")
    print("Verifying 'admin'...")
    v = pwd_context.verify("admin", h)
    print(f"Verify Result: {v}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
