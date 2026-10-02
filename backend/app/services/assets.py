from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException, UploadFile
from app.core.config import settings

ALLOWED={".png":5*1024*1024,".jpg":5*1024*1024,".jpeg":5*1024*1024,".webp":5*1024*1024,".pdf":15*1024*1024,".zip":50*1024*1024,".rar":50*1024*1024,".docx":15*1024*1024,".mp4":50*1024*1024,".webm":50*1024*1024,".mov":50*1024*1024}

async def store_assignment_asset(file:UploadFile,organization_id:int):
    name=Path(file.filename or "file").name
    ext=Path(name).suffix.lower()
    if ext not in ALLOWED: raise HTTPException(415,"Format non autorisé.")
    raw=await file.read(ALLOWED[ext]+1)
    if len(raw)>ALLOWED[ext]: raise HTTPException(413,"Fichier trop volumineux.")
    key=f"schools/{organization_id}/assignments/{uuid4().hex}{ext}"
    if settings.storage_provider=="r2":
        if not settings.r2_configured: raise HTTPException(503,"Stockage R2 non configuré.")
        import boto3
        client=boto3.client("s3",endpoint_url=settings.r2_endpoint_url,aws_access_key_id=settings.r2_access_key_id,aws_secret_access_key=settings.r2_secret_access_key,region_name="auto")
        client.put_object(Bucket=settings.r2_bucket_name,Key=key,Body=raw,ContentType=file.content_type or "application/octet-stream")
        url=f"{settings.r2_public_base_url.rstrip('/')}/{key}"
    else:
        if settings.environment=="production": raise HTTPException(503,"Le stockage local est désactivé en production.")
        root=Path(__file__).resolve().parents[2]/"uploads"; dest=root/key; dest.parent.mkdir(parents=True,exist_ok=True); dest.write_bytes(raw)
        url=f"{settings.backend_public_url}/uploads/{key}"
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
            ContentType=file.content_type or "application/octet-stream",
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
        "content_type": file.content_type or "application/octet-stream",
    }
