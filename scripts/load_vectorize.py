"""
Get the HR documents into Cloudflare Vectorize, the way the Worker expects them.

The Worker searches the index with a filter on acl_group, so every vector has
to carry its document's acl_group, and the document text it hands the model
has to be the MASKED text. This script does both, and it runs control W4 on
the way in exactly as the offline gateway does: a hostile upload is
quarantined and never reaches the index, and personal data is masked in
everything that does.

It writes one file, results/vectorize.ndjson, one vector per line. You then
upload that file with Wrangler (the guide gives the command). Keeping the
upload a separate step means you can open the file and check it first.

    python scripts/load_vectorize.py --dry-run     # no network: what would go in
    python scripts/load_vectorize.py               # embeds with Workers AI

The real run needs CF_ACCOUNT_ID and CF_API_TOKEN set in your terminal.
VERIFIED against the Workers AI and Vectorize docs on the date in the guide.
NOT yet run against a live account.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from warden import constants as C  # noqa: E402
from warden.app.assistant import ingest_scan  # noqa: E402
from warden.backends.classifiers import get_prompt_guard  # noqa: E402
from warden.gateway.pii import get_engine  # noqa: E402

CORPUS = ROOT / "data" / "corpus" / "documents.jsonl"
OUT = ROOT / "results" / "vectorize.ndjson"
# Vectorize keeps metadata small, so the text handed back to the model is cut
# to this many characters. The HR documents in the corpus are well under it.
MAX_TEXT_CHARS = 2000
# Wrangler's documented limit is 5,000 vectors per file.
MAX_VECTORS_PER_FILE = 5000


def clean_documents() -> list:
    docs = []
    with CORPUS.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                record = json.loads(line)
                if not record.get("is_hostile"):
                    docs.append(record)
    return docs


def scan(docs: list) -> tuple:
    """Control W4 on every document. Returns (kept, quarantined)."""
    guard = get_prompt_guard("offline")
    engine = get_engine()
    kept, quarantined = [], []
    for record in docs:
        outcome = ingest_scan(record, guard, engine)
        if outcome["quarantined"]:
            quarantined.append(record["doc_id"])
        else:
            kept.append(outcome["record"])
    return kept, quarantined


def embed(texts: list, account: str, token: str) -> list:
    """One call to the Workers AI embedding model for a batch of texts."""
    import requests

    url = "{base}/accounts/{acct}/ai/run/{model}".format(
        base=C.CF_API_BASE, acct=account, model=C.CF_MODEL_EMBED)
    response = requests.post(url, headers={"Authorization": "Bearer " + token},
                             json={"text": texts}, timeout=120)
    response.raise_for_status()
    vectors = response.json()["result"]["data"]
    if len(vectors) != len(texts) or len(vectors[0]) != C.CF_EMBED_DIMS:
        raise SystemExit("Unexpected embedding shape from Workers AI. Check the "
                         "model name in constants.py against the current docs.")
    return vectors


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Prepare the Vectorize upload file")
    ap.add_argument("--dry-run", action="store_true",
                    help="scan and count only, no network, nothing written")
    ap.add_argument("--batch", type=int, default=50,
                    help="documents per embedding call (default 50)")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args(argv)

    if not CORPUS.exists():
        print("No corpus yet. Run: python data/generator/generate_corpus.py "
              "--out data/corpus")
        return 1
    kept, quarantined = scan(clean_documents())
    # Each employee's own payslip has its own group, self:E0001 and so on.
    # Count those as one line, or the listing runs to a hundred rows.
    groups = Counter("self:<each employee>" if r["acl_group"].startswith("self:")
                     else r["acl_group"] for r in kept)
    print("documents to index: {}".format(len(kept)))
    print("quarantined by W4:  {}".format(len(quarantined)))
    for group, n in sorted(groups.items()):
        print("  acl_group {:<22} {}".format(group, n))
    if len(kept) > MAX_VECTORS_PER_FILE:
        print("More than {} vectors: split the file before uploading.".format(
            MAX_VECTORS_PER_FILE))
    if args.dry_run:
        print("Dry run: nothing embedded, nothing written.")
        return 0

    account = os.environ.get("CF_ACCOUNT_ID")
    token = os.environ.get("CF_API_TOKEN")
    if not account or not token:
        print("Set CF_ACCOUNT_ID and CF_API_TOKEN in this terminal first. The "
              "guide shows where to find both.")
        return 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with out.open("w", encoding="utf-8") as fh:
        for start in range(0, len(kept), args.batch):
            batch = kept[start:start + args.batch]
            vectors = embed([r["text"] for r in batch], account, token)
            for record, values in zip(batch, vectors):
                fh.write(json.dumps({
                    "id": record["doc_id"],
                    "values": values,
                    "metadata": {
                        C.CF_METADATA_FIELD: record["acl_group"],
                        "title": record["title"],
                        "text": record["text"][:MAX_TEXT_CHARS],
                    },
                }) + "\n")
                written += 1
            print("  embedded {}/{}".format(written, len(kept)))
    print("wrote {} vectors to {}".format(written, out))
    print("Next: upload it with Wrangler, from infra/worker (see the guide).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
