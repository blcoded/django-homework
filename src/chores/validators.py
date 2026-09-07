import os
from django.core.exceptions import ValidationError

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def validate_image_proof(file_obj):
    """
    Validate uploaded photo evidence for chore completion:
    - Verifies file size <= 10MB
    - Verifies file extension in [.jpg, .jpeg, .png, .webp, .gif]
    - Verifies content_type MIME type
    - Verifies binary signature / magic bytes
    """
    if not file_obj:
        return

    # Check size
    if file_obj.size > MAX_FILE_SIZE_BYTES:
        raise ValidationError("Photo proof size cannot exceed 10MB.")

    # Check extension
    ext = os.path.splitext(file_obj.name)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file extension '{ext}'. Allowed image extensions: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}."
        )

    # Check content_type if available
    content_type = getattr(file_obj, "content_type", None)
    if content_type and content_type.lower() not in ALLOWED_IMAGE_MIME_TYPES:
        raise ValidationError(
            f"Invalid file MIME type '{content_type}'. Must be an image (JPEG, PNG, WebP, GIF)."
        )

    # Check binary header
    pos = file_obj.tell() if hasattr(file_obj, "tell") else 0
    header = file_obj.read(16)
    if hasattr(file_obj, "seek"):
        file_obj.seek(pos)

    if not header:
        raise ValidationError("Uploaded photo file is empty.")

    is_jpeg = header.startswith(b"\xff\xd8\xff")
    is_png = header.startswith(b"\x89PNG\r\n\x1a\n")
    is_gif = header.startswith(b"GIF87a") or header.startswith(b"GIF89a")
    is_webp = header.startswith(b"RIFF") and len(header) >= 12 and header[8:12] == b"WEBP"

    if not (is_jpeg or is_png or is_gif or is_webp):
        raise ValidationError(
            "Uploaded file is not a valid image format. Supported formats: JPEG, PNG, WebP, GIF."
        )
