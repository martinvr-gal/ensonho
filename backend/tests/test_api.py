import os

from fastapi.testclient import TestClient
import jwt
import httpx
import pytest
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy import select

# Keep API tests isolated from the live Supabase database configured in .env.
os.environ["DATABASE_URL"] = "sqlite:///./data/test.db"
os.environ["SUPABASE_DB_PASSWORD"] = ""

from app.config import Settings, get_settings
from app.main import app
from app import main
from app.models import (
    HouseTypeRecord,
    ListingImportMediaRecord,
    ListingImportRecord,
    ListingRecord,
    OfferTypeRecord,
    RoomTypeRecord,
)
from app.schemas import ListingCreate, ListingMode
from app.media_storage import MediaStorageError, SupabaseMediaStorage
from app.service import ListingService


client = TestClient(app)
TEST_SECRET = "local-test-secret"
TEST_USER_ID = "00000000-0000-4000-8000-000000000123"
get_settings().supabase_jwt_secret = TEST_SECRET


def access_token(role: str = "authenticated", user_id: str = TEST_USER_ID) -> str:
    return jwt.encode(
        {"sub": user_id, "email": "owner@example.com", "role": role},
        TEST_SECRET,
        algorithm="HS256",
    )


class FakeMediaStorage:
    def __init__(self) -> None:
        self.uploaded: list[tuple[str, str]] = []

    def store_image(self, source_url: str, object_path: str) -> tuple[str, str]:
        self.uploaded.append((source_url, object_path))
        return object_path, f"https://storage.example/{object_path}"

    def create_signed_url(self, object_path: str) -> str:
        return f"https://storage.example/{object_path}"


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_supabase_connection_url_escapes_password_without_exposing_it() -> None:
    settings = Settings(
        supabase_project_ref="tdxfwumdmanmfxzoytpm",
        supabase_db_password="p@ss:/?word",
    )

    database_url = settings.effective_database_url

    assert str(database_url).startswith(
        "postgresql+psycopg://postgres.tdxfwumdmanmfxzoytpm:***@"
    )
    assert database_url.password == "p@ss:/?word"
    assert database_url.query["sslmode"] == "require"


def test_uuid_columns_use_postgres_uuid_and_sqlite_text() -> None:
    column_type = ListingRecord.__table__.c.id.type
    import_id_type = ListingImportRecord.__table__.c.id.type
    import_media_id_type = ListingImportMediaRecord.__table__.c.id.type

    assert column_type.compile(dialect=postgresql.dialect()) == "UUID"
    assert column_type.compile(dialect=sqlite.dialect()) == "VARCHAR(36)"
    assert import_id_type.compile(dialect=postgresql.dialect()) == "UUID"
    assert import_id_type.compile(dialect=sqlite.dialect()) == "VARCHAR(36)"
    assert import_media_id_type.compile(dialect=postgresql.dialect()) == "UUID"
    assert import_media_id_type.compile(dialect=sqlite.dialect()) == "VARCHAR(36)"
    assert import_media_id_type.compile(dialect=postgresql.dialect()) == "UUID"
    assert import_media_id_type.compile(dialect=sqlite.dialect()) == "VARCHAR(36)"


def test_create_listing_and_list_it() -> None:
    payload = {
        "title": "Casa tradicional en Nara",
        "description": "Machiya restaurada preto do centro.",
        "mode": "both",
        "prefecture": "Nara",
        "city": "Nara",
        "sale_price_jpy": 38000000,
        "monthly_rent_jpy": 180000,
    }

    created = client.post(
        "/api/v1/listings",
        json=payload,
        headers={"Authorization": f"Bearer {access_token()}"},
    )
    listings = client.get("/api/v1/listings")

    assert created.status_code == 201
    assert created.json()["mode"] == "both"
    assert any(item["id"] == created.json()["id"] for item in listings.json())


def test_instagram_import_defaults_to_preview(monkeypatch) -> None:
    settings = Settings(instagram_graph_access_token="test-token")

    def graph_response(request: httpx.Request) -> httpx.Response:
        post_id = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(
            200,
            json={
                "id": post_id,
                "caption": f"Post {post_id}\nDetails",
                "media_type": "IMAGE",
                "permalink": f"https://www.instagram.com/p/{post_id}/",
            },
        )

    monkeypatch.setattr(
        main,
        "instagram_service",
        main.InstagramImportService(settings, httpx.MockTransport(graph_response)),
    )
    response = client.post(
        "/api/v1/imports/instagram",
        json={"account_id": "178900001", "post_ids": ["post-1", "post-2"]},
        headers={"Authorization": f"Bearer {access_token()}"},
    )

    assert response.status_code == 200
    assert response.json()["dry_run"] is True
    assert [draft["status"] for draft in response.json()["drafts"]] == ["preview", "preview"]
    assert response.json()["drafts"][0]["caption"] == "Post post-1\nDetails"
    assert response.json()["drafts"][0]["source_url"] == "https://www.instagram.com/p/post-1/"


def test_instagram_import_fetches_recent_account_media(monkeypatch) -> None:
    settings = Settings(instagram_graph_access_token="test-token")

    def graph_response(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/178900001/media")
        assert request.url.params["limit"] == "3"
        return httpx.Response(
            200,
            json={"data": [{"id": "post-3", "caption": "Casa en Nara", "media_type": "CAROUSEL_ALBUM"}]},
        )

    monkeypatch.setattr(
        main,
        "instagram_service",
        main.InstagramImportService(settings, httpx.MockTransport(graph_response)),
    )
    response = client.post(
        "/api/v1/imports/instagram",
        json={"account_id": "178900001", "limit": 3},
        headers={"Authorization": f"Bearer {access_token()}"},
    )

    assert response.status_code == 200
    assert response.json()["drafts"][0]["source_post_id"] == "post-3"
    assert response.json()["drafts"][0]["title"] == "Casa en Nara"


def test_instagram_import_persists_pending_drafts_without_duplicates(
    monkeypatch, tmp_path
) -> None:
    settings = Settings(instagram_graph_access_token="test-token")
    media_storage = FakeMediaStorage()

    def graph_response(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/me/assigned_instagram_accounts"):
            return httpx.Response(200, json={"data": [{"id": "178900001", "username": "test_account"}]})
        assert request.url.path.endswith("/178900001/media")
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "post-review-1",
                        "caption": "Casa en Nara\nDetalles da vivenda",
                        "media_type": "CAROUSEL_ALBUM",
                        "permalink": "https://www.instagram.com/p/post-review-1/",
                        "media_url": "https://cdn.example.com/photo.jpg",
                        "children": {
                            "data": [
                                {
                                    "id": "child-image-1",
                                    "media_type": "IMAGE",
                                    "media_url": "https://cdninstagram.com/photo-1.jpg",
                                },
                                {
                                    "id": "child-video-1",
                                    "media_type": "VIDEO",
                                    "thumbnail_url": "https://cdninstagram.com/thumb-1.jpg",
                                },
                            ]
                        },
                    }
                ]
            },
        )

    service = main.InstagramImportService(
        settings,
        httpx.MockTransport(graph_response),
        database_url=f"sqlite:///{tmp_path / 'instagram-imports.db'}",
        media_storage=media_storage,
    )
    monkeypatch.setattr(main, "instagram_service", service)
    headers = {"Authorization": f"Bearer {access_token()}"}
    payload = {"dry_run": False}

    first_response = client.post("/api/v1/imports/instagram", json=payload, headers=headers)
    second_response = client.post("/api/v1/imports/instagram", json=payload, headers=headers)
    pending_response = client.get("/api/v1/imports/instagram", headers=headers)

    assert first_response.status_code == 200
    assert first_response.json()["account_id"] == "178900001"
    first_draft = first_response.json()["drafts"][0]
    assert first_draft["status"] == "pending_review"
    assert first_draft["import_id"]
    assert first_draft["media_url"] == "https://cdn.example.com/photo.jpg"
    assert [image["media_type"] for image in first_draft["images"]] == ["image", "thumbnail"]
    assert len(media_storage.uploaded) == 2
    assert second_response.json()["drafts"][0]["import_id"] == first_draft["import_id"]
    assert len(pending_response.json()) == 1
    assert pending_response.json()[0]["caption"] == "Casa en Nara\nDetalles da vivenda"
    assert len(pending_response.json()[0]["images"]) == 2
    with service._session_factory() as session:
        stored_media = session.scalars(select(ListingImportMediaRecord)).all()
        assert len(stored_media) == 2


def test_supabase_storage_uploads_private_image_and_returns_signed_url() -> None:
    settings = Settings(
        supabase_url="https://project.supabase.co",
        supabase_service_role_key="test-server-key",
        supabase_storage_bucket="instagram-import-media",
    )
    requests = []

    def storage_response(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, headers={"content-type": "image/jpeg"}, content=b"image-bytes")
        if "/sign/" in request.url.path:
            return httpx.Response(200, json={"signedURL": "/object/sign/instagram-import-media/test.jpg?token=signed"})
        return httpx.Response(200, json={"Key": "test.jpg"})

    storage = SupabaseMediaStorage(settings, httpx.MockTransport(storage_response))
    object_path, signed_url = storage.store_image(
        "https://scontent.cdninstagram.com/photo.jpg",
        "user/import/000.jpg",
    )

    assert object_path == "user/import/000.jpg"
    assert signed_url == "https://project.supabase.co/storage/v1/object/sign/instagram-import-media/test.jpg?token=signed"
    assert requests[1].headers["x-upsert"] == "true"
    assert requests[1].content == b"image-bytes"


def test_supabase_storage_rejects_non_meta_media_host() -> None:
    with pytest.raises(MediaStorageError, match="CDN permitido"):
        SupabaseMediaStorage._validate_media_url("https://example.com/image.jpg")


def test_instagram_business_discovery_imports_posts_for_five_usernames(monkeypatch) -> None:
    settings = Settings(instagram_graph_access_token="test-token")
    usernames = [
        "micasajapon",
        "oldhousesjapan",
        "omoroiosaka",
        "japanhousedeal",
        "akiyajourney.japan",
    ]

    def graph_response(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/me/assigned_instagram_accounts"):
            return httpx.Response(
                200,
                json={"data": [{"id": "178900001", "username": "authorized_source"}]},
            )

        fields = request.url.params["fields"]
        username = next(name for name in usernames if f"username({name})" in fields)
        assert "media.limit(10)" in fields
        return httpx.Response(
            200,
            json={
                "business_discovery": {
                    "id": f"target-{username}",
                    "username": username,
                    "media": {
                        "data": [
                            {
                                "id": f"{username}-post-{index}",
                                "caption": f"Example {index} from {username}",
                                "media_type": "IMAGE",
                            }
                            for index in range(10)
                        ]
                    },
                }
            },
        )

    monkeypatch.setattr(
        main,
        "instagram_service",
        main.InstagramImportService(settings, httpx.MockTransport(graph_response)),
    )
    response = client.post(
        "/api/v1/imports/instagram",
        json={"usernames": usernames, "limit": 10},
        headers={"Authorization": f"Bearer {access_token()}"},
    )

    assert response.status_code == 200
    assert response.json()["account_id"] == "178900001"
    drafts = response.json()["drafts"]
    assert len(drafts) == 50
    assert {draft["account_id"] for draft in drafts} == {
        f"target-{username}" for username in usernames
    }
    assert {draft["account_username"] for draft in drafts} == set(usernames)
    assert all(draft["status"] == "preview" for draft in drafts)


def test_listing_survives_a_new_service_instance(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'listings.db'}"
    payload = ListingCreate(
        title="Casa de madeira en Kyoto",
        mode=ListingMode.RENT,
        prefecture="Kyoto",
        city="Kyoto",
        monthly_rent_jpy=220000,
    )

    first_service = ListingService(database_url)
    created = first_service.create(payload, owner_id=TEST_USER_ID)
    second_service = ListingService(database_url)

    assert [listing.id for listing in second_service.list()] == [created.id]


def test_listing_persists_catalog_relations_and_property_details(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'property-details.db'}"
    service = ListingService(database_url)
    payload = ListingCreate(
        title="Machiya para alugar",
        mode=ListingMode.RENT,
        location="Aldea próxima a Kyoto",
        monthly_rent_jpy=150000,
        construction_year=1980,
        garage=True,
        building_size_m2=92.5,
        land_size_m2=130,
        availability_months=3,
        storage_size_m2=4.5,
    )

    created = service.create(payload, owner_id=TEST_USER_ID)

    with service._session_factory() as session:
        house_types = set(session.scalars(select(HouseTypeRecord.name)).all())
        room_types = set(session.scalars(select(RoomTypeRecord.name)).all())
        stored = session.scalar(select(ListingRecord).where(ListingRecord.id == created.id))
        assert stored is not None
        assert "Detached house / 一戸建て (ikkodate)" in house_types
        assert "Apartment unit / 共同住宅 (kyodo jutaku)" in house_types
        assert "Row house / 長屋建て (nagaya)" in house_types
        assert "Japanese-style room / Washitsu (和室)" in room_types
        assert "Living-dining-kitchen / LDK (リビングダイニングキッチン)" in room_types
        assert "Genkan / Entryway (玄関)" in room_types
        assert len(room_types) == 32
        assert session.get(OfferTypeRecord, stored.offer_type_id).name == "rent"
        assert session.get(HouseTypeRecord, stored.house_type_id).name == "Unclassified"
        assert stored.location == "Aldea próxima a Kyoto"
        assert stored.availability_months == 3
        assert stored.building_size_m2 == 92.5


def test_current_user_requires_a_bearer_token() -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401


def test_current_user_accepts_a_valid_supabase_style_token(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "supabase_jwt_secret", TEST_SECRET)
    token = access_token()

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {
        "id": TEST_USER_ID,
        "email": "owner@example.com",
        "role": "authenticated",
    }


def test_listing_creation_rejects_a_non_application_role(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "supabase_jwt_secret", TEST_SECRET)
    response = client.post(
        "/api/v1/listings",
        json={
            "title": "Casa sen permisos",
            "mode": "rent",
            "prefecture": "Osaka",
            "city": "Osaka",
        },
        headers={"Authorization": f"Bearer {access_token(role='anonymous')}"},
    )

    assert response.status_code == 403


def test_listing_creation_assigns_authenticated_user_as_owner(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "supabase_jwt_secret", TEST_SECRET)
    response = client.post(
        "/api/v1/listings",
        json={
            "title": "Casa do propietario",
            "mode": "sale",
            "prefecture": "Hyogo",
            "city": "Kobe",
        },
        headers={"Authorization": f"Bearer {access_token(user_id='00000000-0000-4000-8000-000000000456')}"},
    )

    assert response.status_code == 201
    assert response.json()["owner_id"] == "00000000-0000-4000-8000-000000000456"
