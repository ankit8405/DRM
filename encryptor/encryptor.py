import os
import json
import zipfile
import io
from base64 import urlsafe_b64encode
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import sys

backend = default_backend()

def derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=backend
    )
    return kdf.derive(password.encode())

def encrypt_files(filepaths, password, metadata, package_name=None):
    for fp in filepaths:
        if not os.path.exists(fp):
            raise FileNotFoundError(f"File does not exist: {fp}")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for fp in filepaths:
            arcname = os.path.basename(fp)
            zipf.write(fp, arcname)

    zip_data = zip_buffer.getvalue()
    zip_buffer.close()

    salt = os.urandom(16)
    iv = os.urandom(16)
    key = derive_key(password, salt)

    cipher = Cipher(algorithms.AES(key), modes.CFB(iv), backend=backend)
    encryptor = cipher.encryptor()
    encrypted_data = encryptor.update(zip_data) + encryptor.finalize()

    full_data = {
        "magic": "MYDRM01",
        "salt": urlsafe_b64encode(salt).decode("utf-8"),
        "iv": urlsafe_b64encode(iv).decode("utf-8"),
        "metadata": metadata,
        "data": urlsafe_b64encode(encrypted_data).decode("utf-8")
    }

    if not package_name:
        package_name = "package"
    if not package_name.endswith(".mylock"):
        new_filename = f"{package_name}.mylock"
    else:
        new_filename = package_name
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    files_dir = os.path.join(base_dir, "files")
    os.makedirs(files_dir, exist_ok=True)
    out_path = os.path.join(files_dir, new_filename)

    base, ext = os.path.splitext(new_filename)
    counter = 1
    while os.path.exists(out_path):
        out_path = os.path.join(files_dir, f"{base}_{counter}{ext}")
        counter += 1

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(full_data, f, ensure_ascii=False, indent=2)

    return out_path
