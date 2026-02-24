"""
Upload images from Google Drive to S3 with key format:
  images/{package_slug}/{filename_stem}-{md5_hash}.{ext}
Matches Kerckhoff behavior so URLs look like:
  https://assets3.dailybruin.com/images/rivalry-issue-25-26/A.sp_.football.feature.MJD_.11.23.25.file_-19a0de0cfc3c132740b6be3caa6980bb.jpg
"""
import hashlib
import logging
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

# Max dimension for resized images (same as Kerckhoff)
MAX_IMAGE_SIZE = 1024


def _s3_enabled():
    """Return True if S3 upload is configured with real credentials."""
    bucket = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', None)
    domain = getattr(settings, 'S3_DOMAIN_OF_UPLOADED_IMAGES', None)
    if not bucket or not domain:
        return False
    # Skip if keys look like placeholders (e.g. "key") so dev doesn't spam InvalidAccessKeyId
    access_key = (getattr(settings, 'AWS_ACCESS_KEY_ID', None) or '').strip()
    if access_key and access_key.lower() in ('key', 'your_key', 'your_access_key', 'xxx'):
        return False
    if not access_key:
        # Rely on boto3 default chain (env, IAM role); consider it enabled if bucket+domain set
        pass
    return True


def _get_s3_client():
    """Return boto3 S3 client or None if not configured."""
    if not _s3_enabled():
        return None
    try:
        import boto3
        kwargs = {
            'region_name': getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1'),
        }
        access_key = getattr(settings, 'AWS_ACCESS_KEY_ID', None)
        secret_key = getattr(settings, 'AWS_SECRET_ACCESS_KEY', None)
        if access_key and secret_key:
            kwargs['aws_access_key_id'] = access_key
            kwargs['aws_secret_access_key'] = secret_key
        # Otherwise boto3 uses default chain (env vars, IAM role, etc.)
        return boto3.client('s3', **kwargs)
    except Exception as e:
        logger.exception('Failed to create S3 client: %s', e)
        return None


def _resize_image(data: bytes, content_type: str, max_size: int = MAX_IMAGE_SIZE) -> bytes:
    """Resize image so no side exceeds max_size. Returns bytes in same format."""
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(data))
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        w, h = img.size
        if w <= max_size and h <= max_size:
            out = io.BytesIO()
            img.save(out, format='JPEG', quality=85)
            return out.getvalue()
        if w >= h:
            new_w, new_h = max_size, int(h * max_size / w)
        else:
            new_w, new_h = int(w * max_size / h), max_size
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        img.save(out, format='JPEG', quality=85)
        return out.getvalue()
    except Exception as e:
        logger.warning('Resize failed, using original bytes: %s', e)
        return data


def upload_image_to_s3(
    image_bytes: bytes,
    package_slug: str,
    original_filename: str,
    content_type: str,
) -> dict | None:
    """
    Upload image to S3 with key images/{package_slug}/{stem}-{md5}.{ext}.
    Optionally resizes to max 1024x1024 before upload.
    Returns dict with url, key, hash or None on failure.
    """
    if not _s3_enabled():
        return None
    client = _get_s3_client()
    if not client:
        return None

    path = Path(original_filename)
    stem = path.stem

    try:
        resized = _resize_image(image_bytes, content_type)
        image_hash = hashlib.md5(resized).hexdigest()
    except Exception as e:
        logger.warning('Resize failed for %s: %s', original_filename, e)
        resized = image_bytes
        image_hash = hashlib.md5(resized).hexdigest()

    # Resized output is always JPEG; key matches Kerckhoff: images/{slug}/{stem}-{hash}.jpg
    key = f"images/{package_slug}/{stem}-{image_hash}.jpg"
    bucket = settings.AWS_STORAGE_BUCKET_NAME
    domain = (settings.S3_DOMAIN_OF_UPLOADED_IMAGES or '').rstrip('/')
    url = f"{domain}/{key}"

    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=resized,
            ContentType='image/jpeg',
            ACL='public-read',
        )
        logger.info('[S3] Uploaded %s -> %s', original_filename, key)
        return {'url': url, 'key': key, 'hash': image_hash}
    except Exception as e:
        logger.exception('S3 upload failed for %s: %s', key, e)
        return None
