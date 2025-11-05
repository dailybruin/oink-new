from __future__ import annotations

import io
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from django.conf import settings
from bson import ObjectId

from oink_project.mongo import get_bucket, get_collection

# This new code is lightweight helper functions around GridFS so models/views can store and retrieve files easily

_ASSET_INDEX_INITIALIZED = False


def _ensure_asset_indexes() -> None:
    """Create indexes for the unified asset collection (safe to call repeatedly)."""
    global _ASSET_INDEX_INITIALIZED
    if _ASSET_INDEX_INITIALIZED:
        return
    try:
        collection_name = getattr(settings, "MONGODB_ASSET_COLLECTION", "package_assets")
        collection = get_collection(collection_name)
        collection.create_index("slug", unique=True)
        collection.create_index([("slug", 1), ("assets.asset_type", 1)])
    except Exception:
        return
    _ASSET_INDEX_INITIALIZED = True


def store_bytes(
    name: str,
    content_type: str,
    data: bytes,
    *,
    slug: Optional[str] = None,
    asset_type: Optional[str] = None,
    extra_metadata: Optional[Dict[str, str]] = None,
) -> str:
    
    """ Store bytes in GridFS and return the file ObjectId as a string """
    bucket = get_bucket()
    meta = {"contentType": content_type or "application/octet-stream"}
    if slug:
        meta["slug"] = slug
    if asset_type:
        meta["assetType"] = asset_type
    if extra_metadata:
        for key, value in extra_metadata.items():
            if value is not None:
                meta[key] = value
    file_id = bucket.upload_from_stream(name, io.BytesIO(data), metadata=meta)
    return str(file_id)


def store_text(
    name: str,
    text: str,
    content_type: str = "text/plain; charset=utf-8",
    *,
    slug: Optional[str] = None,
    asset_type: str = "aml",
    extra_metadata: Optional[Dict[str, str]] = None,
) -> str:
    
    """ Store text in GridFS and return the file ObjectId as a string, which can be used later to retrieve the file 
    
    Assumes UTF-8 encoding for the text."""
    return store_bytes(
        name=name,
        content_type=content_type,
        data=text.encode("utf-8"),
        slug=slug,
        asset_type=asset_type,
        extra_metadata=extra_metadata,
    )


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
        # Access metadata before closing the stream
        metadata = getattr(stream, 'metadata', {}) or {}
        content_type = metadata.get("contentType") or "application/octet-stream"
        filename = getattr(stream, 'filename', None) or file_id
    finally:
        stream.close()
    data = out.getvalue()

    return data, content_type, filename


def update_package_asset_index(
    slug: str,
    *,
    aml_assets: Optional[List[Dict[str, str]]] = None,
    image_assets: Optional[List[Dict[str, str]]] = None,
) -> None:
    """Persist a unified view of GridFS assets for a slug."""
    if not slug:
        return
    if not getattr(settings, "MONGODB_FILESTORE_ENABLED", False):
        return

    collection_name = getattr(settings, "MONGODB_ASSET_COLLECTION", "package_assets")
    try:
        collection = get_collection(collection_name)
    except Exception:
        return

    assets: List[Dict[str, str]] = []
    for entry in aml_assets or []:
        file_id = entry.get("file_id") or entry.get("id")
        name = entry.get("name")
        if file_id and name:
            assets.append(
                {
                    "file_id": file_id,
                    "name": name,
                    "asset_type": entry.get("asset_type", "aml"),
                    "content_type": entry.get("content_type", "text/plain"),
                    "source": entry.get("source", "drive"),
                    "source_id": entry.get("source_id") or entry.get("sourceId"),
                }
            )

    for entry in image_assets or []:
        file_id = entry.get("file_id") or entry.get("id")
        name = entry.get("name")
        if file_id and name:
            assets.append(
                {
                    "file_id": file_id,
                    "name": name,
                    "asset_type": entry.get("asset_type", "image"),
                    "content_type": entry.get("content_type", "application/octet-stream"),
                    "source": entry.get("source", "drive"),
                    "source_id": entry.get("source_id") or entry.get("sourceId"),
                }
            )

    now = datetime.utcnow()
    payload = {
        "slug": slug,
        "assets": assets,
        "has_aml": any(asset.get("asset_type") == "aml" for asset in assets),
        "has_chunks": any(asset.get("asset_type") in {"aml", "chunk"} for asset in assets),
        "has_images": any(asset.get("asset_type") == "image" for asset in assets),
        "updated_at": now,
    }

    update_doc = {
        "$set": payload,
        "$setOnInsert": {"created_at": now},
    }

    try:
        _ensure_asset_indexes()
        collection.update_one({"slug": slug}, update_doc, upsert=True)
    except Exception:
        # Unified asset index should not interrupt primary workflow if Mongo write fails.
        return
