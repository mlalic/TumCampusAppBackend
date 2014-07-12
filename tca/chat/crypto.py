from Crypto.Signature import PKCS1_v1_5
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA

import base64


def verify(message, signature, public_key):
    """
    Verify whether the given signature of the message was produced using
    the private key paired with the given public key.

    :param message: A unicode string representing the message whose
        signature is being verified
    :param signature: The signature of the message represented as a base64
        encoded bytearray
    :param public_key: The public key to validate against, represented as
        a base64 encoded bytearray
    """
    if message is None:
        return False

    message = message.encode('utf-8')

    try:
        signature = base64.decodestring(signature)
        public_key = base64.decodestring(public_key)
    except:
        # If either the signature or the public key cannot be converted
        # to bytes (i.e. the base64 representation is invalid), indicate
        # that the verification failed
        return False
    try:
        public_key = RSA.importKey(public_key)
    except:
        # Invalid key => signature does not match it
        return False

    message_hash = SHA.new()
    message_hash.update(message)

    try:
        verifier = PKCS1_v1_5.new(public_key)
        return verifier.verify(message_hash, signature)
    except:
        # Error while verifying => invalid signature
        return False
