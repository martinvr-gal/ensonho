from datetime import UTC, datetime
from uuid import uuid4

import httpx
from sqlalchemy import select, text
from sqlalchemy.engine import URL

from .config import Settings, get_settings
from .database import Base, build_session_factory, migrate_sqlite_compatibility
from .models import (
    HouseTypeRecord,
    ListingImportMediaRecord,
    ListingImportRecord,
    ListingRecord,
    OfferTypeRecord,
    RoleRecord,
    RoomTypeRecord,
)
from .media_storage import MediaStorageError, SupabaseMediaStorage
from .schemas import ImportedDraft, ImportedImage, InstagramImportRequest, Listing, ListingCreate

HOUSE_TYPES = (
    "Detached house / 一戸建て (ikkodate)",
    "Apartment unit / 共同住宅 (kyodo jutaku)",
    "Row house / 長屋建て (nagaya)",
    "Other dwelling / その他",
    "Unclassified",
)

ROOM_TYPES = (
    "Bedroom / Dormitorio (寝室)",
    "Master bedroom / Dormitorio principal (主寝室)",
    "Children's room / Cuarto infantil (子供部屋)",
    "Guest room / Cuarto de invitados (客間)",
    "Japanese-style room / Washitsu (和室)",
    "Western-style room / Yōshitsu (洋室)",
    "Living room / Sala de estar (居間)",
    "Dining room / Comedor (ダイニング)",
    "Kitchen / Cociña (台所)",
    "Dining-kitchen / DK (ダイニングキッチン)",
    "Living-dining-kitchen / LDK (リビングダイニングキッチン)",
    "One-room / Studio (ワンルーム)",
    "Study / Den (書斎)",
    "Service room / Nando (納戸)",
    "Bathroom / Bath (浴室)",
    "Shower room (シャワールーム)",
    "Toilet (トイレ)",
    "Washroom / Vanity (洗面所)",
    "Laundry area (洗濯機置場)",
    "Genkan / Entryway (玄関)",
    "Hall / Corridor (廊下)",
    "Closet (クローゼット)",
    "Oshiire / Futon closet (押入れ)",
    "Walk-in closet (ウォークインクローゼット)",
    "Shoe storage / Getabako (下駄箱)",
    "Pantry (パントリー)",
    "Loft (ロフト)",
    "Balcony (バルコニー)",
    "Engawa / Veranda (縁側)",
    "Terrace (テラス)",
    "Garage (車庫)",
    "Storehouse / Kura (蔵)",
)


class ListingService:
    def __init__(self, database_url: str | URL) -> None:
        self._engine, self._session_factory = build_session_factory(database_url)
        Base.metadata.create_all(self._engine)
        migrate_sqlite_compatibility(self._engine)
        self._seed_reference_data()

    def _seed_reference_data(self) -> None:
        with self._session_factory() as session:
            for name in ("client", "owner", "admin"):
                if session.scalar(select(RoleRecord.id).where(RoleRecord.name == name)) is None:
                    session.add(RoleRecord(name=name))
            for name in ("sale", "rent", "both"):
                if session.scalar(select(OfferTypeRecord.id).where(OfferTypeRecord.name == name)) is None:
                    session.add(OfferTypeRecord(name=name))
            for name in HOUSE_TYPES:
                if session.scalar(select(HouseTypeRecord.id).where(HouseTypeRecord.name == name)) is None:
                    session.add(HouseTypeRecord(name=name))
            for name in ROOM_TYPES:
                if session.scalar(select(RoomTypeRecord.id).where(RoomTypeRecord.name == name)) is None:
                    session.add(RoomTypeRecord(name=name))
            session.commit()

    def list(self) -> list[Listing]:
        with self._session_factory() as session:
            records = session.scalars(select(ListingRecord).order_by(ListingRecord.created_at)).all()
            return [self._to_schema(record) for record in records]

    def create(self, payload: ListingCreate, owner_id: str) -> Listing:
        with self._session_factory() as session:
            offer_type_id = session.scalar(
                select(OfferTypeRecord.id).where(OfferTypeRecord.name == payload.mode.value)
            )
            house_type_id = payload.house_type_id or session.scalar(
                select(HouseTypeRecord.id).where(HouseTypeRecord.name == "Unclassified")
            )
            now = datetime.now(UTC)
            record = ListingRecord(
                id=str(uuid4()),
                created_at=now,
                updated_at=now,
                owner_id=owner_id,
                prefecture=payload.prefecture or "",
                city=payload.city or "",
                mode=payload.mode.value,
                offer_type_id=offer_type_id,
                house_type_id=house_type_id,
                **payload.model_dump(
                    exclude={"mode", "prefecture", "city", "house_type_id"}
                ),
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return self._to_schema(record)

    @staticmethod
    def _to_schema(record: ListingRecord) -> Listing:
        return Listing.model_validate(record, from_attributes=True)


class InstagramImportService:
    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx.BaseTransport | None = None,
        database_url: str | URL | None = None,
        media_storage: SupabaseMediaStorage | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._transport = transport
        self._media_storage = media_storage
        if self._media_storage is None and self._settings.supabase_service_role_key:
            self._media_storage = SupabaseMediaStorage(self._settings)
        self._engine = None
        self._session_factory = None
        if database_url is not None:
            self._engine, self._session_factory = build_session_factory(database_url)
            ListingImportRecord.__table__.create(self._engine, checkfirst=True)
            ListingImportMediaRecord.__table__.create(self._engine, checkfirst=True)
            if self._engine.dialect.name == "postgresql":
                with self._engine.begin() as connection:
                    connection.execute(
                        text("alter table public.listing_import_media enable row level security")
                    )

    def import_posts(
        self,
        payload: InstagramImportRequest,
        user_id: str,
    ) -> tuple[str, list[ImportedDraft]]:
        access_token = self._settings.instagram_graph_access_token
        if not access_token:
            raise InstagramImportConfigurationError(
                "INSTAGRAM_GRAPH_ACCESS_TOKEN non está configurado"
            )
        if not payload.dry_run and self._session_factory is None:
            raise InstagramImportConfigurationError(
                "A persistencia das importacións non está configurada"
            )

        api_root = f"https://graph.facebook.com/{self._settings.instagram_graph_api_version}"
        headers = {"Authorization": f"Bearer {access_token}"}
        fields = (
            "id,caption,media_type,permalink,timestamp,media_url,thumbnail_url,"
            "children{media_type,media_url,thumbnail_url}"
        )

        try:
            with httpx.Client(timeout=20, transport=self._transport) as client:
                account_id = payload.account_id
                if account_id is None:
                    result = self._get_graph_object(
                        client,
                        f"{api_root}/me/assigned_instagram_accounts",
                        headers=headers,
                        params={"fields": "id,username", "limit": 100},
                    )
                    accounts = result.get("data", [])
                    if not accounts:
                        raise InstagramGraphAPIError(
                            "O token non ten ningunha conta de Instagram compartida coa app"
                        )
                    if len(accounts) != 1:
                        raise InstagramGraphAPIError(
                            "O token ten varias contas compartidas; indica account_id explicitamente"
                        )
                    account_id = str(accounts[0]["id"])

                posts_with_accounts: list[tuple[str, str | None, dict]] = []
                if payload.usernames:
                    for username in payload.usernames:
                        discovery = self._get_graph_object(
                            client,
                            f"{api_root}/{account_id}",
                            headers=headers,
                            params={
                                "fields": (
                                    f"business_discovery.username({username})"
                                    f"{{id,username,media.limit({payload.limit}){{{fields}}}}}"
                                )
                            },
                        ).get("business_discovery")
                        if not discovery:
                            continue
                        target_account_id = str(discovery.get("id", ""))
                        for post in discovery.get("media", {}).get("data", []):
                            posts_with_accounts.append((target_account_id, username, post))
                elif payload.post_ids:
                    posts = [
                        self._get_graph_object(
                            client,
                            f"{api_root}/{post_id}",
                            headers=headers,
                            params={"fields": fields},
                        )
                        for post_id in payload.post_ids
                    ]
                    posts_with_accounts = [(account_id, None, post) for post in posts]
                else:
                    result = self._get_graph_object(
                        client,
                        f"{api_root}/{account_id}/media",
                        headers=headers,
                        params={"fields": fields, "limit": payload.limit},
                    )
                    posts = result.get("data", [])
                    posts_with_accounts = [(account_id, None, post) for post in posts]
        except httpx.TimeoutException as error:
            raise InstagramGraphAPIError("Instagram Graph API esgotou o tempo de espera") from error
        except httpx.RequestError as error:
            raise InstagramGraphAPIError("Non foi posible conectar con Instagram Graph API") from error

        drafts = []
        for target_account_id, target_username, post in posts_with_accounts:
            post_id = str(post.get("id", ""))
            if not post_id:
                continue
            caption = post.get("caption") or ""
            title = next((line.strip() for line in caption.splitlines() if line.strip()), "")
            image_assets = self._image_assets(post)
            drafts.append(
                ImportedDraft(
                    account_id=target_account_id,
                    account_username=target_username,
                    source_post_id=post_id,
                    status="preview" if payload.dry_run else "pending_review",
                    title=(title or f"Publicación de Instagram {post_id}")[:160],
                    caption=caption,
                    media_type=post.get("media_type"),
                    source_url=post.get("permalink"),
                    media_url=post.get("media_url") or post.get("thumbnail_url"),
                    images=[
                        ImportedImage(position=position, media_type=media_type, url=url)
                        for position, (url, media_type) in enumerate(image_assets)
                    ],
                )
            )

        if not payload.dry_run:
            try:
                self._persist_drafts(posts_with_accounts, drafts, user_id)
            except MediaStorageError as error:
                raise InstagramGraphAPIError(str(error)) from error
        return account_id, drafts

    @staticmethod
    def _image_assets(post: dict) -> list[tuple[str, str]]:
        media_type = str(post.get("media_type") or "").upper()
        if media_type == "CAROUSEL_ALBUM":
            items = post.get("children", {}).get("data", [])
        else:
            items = [post]

        assets = []
        for item in items:
            item_type = str(item.get("media_type") or media_type).upper()
            if item_type in {"VIDEO", "REELS"}:
                url = item.get("thumbnail_url")
                asset_type = "thumbnail"
            else:
                url = item.get("media_url") or item.get("thumbnail_url")
                asset_type = "image"
            if isinstance(url, str) and url.startswith("https://"):
                assets.append((url, asset_type))
        return assets

    def list_pending_imports(
        self,
        user_id: str,
        account_id: str | None = None,
    ) -> list[ImportedDraft]:
        if self._session_factory is None:
            raise InstagramImportConfigurationError(
                "A persistencia das importacións non está configurada"
            )

        query = select(ListingImportRecord).where(
            ListingImportRecord.user_id == user_id,
            ListingImportRecord.status == "pending_review",
        )
        if account_id:
            query = query.where(ListingImportRecord.source_account_id == account_id)

        with self._session_factory() as session:
            records = session.scalars(
                query.order_by(ListingImportRecord.created_at.desc())
            ).all()
            drafts = []
            for record in records:
                draft = self._record_to_draft(record)
                media_records = session.scalars(
                    select(ListingImportMediaRecord)
                    .where(ListingImportMediaRecord.import_id == record.id)
                    .order_by(ListingImportMediaRecord.position)
                ).all()
                if media_records and self._media_storage is None:
                    raise InstagramImportConfigurationError(
                        "SUPABASE_SERVICE_ROLE_KEY é necesario para xerar URLs das imaxes privadas"
                    )
                if self._media_storage:
                    draft.images = [
                        ImportedImage(
                            position=media.position,
                            media_type=media.media_type,
                            url=self._media_storage.create_signed_url(media.storage_path),
                        )
                        for media in media_records
                    ]
                drafts.append(draft)
            return drafts

    def _persist_drafts(
        self,
        posts_with_accounts: list[tuple[str, str | None, dict]],
        drafts: list[ImportedDraft],
        user_id: str,
    ) -> None:
        if self._session_factory is None:
            raise InstagramImportConfigurationError(
                "A persistencia das importacións non está configurada"
            )

        posts_by_key = {
            (account_id, str(post.get("id"))): post
            for account_id, _, post in posts_with_accounts
            if post.get("id")
        }
        with self._session_factory() as session:
            for draft in drafts:
                post = posts_by_key[(draft.account_id, draft.source_post_id)]
                record = session.scalar(
                    select(ListingImportRecord).where(
                        ListingImportRecord.source == "instagram",
                        ListingImportRecord.source_account_id == draft.account_id,
                        ListingImportRecord.source_post_id == draft.source_post_id,
                    )
                )
                if record is None:
                    record = ListingImportRecord(
                        id=str(uuid4()),
                        user_id=user_id,
                        source="instagram",
                        source_account_id=draft.account_id,
                        source_post_id=draft.source_post_id,
                        status="pending_review",
                        raw_payload={**post, "_source_username": draft.account_username},
                        created_at=datetime.now(UTC),
                    )
                    session.add(record)
                else:
                    record.raw_payload = {**post, "_source_username": draft.account_username}

                session.flush()
                image_assets = self._image_assets(post)
                if image_assets and self._media_storage is None:
                    raise InstagramImportConfigurationError(
                        "Configura SUPABASE_SERVICE_ROLE_KEY e o bucket privado de Storage para gardar imaxes"
                    )
                existing_media = {
                    media.position: media
                    for media in session.scalars(
                        select(ListingImportMediaRecord).where(
                            ListingImportMediaRecord.import_id == record.id
                        )
                    ).all()
                }
                draft.images = []
                for position, (source_url, media_type) in enumerate(image_assets):
                    media_record = existing_media.get(position)
                    if media_record is not None and media_record.source_url == source_url:
                        stored_path = media_record.storage_path
                        signed_url = self._media_storage.create_signed_url(stored_path)
                    else:
                        storage_path = f"{user_id}/{record.id}/{position:03d}"
                        stored_path, signed_url = self._media_storage.store_image(
                            source_url,
                            storage_path,
                        )
                    if media_record is None:
                        media_record = ListingImportMediaRecord(
                            id=str(uuid4()),
                            import_id=record.id,
                            storage_path=stored_path,
                            media_type=media_type,
                            source_url=source_url,
                            position=position,
                            created_at=datetime.now(UTC),
                        )
                        session.add(media_record)
                    else:
                        media_record.storage_path = stored_path
                        media_record.media_type = media_type
                        media_record.source_url = source_url
                    draft.images.append(
                        ImportedImage(
                            position=position,
                            media_type=media_type,
                            url=signed_url,
                        )
                    )

                draft.import_id = record.id
                draft.status = record.status

            session.commit()

    @staticmethod
    def _record_to_draft(record: ListingImportRecord) -> ImportedDraft:
        post = record.raw_payload or {}
        caption = post.get("caption") or ""
        title = next((line.strip() for line in caption.splitlines() if line.strip()), "")
        return ImportedDraft(
            import_id=record.id,
            account_id=record.source_account_id,
            account_username=post.get("_source_username"),
            source_post_id=record.source_post_id,
            status=record.status,
            title=(title or f"Publicación de Instagram {record.source_post_id}")[:160],
            caption=caption,
            media_type=post.get("media_type"),
            source_url=post.get("permalink"),
            media_url=post.get("media_url") or post.get("thumbnail_url"),
        )

    @staticmethod
    def _get_graph_object(
        client: httpx.Client,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, str | int],
    ) -> dict:
        response = client.get(url, headers=headers, params=params)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            try:
                message = response.json().get("error", {}).get("message")
            except ValueError:
                message = None
            raise InstagramGraphAPIError(
                message or f"Instagram Graph API respondeu HTTP {response.status_code}"
            ) from error

        result = response.json()
        if "error" in result:
            raise InstagramGraphAPIError(
                result["error"].get("message", "Erro de Instagram Graph API")
            )
        return result


class InstagramImportConfigurationError(RuntimeError):
    pass


class InstagramGraphAPIError(RuntimeError):
    pass
