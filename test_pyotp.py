import pyotp
import hashlib
import time

secret = 'JBSWY3DPEHPK3PXP'
totp = pyotp.TOTP(secret, digest=hashlib.sha1)
print(totp.now())

totp2 = pyotp.TOTP(secret, digest=hashlib.sha256)
print(totp2.now())
