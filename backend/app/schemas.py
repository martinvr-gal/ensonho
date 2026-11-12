import re
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


class ListingMode(StrEnum):
    SALE = "sale"
    RENT = "rent"
    BOTH = "both"


class ListingCreate(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(default="", max_length=5000)
    mode: ListingMode
    prefecture: str | None = Field(default=None, max_length=80)
    city: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=500)
    house_type_id: int | None = Field(default=None, gt=0)
    sale_price_jpy: int | None = Field(default=None, gt=0)
    monthly_rent_jpy: int | None = Field(default=None, gt=0)
    construction_year: int | None = Field(default=None, ge=1800, le=2100)
    garage: bool = False
    building_size_m2: float | None = Field(default=None, gt=0)
    land_size_m2: float | None = Field(default=None, gt=0)
    availability_months: int | None = Field(default=None, ge=0)
    storage_size_m2: float | None = Field(default=None, gt=0)


class Listing(ListingCreate):
    id: str
    owner_id: str
    status: str = "draft"
    offer_type_id: int
    published_at: datetime | None = None
    created_at: datetime


class InstagramImportRequest(BaseModel):
    account_id: str | None = Field(
        default=None,
        min_length=1,
        description="Instagram professional account ID; inferred when one account is shared",
    )
    usernames: list[str] = Field(default_factory=list, max_length=5)
    post_ids: list[str] = Field(default_factory=list, max_length=50)
    limit: int = Field(default=10, ge=1, le=50)
    dry_run: bool = True

    @field_validator("usernames")
    @classmethod
    def normalize_usernames(cls, usernames: list[str]) -> list[str]:
        normalized = [username.strip().removeprefix("@").lower() for username in usernames]
        if any(not re.fullmatch(r"[a-z0-9._]{1,30}", username) for username in normalized):
            raise ValueError("Os usernames de Instagram non teñen un formato válido")
        if len(set(normalized)) != len(normalized):
            raise ValueError("Non repitas usernames na mesma importación")
        return normalized

    @model_validator(mode="after")
    def validate_source_mode(self):
        if self.usernames and self.post_ids:
            raise ValueError("Indica usernames ou post_ids, pero non ambos á vez")
        return self


class ImportedImage(BaseModel):
    position: int
    media_type: str
    url: HttpUrl


class ImportedDraft(BaseModel):
    import_id: str | None = None
    account_id: str
    account_username: str | None = None
    source_post_id: str
    status: str
    title: str
    caption: str = ""
    media_type: str | None = None
    source_url: HttpUrl | None = None
    media_url: HttpUrl | None = None
    images: list[ImportedImage] = Field(default_factory=list)


class InstagramImportResponse(BaseModel):
    account_id: str
    dry_run: bool
    drafts: list[ImportedDraft]
    message: str


class CurrentUser(BaseModel):
    id: str
    email: str | None = None
    role: str | None = None
