# Lawful local retrieval and explicit reconstruction

Prepared 6 November 2026. These are new release aids, not missing historical experiment scripts. Keep all restoration products in a new external private directory. Downloading publicly accessible material does not itself grant onward redistribution rights.

The official pinned SciFact download script identifies `https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz`: https://github.com/allenai/scifact/blob/68b98a56d93e0f9da0d2aab4e6c3294699a0f72e/script/download-data.sh . Retrieve under applicable terms into a private external folder and extract only `data/corpus.jsonl`. The release URL is mutable: require corpus SHA-256 `b8d6c89624cb2ed74dee8938effc4f5d8bd2086887880af8110d64be4ceade62` before reconstruction. A mismatch must stop restoration; do not replace frozen data with a newer corpus. No downloaded archive is bundled here.

From this repository root, after lawfully obtaining that exact corpus:

```bash
PYTHONDONTWRITEBYTECODE=1 python3.12 reconstruction/reconstruct_scifact_tasks.py --corpus /absolute/private/data/corpus.jsonl --output-dir /absolute/new/private-restoration
```

The metadata-only recipes retain original task/claim IDs, prompts, labels, document order and provenance fields, with source context supplied from the external corpus. SciFact claim/annotation components retain CC BY 4.0 and the original SciFact/S2ORC notices apply. The helper uses the unchanged historical formatter and refuses any corpus or reconstructed-file hash mismatch. All ten task files were checked byte-for-byte against the frozen archive during preparation; no sampling or new model request is involved. These reconstructed copies are labelled as such; they do not replace the original private evidence.

This reconstructs ten approved/processed task files, including the 100 confirmatory packets. Only 349 distinct abstracts appear in those final packets, versus 5,183 in the full raw corpus; all ten task-file recipes use 460 distinct documents. Sharing those fewer abstracts would still need an applicable content-level basis; reduced scope is not automatic clearance.

The remaining source-bearing response/judge logs, human annotations and historical audits cannot be recovered exactly from a corpus download. Their expected original paths and hashes are in rights/WITHHELD_FILES.csv. Restore them only from the unchanged private archive when access and reuse are lawful. No public download of those frozen original responses has been authorised, and rerunning models would not recreate them. The complete 94,682,411-byte results.jsonl remains private and intact.

HaluEval's exact pinned source is https://github.com/RUCAIBox/HaluEval/tree/b7253db3cdaa0ab2c382f92b26b390109174f77e . Raw QA retrieval under upstream terms is possible; its source matches and partial article-attribution sidecar are retained in the private finalisation evidence. Fetching HaluEval does not resolve incomplete Wikipedia contributor credit for further distribution. No newly generated substitute responses or labels are supplied.
