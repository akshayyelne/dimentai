"""Import the SYNTHETIC mock grounding fixture into a Vertex AI Search data store.

⚠️  TEST UTILITY — loads FABRICATED data for pipeline testing only.
    Point --data-store at a MOCK/secondary RAG store, never a production one.

Usage:
    python ingest_mock_grounding.py --data-store <MOCK_DATA_STORE_ID> --dry-run
    python ingest_mock_grounding.py --data-store <MOCK_DATA_STORE_ID>

Each record is written with its `id`, with the full JSON object stored as the
document's struct/json data so retrieval + the Phase 4.4 hallucination audit can
inspect provenance fields (data_status, not_for_clinical_use, provenance).
"""
import argparse
import json
import pathlib

PROJECT = "dimentai1"
LOCATION = "global"
COLLECTION = "default_collection"  # NOTE: Vertex collection, not a Firestore collection
FIXTURE = pathlib.Path(__file__).with_name("clinical_grounding_mock.jsonl")


def load_records():
    records = []
    with FIXTURE.open() as fh:
        for line_no, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"Invalid JSON on line {line_no}: {exc}")
    return records


def guard(records):
    """Refuse to ingest anything not explicitly marked as a test fixture."""
    for r in records:
        if not r.get("not_for_clinical_use", False):
            raise SystemExit(
                f"Record {r.get('id')!r} is missing not_for_clinical_use=true; "
                "this script only ingests watermarked mock data."
            )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-store", required=True, help="MOCK/secondary data store ID")
    ap.add_argument("--dry-run", action="store_true", help="Validate + print, do not write")
    args = ap.parse_args()

    records = load_records()
    guard(records)
    print(f"Loaded {len(records)} watermarked mock records from {FIXTURE.name}")

    if args.dry_run:
        for r in records:
            print(f"  [dry-run] {r['id']:<28} {r.get('doc_type','?'):<18} {r['data_status']}")
        print("Dry run only — nothing written.")
        return

    # Imported lazily so --dry-run works without the SDK installed.
    from google.cloud import discoveryengine_v1 as de

    client = de.DocumentServiceClient()
    parent = client.branch_path(
        PROJECT, LOCATION, args.data_store, "default_branch"
    ) if hasattr(client, "branch_path") else (
        f"projects/{PROJECT}/locations/{LOCATION}/collections/{COLLECTION}"
        f"/dataStores/{args.data_store}/branches/default_branch"
    )

    for r in records:
        doc = de.Document(id=r["id"], json_data=json.dumps(r))
        client.create_document(parent=parent, document=doc, document_id=r["id"])
        print(f"  ingested {r['id']}")
    print(f"Done. {len(records)} mock records written to {args.data_store}.")


if __name__ == "__main__":
    main()
