#!/usr/bin/env python3
"""
Manage imported Instagram posts - review, approve, or reject.
"""

import argparse
import json
from datetime import UTC, datetime
from uuid import uuid4

from app.config import get_settings
from app.database import build_session_factory
from app.models import ListingImportRecord, ListingImportMediaRecord
from app.schemas import ListingCreate, ListingMode
from app.service import InstagramImportService, ListingService
from sqlalchemy import select


def list_pending_posts(service: InstagramImportService, user_id: str, limit: int = 10):
    """List pending import posts."""
    drafts = service.list_pending_imports(user_id=user_id)
    
    print(f"\nPending posts: {len(drafts)}\n")
    for i, draft in enumerate(drafts[:limit], 1):
        username = draft.account_username or "unknown"
        title = draft.title[:50].encode('ascii', errors='replace').decode('ascii')
        print(f"{i}. {username} - {title}")
        print(f"   ID: {draft.import_id}")
        print(f"   Images: {len(draft.images)}")
        print()


def approve_post_to_listing(
    import_id: str,
    title: str,
    description: str = "",
    prefecture: str = "",
    city: str = "",
    owner_id: str = "admin",
):
    """Convert approved import to a listing."""
    settings = get_settings()
    engine, session_factory = build_session_factory(settings.effective_database_url)
    
    with session_factory() as session:
        # Get import record
        import_record = session.scalar(
            select(ListingImportRecord).where(ListingImportRecord.id == import_id)
        )
        if not import_record:
            print(f"Import not found: {import_id}")
            return False
        
        # Get media records
        media_records = session.scalars(
            select(ListingImportMediaRecord)
            .where(ListingImportMediaRecord.import_id == import_id)
            .order_by(ListingImportMediaRecord.position)
        ).all()
        
        # Create listing using ListingService
        listing_service = ListingService(settings.effective_database_url)
        
        payload = ListingCreate(
            title=title,
            description=description,
            mode=ListingMode.SALE,  # Default to sale
            prefecture=prefecture,
            city=city,
        )
        
        try:
            listing = listing_service.create(payload, owner_id=owner_id)
            
            # Update import status
            import_record.status = "approved"
            import_record.listing_id = listing.id
            session.commit()
            
            print(f"\n[OK] Listing created: {listing.id}")
            print(f"    Title: {listing.title}")
            print(f"    Media attached: {len(media_records)}")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to create listing: {e}")
            return False


def reject_post(import_id: str, reason: str = ""):
    """Reject an imported post."""
    settings = get_settings()
    engine, session_factory = build_session_factory(settings.effective_database_url)
    
    with session_factory() as session:
        import_record = session.scalar(
            select(ListingImportRecord).where(ListingImportRecord.id == import_id)
        )
        if not import_record:
            print(f"Import not found: {import_id}")
            return False
        
        import_record.status = "rejected"
        session.commit()
        
        print(f"[OK] Post rejected: {import_id}")
        if reason:
            print(f"     Reason: {reason}")
        return True


def export_post_data(import_id: str):
    """Export post data as JSON for manual editing."""
    settings = get_settings()
    engine, session_factory = build_session_factory(settings.effective_database_url)
    
    with session_factory() as session:
        import_record = session.scalar(
            select(ListingImportRecord).where(ListingImportRecord.id == import_id)
        )
        if not import_record:
            print(f"Import not found: {import_id}")
            return None
        
        media_records = session.scalars(
            select(ListingImportMediaRecord)
            .where(ListingImportMediaRecord.import_id == import_id)
            .order_by(ListingImportMediaRecord.position)
        ).all()
        
        data = {
            "import_id": str(import_id),
            "source": import_record.source,
            "source_account_id": import_record.source_account_id,
            "source_post_id": import_record.source_post_id,
            "source_url": import_record.raw_payload.get("permalink") if import_record.raw_payload else None,
            "caption": import_record.raw_payload.get("caption") if import_record.raw_payload else None,
            "media": [
                {
                    "position": m.position,
                    "storage_path": m.storage_path,
                    "media_type": m.media_type,
                    "source_url": m.source_url,
                }
                for m in media_records
            ],
            "listing_data": {
                "title": "",
                "description": "",
                "mode": "sale",
                "prefecture": "",
                "city": "",
                "location": "",
                "sale_price_jpy": None,
                "construction_year": None,
                "building_size_m2": None,
                "land_size_m2": None,
            }
        }
        
        return data


def main():
    parser = argparse.ArgumentParser(description="Manage imported Instagram posts")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List pending posts")
    list_parser.add_argument("--user-id", required=True, help="User ID")
    list_parser.add_argument("--limit", type=int, default=10, help="Max posts to show")
    
    # Approve command
    approve_parser = subparsers.add_parser("approve", help="Approve post as listing")
    approve_parser.add_argument("import_id", help="Import ID to approve")
    approve_parser.add_argument("--title", required=True, help="Listing title")
    approve_parser.add_argument("--description", default="", help="Listing description")
    approve_parser.add_argument("--prefecture", default="", help="Prefecture")
    approve_parser.add_argument("--city", default="", help="City")
    approve_parser.add_argument("--owner-id", default="admin", help="Owner user ID")
    
    # Reject command
    reject_parser = subparsers.add_parser("reject", help="Reject post")
    reject_parser.add_argument("import_id", help="Import ID to reject")
    reject_parser.add_argument("--reason", default="", help="Rejection reason")
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export post data as JSON")
    export_parser.add_argument("import_id", help="Import ID to export")
    export_parser.add_argument("--output", help="Output JSON file")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    settings = get_settings()
    service = InstagramImportService(database_url=settings.effective_database_url)
    
    if args.command == "list":
        list_pending_posts(service, user_id=args.user_id, limit=args.limit)
    
    elif args.command == "approve":
        approve_post_to_listing(
            import_id=args.import_id,
            title=args.title,
            description=args.description,
            prefecture=args.prefecture,
            city=args.city,
            owner_id=args.owner_id,
        )
    
    elif args.command == "reject":
        reject_post(import_id=args.import_id, reason=args.reason)
    
    elif args.command == "export":
        data = export_post_data(import_id=args.import_id)
        if data:
            if args.output:
                with open(args.output, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                print(f"[OK] Data exported to {args.output}")
            else:
                print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
