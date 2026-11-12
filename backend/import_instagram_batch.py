#!/usr/bin/env python3
"""
Batch import script for Instagram house listings.
Imports 10 posts from each of 5 Instagram accounts (50 total).
Saves all images to Supabase Storage.

Usage:
    python import_instagram_batch.py [--account-list] [--dry-run]
    
Environment:
    INSTAGRAM_GRAPH_ACCESS_TOKEN: Required for API access
    DATABASE_URL: Defaults to sqlite:///./data/ensonho.db
    SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY: Required to store images

Examples:
    python import_instagram_batch.py
    python import_instagram_batch.py --dry-run
    python import_instagram_batch.py --account-list accounts.txt
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

from app.config import Settings, get_settings
from app.schemas import InstagramImportRequest
from app.service import (
    InstagramImportConfigurationError,
    InstagramGraphAPIError,
    InstagramImportService,
)


DEFAULT_ACCOUNTS = [
    "micasajapon",
    "oldhousesjapan",
    "omoroiosaka",
    "japanhousedeal",
    "akiyajourney.japan",
]


def load_account_list(file_path: Path) -> list[str]:
    """Load account list from a text file (one per line)."""
    with open(file_path, encoding="utf-8") as f:
        accounts = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    return accounts


def format_batch_import_result(
    account_id: str,
    username: str,
    total_imported: int,
    total_images: int,
    errors: list[str],
) -> dict:
    """Format import result for logging."""
    return {
        "account_id": account_id,
        "username": username,
        "total_imported": total_imported,
        "total_images": total_images,
        "status": "success" if not errors else "partial" if total_imported > 0 else "failed",
        "errors": errors,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def import_accounts_batch(
    usernames: list[str],
    dry_run: bool = True,
    posts_per_account: int = 10,
    settings: Optional[Settings] = None,
    user_id: str = "batch-import-service",
) -> dict:
    """
    Import posts from multiple Instagram accounts.
    
    Args:
        usernames: List of Instagram account usernames to import
        dry_run: If True, preview only without saving to database
        posts_per_account: Number of posts to import from each account
        settings: Settings instance (uses get_settings() if None)
        user_id: User ID to associate with imports
        
    Returns:
        Summary dict with results and statistics
    """
    if not usernames:
        raise ValueError("At least one username must be provided")
    
    if posts_per_account < 1 or posts_per_account > 50:
        raise ValueError("posts_per_account must be between 1 and 50")
    
    settings = settings or get_settings()
    service = InstagramImportService(database_url=settings.effective_database_url)
    
    results = {
        "timestamp": datetime.now(UTC).isoformat(),
        "dry_run": dry_run,
        "total_accounts": len(usernames),
        "total_posts_requested": len(usernames) * posts_per_account,
        "accounts": [],
        "summary": {
            "total_posts_imported": 0,
            "total_images_stored": 0,
            "accounts_failed": 0,
            "accounts_partial": 0,
            "accounts_success": 0,
        },
    }
    
    for idx, username in enumerate(usernames, 1):
        print(f"\n[{idx}/{len(usernames)}] Importing from @{username}...")
        errors = []
        
        try:
            request = InstagramImportRequest(
                usernames=[username],
                limit=posts_per_account,
                dry_run=dry_run,
            )
            account_id, drafts = service.import_posts(request, user_id=user_id)
            
            total_images = sum(len(draft.images) for draft in drafts)
            results["accounts"].append(
                format_batch_import_result(
                    account_id=account_id,
                    username=username,
                    total_imported=len(drafts),
                    total_images=total_images,
                    errors=errors,
                )
            )
            
            results["summary"]["total_posts_imported"] += len(drafts)
            results["summary"]["total_images_stored"] += total_images
            results["summary"]["accounts_success"] += 1
            
            status = "preview" if dry_run else "saved to database"
            print(f"[OK] Imported {len(drafts)} posts with {total_images} images ({status})")
            
        except InstagramImportConfigurationError as e:
            errors.append(f"Configuration error: {e}")
            results["accounts"].append(
                format_batch_import_result(
                    account_id="unknown",
                    username=username,
                    total_imported=0,
                    total_images=0,
                    errors=errors,
                )
            )
            results["summary"]["accounts_failed"] += 1
            print(f"[ERROR] Configuration error: {e}")
            
        except InstagramGraphAPIError as e:
            errors.append(f"API error: {e}")
            results["accounts"].append(
                format_batch_import_result(
                    account_id="unknown",
                    username=username,
                    total_imported=0,
                    total_images=0,
                    errors=errors,
                )
            )
            results["summary"]["accounts_failed"] += 1
            print(f"[ERROR] API error: {e}")
            
        except Exception as e:
            errors.append(f"Unexpected error: {e}")
            results["accounts"].append(
                format_batch_import_result(
                    account_id="unknown",
                    username=username,
                    total_imported=0,
                    total_images=0,
                    errors=errors,
                )
            )
            results["summary"]["accounts_failed"] += 1
            print(f"[ERROR] Unexpected error: {e}")
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Batch import Instagram house listings",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--account-list",
        type=Path,
        help="Path to file with Instagram usernames (one per line)",
    )
    parser.add_argument(
        "--usernames",
        nargs="+",
        help="Instagram usernames to import (space-separated)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview import without saving to database or storage",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Posts to import per account (1-50, default: 10)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Save results to JSON file",
    )
    parser.add_argument(
        "--user-id",
        default="batch-import-service",
        help="User ID for import records",
    )
    
    args = parser.parse_args()
    
    # Determine which accounts to import
    usernames = []
    if args.account_list:
        usernames = load_account_list(args.account_list)
        print(f"Loaded {len(usernames)} accounts from {args.account_list}")
    elif args.usernames:
        usernames = args.usernames
    else:
        usernames = DEFAULT_ACCOUNTS
        print(f"Using default accounts: {', '.join(usernames)}")
    
    # Run batch import
    print(f"\n{'='*70}")
    print(f"Instagram Batch Import")
    print(f"{'='*70}")
    print(f"Accounts to import: {len(usernames)}")
    print(f"Posts per account: {args.limit}")
    print(f"Total posts: {len(usernames) * args.limit}")
    print(f"Dry run: {args.dry_run}")
    print(f"{'='*70}\n")
    
    try:
        results = import_accounts_batch(
            usernames=usernames,
            dry_run=args.dry_run,
            posts_per_account=args.limit,
            user_id=args.user_id,
        )
        
        # Print summary
        print(f"\n{'='*70}")
        print("SUMMARY")
        print(f"{'='*70}")
        summary = results["summary"]
        print(f"Total posts imported: {summary['total_posts_imported']}")
        print(f"Total images stored: {summary['total_images_stored']}")
        print(f"Successful accounts: {summary['accounts_success']}")
        print(f"Partial imports: {summary['accounts_partial']}")
        print(f"Failed accounts: {summary['accounts_failed']}")
        print(f"{'='*70}\n")
        
        # Save results if requested
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2)
            print(f"Results saved to {args.output}")
        
        # Exit with appropriate code
        if summary["accounts_failed"] == len(usernames):
            sys.exit(1)
        elif summary["accounts_failed"] > 0:
            sys.exit(2)
        else:
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\n\nImport cancelled by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
