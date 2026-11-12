from __future__ import annotations

from urllib.parse import quote, urljoin, urlsplit

import httpx

from .config import Settings

ALLOWED_MEDIA_HOSTS = (
    "cdninstagram.com",
    "fbcdn.net",
    "fbsbx.com",
)
MAX_IMAGE_BYTES = 15 * 1024 * 1024
SIGNED_URL_TTL_SECONDS = 3600
IMAGE_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
    "image/avif": "avif",
}


class MediaStorageConfigurationError(RuntimeError):
    pass


class MediaStorageError(RuntimeError):
    pass


class SupabaseMediaStorage:
    def __init__(
        self,
        settings: Settings,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not settings.supabase_url:
            raise MediaStorageConfigurationError("SUPABASE_URL non está configurado")
        if not settings.supabase_service_role_key:
            raise MediaStorageConfigurationError(
                "SUPABASE_SERVICE_ROLE_KEY non está configurado no servidor"
            )
        self._base_url = settings.supabase_url.rstrip("/")
        self._bucket = settings.supabase_storage_bucket
        self._service_key = settings.supabase_service_role_key.get_secret_value()
        self._transport = transport

    def store_image(self, source_url: str, object_path: str) -> tuple[str, str]:
        content, content_type = self._download_image(source_url)
        escaped_path = quote(object_path, safe="/")
        upload_url = f"{self._base_url}/storage/v1/object/{self._bucket}/{escaped_path}"
        headers = self._headers(content_type)
        headers["x-upsert"] = "true"

        try:
            with httpx.Client(timeout=30, transport=self._transport) as client:
                response = client.post(upload_url, headers=headers, content=content)
                response.raise_for_status()
        except httpx.HTTPError as error:
            raise MediaStorageError("Non foi posible gardar unha imaxe en Supabase Storage") from error

        signed_url = self.create_signed_url(object_path)
        return object_path, signed_url

    def create_signed_url(self, object_path: str) -> str:
        escaped_path = quote(object_path, safe="/")
        url = f"{self._base_url}/storage/v1/object/sign/{self._bucket}/{escaped_path}"
        try:
            with httpx.Client(timeout=20, transport=self._transport) as client:
                response = client.post(
                    url,
                    headers=self._headers("application/json"),
                    json={"expiresIn": SIGNED_URL_TTL_SECONDS},
                )
                response.raise_for_status()
                signed_path = response.json().get("signedURL")
        except (httpx.HTTPError, ValueError) as error:
            raise MediaStorageError(
                "Non foi posible xerar unha URL temporal para a imaxe almacenada"
            ) from error
        if not isinstance(signed_path, str) or not signed_path:
            raise MediaStorageError("Supabase Storage non devolveu unha URL asinada válida")
        return urljoin(f"{self._base_url}/storage/v1/", signed_path.lstrip("/"))

    def _download_image(self, source_url: str) -> tuple[bytes, str]:
        current_url = source_url
        try:
            with httpx.Client(timeout=30, transport=self._transport) as client:
                for _ in range(4):
                    self._validate_media_url(current_url)
                    with client.stream("GET", current_url, follow_redirects=False) as response:
                        if response.status_code in {301, 302, 303, 307, 308}:
                            location = response.headers.get("location")
                            if not location:
                                raise MediaStorageError("A URL da imaxe redirixiu sen destino")
                            current_url = urljoin(current_url, location)
                            continue
                        response.raise_for_status()
                        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                        if not content_type.startswith("image/"):
                            raise MediaStorageError("A URL de Instagram non devolveu un ficheiro de imaxe")
                        length = response.headers.get("content-length")
                        if length and int(length) > MAX_IMAGE_BYTES:
                            raise MediaStorageError("A imaxe supera o límite de tamaño permitido")
                        chunks = bytearray()
                        for chunk in response.iter_bytes():
                            chunks.extend(chunk)
                            if len(chunks) > MAX_IMAGE_BYTES:
                                raise MediaStorageError("A imaxe supera o límite de tamaño permitido")
                        if not chunks:
                            raise MediaStorageError("A imaxe descargada está baleira")
                        return bytes(chunks), content_type
        except (httpx.HTTPError, ValueError) as error:
            raise MediaStorageError("Non foi posible descargar a imaxe de Instagram") from error
        raise MediaStorageError("A imaxe superou o límite de redireccións permitido")

    @staticmethod
    def _validate_media_url(url: str) -> None:
        try:
            parsed = urlsplit(url)
            host = (parsed.hostname or "").lower()
        except ValueError as error:
            raise MediaStorageError("A URL de imaxe recibida non é válida") from error
        if parsed.scheme != "https" or not any(
            host == allowed or host.endswith(f".{allowed}")
            for allowed in ALLOWED_MEDIA_HOSTS
        ):
            raise MediaStorageError("A URL da imaxe non pertence a un CDN permitido de Meta")

    def object_path(self, user_id: str, import_id: str, position: int, content_type: str) -> str:
        extension = IMAGE_EXTENSIONS.get(content_type, "img")
        return f"{user_id}/{import_id}/{position}.{extension}"

    def _headers(self, content_type: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._service_key}",
            "apikey": self._service_key,
            "Content-Type": content_type,
        }
