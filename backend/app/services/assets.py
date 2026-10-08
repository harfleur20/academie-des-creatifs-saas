from pathlib import Path
import re
from io import BytesIO
from uuid import uuid4
from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from app.core.config import settings

ALLOWED={".png":5*1024*1024,".jpg":5*1024*1024,".jpeg":5*1024*1024,".webp":5*1024*1024,".pdf":15*1024*1024,".zip":50*1024*1024,".rar":50*1024*1024,".docx":15*1024*1024,".mp4":50*1024*1024,".webm":50*1024*1024,".mov":50*1024*1024}

PUBLIC_CONTENT_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
}


def _validate_public_asset(ext: str, raw: bytes) -> str:
    valid = (
        (ext == ".png" and raw.startswith(b"\x89PNG\r\n\x1a\n"))
        or (ext in {".jpg", ".jpeg"} and raw.startswith(b"\xff\xd8\xff"))
        or (ext == ".webp" and raw.startswith(b"RIFF") and raw[8:12] == b"WEBP")
        or (ext == ".pdf" and raw.startswith(b"%PDF-"))
    )
    if not valid:
        raise HTTPException(415, "Le contenu du fichier ne correspond pas au format choisi.")
    if ext != ".pdf":
        expected_format = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}[ext]
        try:
            with Image.open(BytesIO(raw)) as image:
                if image.format != expected_format or image.width * image.height > 40_000_000:
                    raise ValueError("Image invalide ou trop grande.")
                image.verify()
        except (OSError, ValueError, UnidentifiedImageError) as exc:
            raise HTTPException(415, "Image invalide.") from exc
    return PUBLIC_CONTENT_TYPES[ext]


async def store_submission_asset(file: UploadFile, organization_id: int, user_id: int):
    name = Path(file.filename or "file").name
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(415, "Format non autorisé.")
    raw = await file.read(ALLOWED[ext] + 1)
    if len(raw) > ALLOWED[ext]:
        raise HTTPException(413, "Fichier trop volumineux.")
    filename = f"{uuid4().hex}{ext}"
    key = f"schools/{organization_id}/assignments/{user_id}/{filename}"
    if settings.storage_provider == "r2":
        if not settings.r2_configured or not settings.r2_private_bucket_name or settings.r2_private_bucket_name == settings.r2_bucket_name:
            raise HTTPException(503, "Un bucket R2 privé distinct est requis pour les devoirs.")
        import boto3
        client = boto3.client("s3", endpoint_url=settings.r2_endpoint_url, aws_access_key_id=settings.r2_access_key_id, aws_secret_access_key=settings.r2_secret_access_key, region_name="auto")
        client.put_object(Bucket=settings.r2_private_bucket_name, Key=key, Body=raw, ContentType=file.content_type or "application/octet-stream")
    else:
        if settings.environment == "production":
            raise HTTPException(503, "Le stockage local est désactivé en production.")
        destination = Path(__file__).resolve().parents[2] / "private_uploads" / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
    return {
        "filename": name,
        "public_url": f"{settings.backend_public_url}{settings.api_prefix}/assignments/submission-assets/{user_id}/{filename}",
        "size": len(raw),
        "content_type": file.content_type or "application/octet-stream",
    }


def validate_submission_asset(url: str, organization_id: int, user_id: int) -> None:
    prefix = f"{settings.backend_public_url}{settings.api_prefix}/assignments/submission-assets/{user_id}/"
    filename = url.removeprefix(prefix)
    if not url.startswith(prefix) or not re.fullmatch(r"[a-f0-9]{32}\.[a-z0-9]+", filename) or Path(filename).suffix not in ALLOWED:
        raise HTTPException(422, "Utilisez un fichier téléversé pour cette remise.")
    key = f"schools/{organization_id}/assignments/{user_id}/{filename}"
    if settings.storage_provider == "r2":
        import boto3
        from botocore.exceptions import ClientError
        client = boto3.client("s3", endpoint_url=settings.r2_endpoint_url, aws_access_key_id=settings.r2_access_key_id, aws_secret_access_key=settings.r2_secret_access_key, region_name="auto")
        try:
            client.head_object(Bucket=settings.r2_private_bucket_name, Key=key)
        except ClientError as exc:
            raise HTTPException(422, "Fichier de remise introuvable.") from exc
    elif not (Path(__file__).resolve().parents[2] / "private_uploads" / key).is_file():
        raise HTTPException(422, "Fichier de remise introuvable.")

async def store_assignment_asset(file:UploadFile,organization_id:int):
    name=Path(file.filename or "file").name
    ext=Path(name).suffix.lower()
    if ext not in ALLOWED: raise HTTPException(415,"Format non autorisé.")
    raw=await file.read(ALLOWED[ext]+1)
    if len(raw)>ALLOWED[ext]: raise HTTPException(413,"Fichier trop volumineux.")
    filename = f"{uuid4().hex}{ext}"
    key=f"schools/{organization_id}/resources/{filename}"
    if settings.storage_provider=="r2":
        if not settings.r2_configured or not settings.r2_private_bucket_name or settings.r2_private_bucket_name == settings.r2_bucket_name:
            raise HTTPException(503,"Un bucket R2 privé distinct est requis pour les ressources.")
        import boto3
        client=boto3.client("s3",endpoint_url=settings.r2_endpoint_url,aws_access_key_id=settings.r2_access_key_id,aws_secret_access_key=settings.r2_secret_access_key,region_name="auto")
        client.put_object(Bucket=settings.r2_private_bucket_name,Key=key,Body=raw,ContentType=file.content_type or "application/octet-stream")
    else:
        if settings.environment=="production": raise HTTPException(503,"Le stockage local est désactivé en production.")
        root=Path(__file__).resolve().parents[2]/"private_uploads"; dest=root/key; dest.parent.mkdir(parents=True,exist_ok=True); dest.write_bytes(raw)
    url=f"{settings.backend_public_url}{settings.api_prefix}/assignments/resource-assets/{filename}"
    return {"filename":name,"public_url":url,"size":len(raw),"content_type":file.content_type or "application/octet-stream"}



async def store_profile_avatar(file: UploadFile, user_id: int):
    name = Path(file.filename or "avatar").name
    ext = Path(name).suffix.lower()
    image_limits = {
        ".png": 2 * 1024 * 1024,
        ".jpg": 2 * 1024 * 1024,
        ".jpeg": 2 * 1024 * 1024,
        ".webp": 2 * 1024 * 1024,
    }
    if ext not in image_limits:
        raise HTTPException(415, "Format autorisé : PNG, JPG ou WebP.")
    raw = await file.read(image_limits[ext] + 1)
    if len(raw) > image_limits[ext]:
        raise HTTPException(413, "La photo de profil ne doit pas dépasser 2 Mo.")
    content_type = _validate_public_asset(ext, raw)

    key = f"users/{user_id}/avatar-{uuid4().hex}{ext}"
    if settings.storage_provider == "r2":
        if not settings.r2_configured:
            raise HTTPException(503, "Stockage R2 non configuré.")
        import boto3
        client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name="auto",
        )
        client.put_object(
            Bucket=settings.r2_bucket_name,
            Key=key,
            Body=raw,
            ContentType=content_type,
        )
        url = f"{settings.r2_public_base_url.rstrip('/')}/{key}"
    else:
        if settings.environment == "production":
            raise HTTPException(503, "Le stockage local est désactivé en production.")
        root = Path(__file__).resolve().parents[2] / "uploads"
        destination = root / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
        url = f"{settings.backend_public_url}/uploads/{key}"

    return {
        "filename": name,
        "public_url": url,
        "size": len(raw),
        "content_type": content_type,
    }



async def store_school_asset(file: UploadFile, organization_id: int):
    name = Path(file.filename or "asset").name
    ext = Path(name).suffix.lower()
    limits = {
        ".png": 5 * 1024 * 1024,
        ".jpg": 5 * 1024 * 1024,
        ".jpeg": 5 * 1024 * 1024,
        ".webp": 5 * 1024 * 1024,
        ".pdf": 15 * 1024 * 1024,
    }
    if ext not in limits:
        raise HTTPException(415, "Format non autorisé.")
    raw = await file.read(limits[ext] + 1)
    if len(raw) > limits[ext]:
        raise HTTPException(413, "Fichier trop volumineux.")
    content_type = _validate_public_asset(ext, raw)
    key = f"schools/{organization_id}/brand/{uuid4().hex}{ext}"
    if settings.storage_provider == "r2":
        if not settings.r2_configured:
            raise HTTPException(503, "Stockage R2 non configuré.")
        import boto3
        client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name="auto",
        )
        client.put_object(
            Bucket=settings.r2_bucket_name,
            Key=key,
            Body=raw,
            ContentType=content_type,
            ContentDisposition="attachment" if ext == ".pdf" else "inline",
        )
        url = f"{settings.r2_public_base_url.rstrip('/')}/{key}"
    else:
        if settings.environment == "production":
            raise HTTPException(503, "Le stockage local est désactivé en production.")
        root = Path(__file__).resolve().parents[2] / "uploads"
        destination = root / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
        url = f"{settings.backend_public_url}/uploads/{key}"
    return {
        "filename": name,
        "public_url": url,
        "size": len(raw),
        "content_type": content_type,
    }


async def store_class_discussion_image(
    file: UploadFile, organization_id: int, session_id: int
):
    name = Path(file.filename or "image").name
    ext = Path(name).suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(415, "Format autorisé : PNG, JPG ou WebP.")
    limit = 5 * 1024 * 1024
    raw = await file.read(limit + 1)
    if len(raw) > limit:
        raise HTTPException(413, "L'image ne doit pas dépasser 5 Mo.")
    content_type = _validate_public_asset(ext, raw)
    key = f"schools/{organization_id}/discussion/{session_id}/{uuid4().hex}{ext}"
    if settings.storage_provider == "r2":
        if not settings.r2_configured:
            raise HTTPException(503, "Stockage R2 non configuré.")
        import boto3
        client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name="auto",
        )
        client.put_object(
            Bucket=settings.r2_bucket_name,
            Key=key,
            Body=raw,
            ContentType=content_type,
            ContentDisposition="inline",
        )
        url = f"{settings.r2_public_base_url.rstrip('/')}/{key}"
    else:
        if settings.environment == "production":
            raise HTTPException(503, "Le stockage local est désactivé en production.")
        destination = Path(__file__).resolve().parents[2] / "uploads" / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
        url = f"{settings.backend_public_url}/uploads/{key}"
    return {
        "filename": name,
        "public_url": url,
        "size": len(raw),
        "content_type": content_type,
    }
