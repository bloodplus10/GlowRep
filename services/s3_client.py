import io
import uuid
from minio import Minio
from config import settings

client = Minio(endpoint=settings.MINIO_ENDPOINT, access_key=settings.MINIO_ACCESS_KEY, secret_key=settings.MINIO_SECRET_KEY, secure=settings.MINIO_SECURE)

async def ensure_bucket():
    if not client.bucket_exists(settings.MINIO_BUCKET):
        client.make_bucket(settings.MINIO_BUCKET)
        print(f"Bucket '{settings.MINIO_BUCKET}' created.")

async def upload_photo(file_bytes: bytes, extension: str = "jpg") -> str:
    object_name = f"{uuid.uuid4()}.{extension}"
    client.put_object(bucket_name=settings.MINIO_BUCKET, object_name=object_name, data=io.BytesIO(file_bytes), length=len(file_bytes), content_type=f"image/{extension}")
    return object_name

def get_public_url(object_name: str) -> str:
    return client.presigned_get_object(bucket_name=settings.MINIO_BUCKET, object_name=object_name)