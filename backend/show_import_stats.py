#!/usr/bin/env python3
"""
Simple script to show pending imports count.
"""

from app.config import get_settings
from app.database import build_session_factory
from app.models import ListingImportRecord
from sqlalchemy import select, func


def show_stats():
    settings = get_settings()
    engine, session_factory = build_session_factory(settings.effective_database_url)
    
    with session_factory() as session:
        # Count by user
        total = session.scalar(select(func.count(ListingImportRecord.id)))
        pending = session.scalar(
            select(func.count(ListingImportRecord.id))
            .where(ListingImportRecord.status == "pending_review")
        )
        approved = session.scalar(
            select(func.count(ListingImportRecord.id))
            .where(ListingImportRecord.status == "approved")
        )
        rejected = session.scalar(
            select(func.count(ListingImportRecord.id))
            .where(ListingImportRecord.status == "rejected")
        )
        
        print("=" * 60)
        print("IMPORT STATUS SUMMARY")
        print("=" * 60)
        print(f"Total imports:     {total}")
        print(f"Pending review:    {pending}")
        print(f"Approved:          {approved}")
        print(f"Rejected:          {rejected}")
        print("=" * 60)


if __name__ == "__main__":
    show_stats()
