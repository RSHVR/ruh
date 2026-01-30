#!/usr/bin/env python3
"""Test the simplified extraction service.

Usage:
    python scripts/test_extraction.py [--url URL] [--force-js]
"""

import asyncio
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from supabase import create_client
from src.infrastructure.config import settings
from src.infrastructure.extraction_service import ExtractionService


async def test_extraction(url: str, force_js: bool = False):
    """Test extraction on a single URL."""
    print(f"\n{'='*70}")
    print(f"Testing: {url}")
    print(f"{'='*70}")

    supabase = create_client(settings.supabase_url, settings.supabase_key)
    service = ExtractionService(supabase_client=supabase)

    try:
        content = await service.extract(url, force_js=force_js, skip_cache=True)

        print(f"\nResults:")
        print(f"  Title: {content.title}")
        print(f"  Extractor: {content.extractor}")
        print(f"  JS Rendered: {content.js_rendered}")
        print(f"  Content: {content.content_length:,} chars")
        print(f"  Time: {content.extraction_time_ms}ms")

        if content.metadata:
            print(f"\n  Metadata: {content.metadata}")

        print(f"\n  Text preview (first 300 chars):")
        print(f"  {content.text[:300]}...")

        print(f"\n{'='*70}")
        print(f"Stats: {service.get_stats()}")

    finally:
        await service.close()


async def test_all():
    """Test extraction on multiple sites."""
    urls = [
        ("PubMed", "https://pubmed.ncbi.nlm.nih.gov/33945786/"),
        ("PMC", "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7158881/"),
        ("FDA", "https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts"),
        ("IARC", "https://monographs.iarc.who.int/agents-classified-by-the-iarc/"),
        ("EPA (JS)", "https://www.epa.gov/pfas"),
        ("EWG (JS)", "https://www.ewg.org/skindeep/"),
    ]

    supabase = create_client(settings.supabase_url, settings.supabase_key)
    service = ExtractionService(supabase_client=supabase)

    try:
        print("\n" + "=" * 70)
        print("EXTRACTION SERVICE AUDIT")
        print("=" * 70)

        for name, url in urls:
            try:
                content = await service.extract(url, skip_cache=True)
                status = "✅" if content.content_length > 500 else "⚠️"
                js = "🔄 JS" if content.js_rendered else "📄"
                print(f"{status} {js} {name}: {content.content_length:,} chars in {content.extraction_time_ms}ms")
            except Exception as e:
                print(f"❌ {name}: {e}")

        print("\n" + "-" * 70)
        print(f"Stats: {service.get_stats()}")

    finally:
        await service.close()


async def main():
    parser = argparse.ArgumentParser(description="Test extraction service")
    parser.add_argument("--url", type=str, help="URL to extract")
    parser.add_argument("--force-js", action="store_true", help="Force JS rendering")
    parser.add_argument("--all", action="store_true", help="Test all sites")
    args = parser.parse_args()

    if args.all:
        await test_all()
    elif args.url:
        await test_extraction(args.url, force_js=args.force_js)
    else:
        # Default: test PMC
        await test_extraction("https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7158881/")


if __name__ == "__main__":
    asyncio.run(main())
