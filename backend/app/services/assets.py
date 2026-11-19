import math
import logging
import re
import struct
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException, UploadFile
from mutagen import MutagenError
from mutagen.mp4 import MP4
from PIL import Image, UnidentifiedImageError
from app.core.config import settings
from app.services.object_storage import b2_client

logger = logging.getLogger(__name__)

ALLOWED={".png":5*1024*1024,".jpg":5*1024*1024,".jpeg":5*1024*1024,".webp":5*1024*1024,".pdf":15*1024*1024,".zip":50*1024*1024,".rar":50*1024*1024,".docx":15*1024*1024,".mp4":50*1024*1024,".webm":50*1024*1024,".mov":50*1024*1024}
PRESENTATION_VIDEO_MAX_BYTES = 50 * 1024 * 1024
PRESENTATION_VIDEO_MAX_SECONDS = 3 * 60

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


class _NamedBytesIO(BytesIO):
    def __init__(self, raw: bytes, name: str):
        super().__init__(raw)
        self.name = name


def _store_public_asset(raw: bytes, key: str, filename: str, resource_type: str) -> str:
    if settings.public_asset_provider == "cloudinary":
        if not settings.cloudinary_configured:
            raise HTTPException(503, "Stockage public Cloudinary non configuré.")
        import cloudinary
        from cloudinary import uploader

        cloudinary.config(
            cloud_name=settings.cloudinary_cloud_name,
            api_key=settings.cloudinary_api_key,
            api_secret=settings.cloudinary_api_secret,
            secure=True,
        )
        public_id = key.rsplit(".", 1)[0] if Path(key).suffix else key
        try:
            result = uploader.upload(
                _NamedBytesIO(raw, filename),
                public_id=public_id,
                resource_type=resource_type,
                type="upload",
                overwrite=False,
                use_filename=False,
                unique_filename=False,
            )
        except Exception as exc:
            logger.exception("Échec de l'envoi d'un média public vers Cloudinary")
            raise HTTPException(502, "Impossible d'envoyer le fichier vers le stockage public.") from exc
        secure_url = result.get("secure_url")
        if not secure_url:
            raise HTTPException(502, "Cloudinary n'a pas renvoyé l'URL du fichier.")
        return secure_url

    if settings.environment == "production":
        raise HTTPException(503, "Le stockage public Cloudinary est requis en production.")
    destination = Path(__file__).resolve().parents[2] / "uploads" / key
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw)
    return f"{settings.backend_public_url}/uploads/{key}"


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
    if settings.storage_provider == "b2":
        if not settings.b2_configured or not settings.b2_private_bucket_name or settings.b2_private_bucket_name == settings.b2_bucket_name:
            raise HTTPException(503, "Un bucket B2 privé distinct est requis pour les devoirs.")
        client = b2_client()
        client.put_object(Bucket=settings.b2_private_bucket_name, Key=key, Body=raw, ContentType=file.content_type or "application/octet-stream")
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
    if settings.storage_provider == "b2":
        from botocore.exceptions import ClientError
        client = b2_client()
        try:
            client.head_object(Bucket=settings.b2_private_bucket_name, Key=key)
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
    if settings.storage_provider=="b2":
        if not settings.b2_configured or not settings.b2_private_bucket_name or settings.b2_private_bucket_name == settings.b2_bucket_name:
            raise HTTPException(503,"Un bucket B2 privé distinct est requis pour les ressources.")
        client=b2_client()
        client.put_object(Bucket=settings.b2_private_bucket_name,Key=key,Body=raw,ContentType=file.content_type or "application/octet-stream")
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
    url = _store_public_asset(raw, key, name, "image")

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
        # Cloudinary Free supports public PDFs up to 10 MB; private course PDFs keep their 15 MB limit.
        ".pdf": 10 * 1024 * 1024,
    }
    if ext not in limits:
        raise HTTPException(415, "Format non autorisé.")
    raw = await file.read(limits[ext] + 1)
    if len(raw) > limits[ext]:
        raise HTTPException(413, "Le PDF public ne doit pas dépasser 10 Mo." if ext == ".pdf" else "Fichier trop volumineux.")
    content_type = _validate_public_asset(ext, raw)
    key = f"schools/{organization_id}/brand/{uuid4().hex}{ext}"
    url = _store_public_asset(raw, key, name, "image")
    return {
        "filename": name,
        "public_url": url,
        "size": len(raw),
        "content_type": content_type,
    }


async def store_formation_video_asset(file: UploadFile, organization_id: int):
    name = Path(file.filename or "presentation.mp4").name
    if Path(name).suffix.lower() != ".mp4":
        raise HTTPException(415, "Format autorisé : MP4 (H.264 recommandé).")
    raw = await file.read(PRESENTATION_VIDEO_MAX_BYTES + 1)
    if len(raw) > PRESENTATION_VIDEO_MAX_BYTES:
        raise HTTPException(413, "La vidéo de présentation ne doit pas dépasser 50 Mo.")
    if len(raw) < 12 or raw[4:8] != b"ftyp":
        raise HTTPException(415, "Le fichier ne contient pas une vidéo MP4 valide.")
    try:
        duration = MP4(BytesIO(raw)).info.length
    except (MutagenError, OSError, ValueError, EOFError, struct.error) as exc:
        raise HTTPException(415, "Le fichier ne contient pas une vidéo MP4 valide.") from exc
    if duration is None or not math.isfinite(duration) or duration <= 0:
        raise HTTPException(415, "Impossible de lire la durée de cette vidéo MP4.")
    if duration > PRESENTATION_VIDEO_MAX_SECONDS:
        raise HTTPException(422, "La vidéo de présentation ne doit pas dépasser 3 minutes.")

    filename = f"{uuid4().hex}.mp4"
    key = f"schools/{organization_id}/presentations/{filename}"
    url = _store_public_asset(raw, key, name, "video")

    return {
        "filename": name,
        "public_url": url,
        "size": len(raw),
        "content_type": "video/mp4",
        "duration_seconds": duration,
    }


UPLOADS_ROOT = Path(__file__).resolve().parents[2] / "uploads"
PRESENTATION_VIDEO_NAME = re.compile(r"[0-9a-f]{32}\.mp4")


def presentation_video_location(url: str | None, organization_id: int) -> tuple[str, str] | None:
    """Where a presentation video this school uploaded here is stored: (provider, object key).

    None for any other address: a formation only shows a video imported from its page.
    """
    if not url:
        return None
    cloudinary_prefix = f"{settings.cloudinary_public_base_url}/video/upload/"
    if settings.cloudinary_public_base_url and url.startswith(cloudinary_prefix):
        delivered_path = url.removeprefix(cloudinary_prefix).split("?", 1)[0]
        delivered_path = re.sub(r"^v[0-9]+/", "", delivered_path)
        public_id = delivered_path.rsplit(".", 1)[0]
        expected_prefix = f"schools/{organization_id}/presentations/"
        filename = public_id.removeprefix(expected_prefix)
        if public_id.startswith(expected_prefix) and re.fullmatch(r"[0-9a-f]{32}", filename):
            return "cloudinary", public_id

    bases = [("local", f"{settings.backend_public_url.rstrip('/')}/uploads")]
    if settings.b2_public_base_url:
        bases.append(("b2", settings.b2_public_base_url.rstrip("/")))
    for storage, base in bases:
        prefix = f"{base}/schools/{organization_id}/presentations/"
        if url.startswith(prefix) and PRESENTATION_VIDEO_NAME.fullmatch(url[len(prefix):]):
            return storage, f"schools/{organization_id}/presentations/{url[len(prefix):]}"
    return None


def delete_presentation_video(location: tuple[str, str]) -> None:
    """Remove a presentation video that no formation shows anymore. Best effort: a failure
    only leaves a file behind."""
    storage, key = location
    try:
        if storage == "cloudinary":
            if not settings.cloudinary_configured:
                return
            import cloudinary
            from cloudinary import uploader

            cloudinary.config(
                cloud_name=settings.cloudinary_cloud_name,
                api_key=settings.cloudinary_api_key,
                api_secret=settings.cloudinary_api_secret,
                secure=True,
            )
            uploader.destroy(key, resource_type="video", type="upload", invalidate=True)
        elif storage == "b2":
            if not settings.b2_configured:
                return
            b2_client().delete_object(Bucket=settings.b2_bucket_name, Key=key)
        else:
            path = (UPLOADS_ROOT / key).resolve()
            path.relative_to(UPLOADS_ROOT.resolve())
            path.unlink(missing_ok=True)
    except Exception:
        return


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
    url = _store_public_asset(raw, key, name, "image")
    return {
        "filename": name,
        "public_url": url,
        "size": len(raw),
        "content_type": content_type,
    }
