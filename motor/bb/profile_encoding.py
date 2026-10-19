"""Deterministic, bounded profile packaging for private server files.

Compression is storage encoding, not encryption. Decoded profiles keep the same
canonical hash as plain JSON. No user upload can select or supply these files.
"""
import base64
import gzip
from hashlib import sha256
from io import BytesIO
import json

from .flora_jobs import canonical

SCHEMA='bb-compressed-profile/1.0'
MAX_BYTES=32*1024*1024
MAX_ENCODED_BYTES=2*1024*1024


def encode_profile(profile):
    data=canonical(profile).encode()
    if len(data)>MAX_BYTES:
        raise ValueError('Beslutsprofilen överskrider lagringsgränsen.')
    encoded=base64.b64encode(gzip.compress(data,mtime=0)).decode('ascii')
    if len(encoded)>MAX_ENCODED_BYTES:
        raise ValueError('Den komprimerade beslutsprofilen är för stor.')
    return dict(schema_version=SCHEMA,encoding='gzip+base64',uncompressed_bytes=len(data),
                sha256=sha256(data).hexdigest(),data=encoded)


def decode_profile(value):
    if not isinstance(value,dict) or value.get('schema_version')!=SCHEMA:
        return value
    if set(value)!={'schema_version','encoding','uncompressed_bytes','sha256','data'}:
        raise ValueError('Komprimerad beslutsprofil har okända fält.')
    size=value['uncompressed_bytes']
    if (value['encoding']!='gzip+base64' or type(size) is not int or not 0<size<=MAX_BYTES
            or not isinstance(value['data'],str) or len(value['data'])>MAX_ENCODED_BYTES
            or not isinstance(value['sha256'],str) or len(value['sha256'])!=64):
        raise ValueError('Komprimerad beslutsprofil har ogiltiga gränser.')
    packed=base64.b64decode(value['data'],validate=True)
    with gzip.GzipFile(fileobj=BytesIO(packed)) as stream:
        data=stream.read(size+1)
    if len(data)!=size or sha256(data).hexdigest()!=value['sha256']:
        raise ValueError('Beslutsprofilens storlek eller kontrollsumma stämmer inte.')
    result=json.loads(data)
    if not isinstance(result,dict) or result.get('schema_version')==SCHEMA:
        raise ValueError('Komprimerad beslutsprofil saknar en enkel profil.')
    return result
