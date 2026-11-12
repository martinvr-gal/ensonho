#!/usr/bin/env python3
"""
Verify imported Instagram posts and media in Supabase.
Shows statistics about imported posts and images.
"""

from sqlalchemy import select, func
from app.database import build_session_factory
from app.models import ListingImportRecord, ListingImportMediaRecord
from app.config import get_settings


def verify_imports():
    """Verify and display import statistics."""
    settings = get_settings()
    engine, session_factory = build_session_factory(settings.effective_database_url)
    
    with session_factory() as session:
        # Count totals
        total_imports = session.scalar(
            select(func.count(ListingImportRecord.id))
        )
        total_media = session.scalar(
            select(func.count(ListingImportMediaRecord.id))
        )
        
        # Get accounts
        accounts = session.scalars(
            select(ListingImportRecord.source_account_id).distinct()
        ).all()
        
        # Get usernames
        usernames = session.scalars(
            select(ListingImportRecord.raw_payload['_source_username'])
            .where(ListingImportRecord.raw_payload['_source_username'].isnot(None))
            .distinct()
        ).all()
        
        print("=" * 70)
        print("INSTAGRAM IMPORT VERIFICATION")
        print("=" * 70)
        print(f"\nTotal import records (posts):  {total_imports}")
        print(f"Total media records (images):  {total_media}")
        print(f"Unique accounts:                {len(accounts)}")
        
        print("\n" + "=" * 70)
        print("IMPORT BREAKDOWN BY ACCOUNT")
        print("=" * 70)
        
        for account_id in sorted(accounts):
            posts = session.scalar(
                select(func.count(ListingImportRecord.id))
                .where(ListingImportRecord.source_account_id == account_id)
            )
            media = session.scalar(
                select(func.count(ListingImportMediaRecord.id))
                .where(
                    ListingImportMediaRecord.import_id.in_(
                        select(ListingImportRecord.id)
                        .where(ListingImportRecord.source_account_id == account_id)
                    )
                )
            )
            print(f"\nAccount ID: {account_id}")
            print(f"  Posts:  {posts}")
            print(f"  Images: {media}")
        
        print("\n" + "=" * 70)
        print("SAMPLE IMPORTED POSTS")
        print("=" * 70)
        
        sample_posts = session.scalars(
            select(ListingImportRecord)
            .order_by(ListingImportRecord.created_at.desc())
            .limit(5)
        ).all()
        
        for i, post in enumerate(sample_posts, 1):
            media_count = session.scalar(
                select(func.count(ListingImportMediaRecord.id))
                .where(ListingImportMediaRecord.import_id == post.id)
            )
            username = (post.raw_payload or {}).get("_source_username", "unknown")
            
            print(f"\n{i}. {username}")
            print(f"   Post ID:    {post.source_post_id}")
            print(f"   Images:     {media_count}")
            print(f"   Status:     {post.status}")
            print(f"   Created:    {post.created_at}")
        
        print("\n" + "=" * 70)


if __name__ == "__main__":
    verify_imports()
