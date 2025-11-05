from __future__ import annotations

import io
from typing import Optional, Tuple

from bson import ObjectId

from oink_project.mongo import get_bucket

# This new code is lightweight helper functions around GridFS so models/views can store and retrieve files easily

def store_bytes(name: str, content_type: str, data: bytes) -> str:
    
    """ Store bytes in GridFS and return the file ObjectId as a string """
    bucket = get_bucket()
    meta = {"contentType": content_type or "application/octet-stream"}
    file_id = bucket.upload_from_stream(name, io.BytesIO(data), metadata=meta)
    return str(file_id)


def store_text(name: str, text: str, content_type: str = "text/plain; charset=utf-8") -> str:
    
    """ Store text in GridFS and return the file ObjectId as a string, which can be used later to retrieve the file 
    
    Assumes UTF-8 encoding for the text."""
    return store_bytes(name=name, content_type=content_type, data=text.encode("utf-8"))


def read_file(file_id: str) -> Tuple[bytes, str, str]:
    
    """ Read a GridFS file and return (data, content_type, filename) """
    bucket = get_bucket()
    oid = ObjectId(file_id)
    
    """ Download to memory for large files, stream in chunks in a view """
    out = io.BytesIO()
    stream = bucket.open_download_stream(oid)
    
    """ Here we read the file in chunks to avoid loading large files entirely into memory """
    try:
        out.write(stream.read())
    finally:
        stream.close()
    data = out.getvalue()
    
    """ Get content type and filename from file document metadata """
    content_type = (stream.file_document.get("metadata", {}) or {}).get("contentType") or "application/octet-stream"
    filename = stream.filename or file_id
    return data, content_type, filename
