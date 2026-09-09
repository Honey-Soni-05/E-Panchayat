"""Build the retrieval index.

    python -m app.index            # embed anything new or changed
    python -m app.index --force    # re-embed everything
    python -m app.index --dry-run  # show what would be indexed, call no API

Run this after seeding, and again whenever records change enough to matter. It
is incremental: a second run with nothing changed embeds nothing and costs
nothing.

Needs GEMINI_API_KEY. Without one the chunks are still written — the sentences
and their links are built from the database, not the model — but nothing is
embedded, so the assistant keeps using keyword retrieval until you run this
again with a key configured.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.db.session import SessionLocal
from app.services.indexer import build_drafts, reindex


async def _run(force: bool, dry_run: bool) -> int:
    with SessionLocal() as db:
        if dry_run:
            drafts = build_drafts(db)
            by_type: dict[str, int] = {}
            for d in drafts:
                by_type[d.entity_type] = by_type.get(d.entity_type, 0) + 1

            print(f"Would index {len(drafts)} chunks:")
            for entity_type, count in sorted(by_type.items()):
                print(f"  {entity_type:<16} {count:>4}")

            linked = sum(1 for d in drafts if d.links)
            print(f"\n{linked} of them carry links to other records.")
            print("\nSample:")
            for d in drafts[:3]:
                print(f"  [{d.entity_type}] {d.content[:110]}…")
            return 0

        result = await reindex(db, force=force)

    print(
        f"Chunks: {result['chunks']}  "
        f"embedded: {result['embedded']}  "
        f"unchanged: {result['unchanged']}  "
        f"removed: {result['removed']}"
    )

    if result["error"]:
        print(f"\nStopped early: {result['error']}", file=sys.stderr)
        print(
            f"{result['pending']} chunks are written but not embedded. They are "
            "skipped by search rather than treated as matches, so the assistant "
            "falls back to keyword retrieval. Re-run this once the key is set.",
            file=sys.stderr,
        )
        return 1

    if result["embedded"] == 0 and result["unchanged"] == 0:
        print("\nNothing to index. Has the database been seeded?", file=sys.stderr)
        return 1

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the semantic retrieval index.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-embed every chunk, not only the changed ones.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be indexed without calling the embedding API.",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(args.force, args.dry_run)))


if __name__ == "__main__":
    main()
