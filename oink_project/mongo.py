import os
from functools import lru_cache
from typing import Optional

from pymongo import MongoClient
from gridfs import GridFSBucket

# This new file will handle MongoDB connection and GridFS bucket access
@lru_cache(maxsize=1)
def get_client() -> MongoClient:
    
    #Connect to MongoDB with URI from .env
    uri = os.getenv("MONGODB_URI")
    
    # Let pymongo validate/parse options to keep defaults simple here
    return MongoClient(uri)


def get_db(name: Optional[str] = None):
    """This was optional to do, but to make it clean, 
    
    I set the name "oink" for the database as default"""
    db_name = name or os.getenv("MONGODB_DB_NAME")
    return get_client()[db_name]


def get_bucket(db_name: Optional[str] = None, bucket_name: Optional[str] = None) -> GridFSBucket:
    """Same here, this was optional to do, but to make it clean, 
    
    I set the name "files" for the bucket inside the database as default"""
    _db = get_db(db_name)
    _bucket = bucket_name or os.getenv("MONGODB_BUCKET")
    return GridFSBucket(_db, bucket_name=_bucket)
