from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import TypeDecorator

from .database import Base


class UUIDString(TypeDecorator):
    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(UUID(as_uuid=False))
        return dialect.type_descriptor(String(36))


class UserRecord(Base):
    __tablename__ = "user_profiles"

    id = Column(UUIDString(), primary_key=True)
    name = Column(String(120), nullable=False)
    surname = Column(String(120), nullable=False, default="")
    email = Column(String(320), nullable=False, unique=True)
    phone_number = Column(String(40), nullable=True)
    state = Column(String(30), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), nullable=False)


class RoleRecord(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(40), nullable=False, unique=True)


class UserRoleRecord(Base):
    __tablename__ = "user_roles"

    user_id = Column(ForeignKey("user_profiles.id", ondelete="CASCADE"), primary_key=True)
    role_id = Column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)


class OfferTypeRecord(Base):
    __tablename__ = "offer_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(40), nullable=False, unique=True)


class HouseTypeRecord(Base):
    __tablename__ = "house_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(80), nullable=False, unique=True)


class RoomTypeRecord(Base):
    __tablename__ = "room_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(80), nullable=False, unique=True)


class ListingRecord(Base):
    __tablename__ = "listings"

    id = Column(UUIDString(), primary_key=True)
    title = Column(String(160), nullable=False)
    description = Column(Text, default="", nullable=False)
    mode = Column(String(10), nullable=False)
    status = Column(String(30), default="draft", nullable=False)
    owner_id = Column(ForeignKey("user_profiles.id"), nullable=False)
    prefecture = Column(String(80), nullable=False)
    city = Column(String(120), nullable=False)
    location = Column(Text, nullable=True)
    offer_type_id = Column(ForeignKey("offer_types.id"), nullable=False)
    house_type_id = Column(ForeignKey("house_types.id"), nullable=False)
    sale_price_jpy = Column(Integer, nullable=True)
    monthly_rent_jpy = Column(Integer, nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    construction_year = Column(Integer, nullable=True)
    garage = Column(Boolean, nullable=False, default=False)
    building_size_m2 = Column(Float, nullable=True)
    land_size_m2 = Column(Float, nullable=True)
    availability_months = Column(Integer, nullable=True)
    storage_size_m2 = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class RoomRecord(Base):
    __tablename__ = "rooms"

    id = Column(UUIDString(), primary_key=True)
    listing_id = Column(ForeignKey("listings.id", ondelete="CASCADE"), nullable=False)
    room_type_id = Column(ForeignKey("room_types.id"), nullable=False)
    size_m2 = Column(Float, nullable=True)


class ListingMediaRecord(Base):
    __tablename__ = "listing_media"

    id = Column(UUIDString(), primary_key=True)
    listing_id = Column(ForeignKey("listings.id", ondelete="CASCADE"), nullable=False)
    storage_path = Column(Text, nullable=False)
    media_type = Column(String(20), nullable=False, default="image")
    position = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False)


class ListingImportRecord(Base):
    __tablename__ = "listing_imports"
    __table_args__ = (
        UniqueConstraint(
            "source", "source_account_id", "source_post_id", name="uq_listing_import_source_post"
        ),
    )

    id = Column(UUIDString(), primary_key=True)
    user_id = Column(ForeignKey("user_profiles.id", ondelete="SET NULL"), nullable=True)
    listing_id = Column(ForeignKey("listings.id", ondelete="SET NULL"), nullable=True)
    source = Column(String(40), nullable=False, default="instagram")
    source_account_id = Column(String(120), nullable=False)
    source_post_id = Column(String(120), nullable=False)
    status = Column(String(30), nullable=False, default="pending_review")
    raw_payload = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)


class ListingImportMediaRecord(Base):
    __tablename__ = "listing_import_media"
    __table_args__ = (
        UniqueConstraint("import_id", "position", name="uq_listing_import_media_position"),
    )

    id = Column(UUIDString(), primary_key=True)
    import_id = Column(ForeignKey("listing_imports.id", ondelete="CASCADE"), nullable=False)
    storage_path = Column(Text, nullable=False, unique=True)
    media_type = Column(String(20), nullable=False, default="image")
    source_url = Column(Text, nullable=True)
    position = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False)
