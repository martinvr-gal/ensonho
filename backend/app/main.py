from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .auth import get_current_user, require_roles
from .config import get_settings
from .schemas import (
    CurrentUser,
    ImportedDraft,
    InstagramImportRequest,
    InstagramImportResponse,
    Listing,
    ListingCreate,
)
from .media_storage import MediaStorageError
from .service import (
    InstagramGraphAPIError,
    InstagramImportConfigurationError,
    InstagramImportService,
    ListingService,
)

settings = get_settings()
app = FastAPI(
    title="Ensonho API",
    description="API inicial do portal inmobiliario de vivendas xaponesas.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

listing_service = ListingService(settings.effective_database_url)
instagram_service = InstagramImportService(database_url=settings.effective_database_url)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.app_env}


@app.get("/api/v1/auth/me", response_model=CurrentUser)
def current_user(claims: dict = Depends(get_current_user)) -> CurrentUser:
    return CurrentUser(
        id=claims["sub"],
        email=claims.get("email"),
        role=claims.get("role") or claims.get("user_metadata", {}).get("role"),
    )


@app.get("/api/v1/listings", response_model=list[Listing])
def list_listings() -> list[Listing]:
    return listing_service.list()


@app.post("/api/v1/listings", response_model=Listing, status_code=201)
def create_listing(
    payload: ListingCreate,
    claims: dict = Depends(require_roles("authenticated", "owner", "admin")),
) -> Listing:
    return listing_service.create(payload, owner_id=claims["sub"])


@app.post("/api/v1/imports/instagram", response_model=InstagramImportResponse)
def import_instagram_posts(
    payload: InstagramImportRequest,
    claims: dict = Depends(require_roles("authenticated", "owner", "admin")),
) -> InstagramImportResponse:
    try:
        account_id, drafts = instagram_service.import_posts(payload, user_id=claims["sub"])
    except InstagramImportConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except InstagramGraphAPIError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return InstagramImportResponse(
        account_id=account_id,
        dry_run=payload.dry_run,
        drafts=drafts,
        message=(
            "Previsualización creada; non se gardou ningún borrador."
            if payload.dry_run
            else "Publicacións gardadas como borradores para revisión manual."
        ),
    )


@app.get("/api/v1/imports/instagram", response_model=list[ImportedDraft])
def list_instagram_imports(
    account_id: str | None = None,
    claims: dict = Depends(require_roles("authenticated", "owner", "admin")),
) -> list[ImportedDraft]:
    try:
        return instagram_service.list_pending_imports(
            user_id=claims["sub"],
            account_id=account_id,
        )
    except InstagramImportConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except InstagramGraphAPIError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except MediaStorageError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
