"""
SKONGA Library API — Git → Postgres Ingestion Script
======================================================
Reads the structured content from the SKONGA Library Git repository
(content/subjects/.../meta.json + content.md) and upserts every
subject, form, and topic into the Postgres database.

This script is the ONLY way data enters the database. The Git repo
remains the single source of truth — Postgres is the "runtime store"
that the API queries at high speed.

Run:
    python3 ingestion/sync_from_git.py --content-dir /path/to/skonga-library/content

Or set LIBRARY_CONTENT_DIR env var and run without arguments.
"""
import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

# Allow running from the repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.db.models import Base, Form, Subject, SubjectForm, Topic
from app.db.session import SessionLocal, engine


def upsert_subject(db, meta: dict, subject_id: str) -> None:
    existing = db.query(Subject).filter(Subject.id == subject_id).first()
    if existing:
        existing.name_en = meta.get("name_en", subject_id)
        existing.name_sw = meta.get("name_sw", subject_id)
        existing.icon = meta.get("icon")
        existing.schema_version = meta.get("schema_version", 1)
        existing.last_updated = date.fromisoformat(meta.get("last_updated", date.today().isoformat()))
    else:
        db.add(Subject(
            id=subject_id,
            name_en=meta.get("name_en", subject_id),
            name_sw=meta.get("name_sw", subject_id),
            icon=meta.get("icon"),
            schema_version=meta.get("schema_version", 1),
            last_updated=date.fromisoformat(meta.get("last_updated", date.today().isoformat())),
        ))


def upsert_topic(db, meta: dict, content_md: str | None = None) -> None:
    topic_id = meta["id"]
    existing = db.query(Topic).filter(Topic.id == topic_id).first()

    kwargs = dict(
        subject_id=meta["subject"],
        form_id=meta["form"],
        order_index=meta.get("order_index", 0),
        title_en=meta.get("title_en", ""),
        title_sw=meta.get("title_sw", ""),
        competency_mkuu=meta.get("competency_mkuu"),
        tags=meta.get("tags", []),
        related_topics=meta.get("related_topics", []),
        difficulty=meta.get("difficulty"),
        status=meta.get("status", "skeleton"),
        content_version=meta.get("content_version", 1),
        last_updated=date.fromisoformat(meta.get("last_updated", date.today().isoformat())),
        content_md=content_md,
    )
    if existing:
        for k, v in kwargs.items():
            setattr(existing, k, v)
    else:
        db.add(Topic(id=topic_id, **kwargs))


def ensure_subject_form(db, subject_id: str, form_id: int) -> None:
    exists = (
        db.query(SubjectForm)
        .filter(SubjectForm.subject_id == subject_id, SubjectForm.form_id == form_id)
        .first()
    )
    if not exists:
        db.add(SubjectForm(subject_id=subject_id, form_id=form_id))


def sync(content_dir: Path) -> None:
    print(f"[sync] Starting ingestion from {content_dir}")

    # Ensure schema exists
    Base.metadata.create_all(bind=engine)

    # Ensure all 6 form rows exist
    db = SessionLocal()
    try:
        for form_id in range(1, 7):
            if not db.query(Form).filter(Form.id == form_id).first():
                db.add(Form(id=form_id))
        db.commit()
    finally:
        db.close()

    subjects_dir = content_dir / "subjects"
    if not subjects_dir.exists():
        print(f"[sync] ERROR: {subjects_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    total_subjects = 0
    total_topics = 0
    errors = []

    for subject_dir in sorted(subjects_dir.iterdir()):
        if not subject_dir.is_dir():
            continue

        manifest_path = subject_dir / "manifest.json"
        if not manifest_path.exists():
            errors.append(f"No manifest.json in {subject_dir}")
            continue

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        subject_id = manifest.get("id") or subject_dir.name

        db = SessionLocal()
        try:
            upsert_subject(db, manifest, subject_id)
            db.commit()
            total_subjects += 1

            # Walk form-N/topics/ subdirectories
            for form_dir in sorted(subject_dir.glob("form-*")):
                if not form_dir.is_dir():
                    continue
                form_num = int(form_dir.name.split("-")[1])
                ensure_subject_form(db, subject_id, form_num)

                for topic_dir in sorted((form_dir / "topics").glob("*")):
                    if not topic_dir.is_dir():
                        continue

                    meta_path = topic_dir / "meta.json"
                    if not meta_path.exists():
                        errors.append(f"No meta.json in {topic_dir}")
                        continue

                    meta = json.loads(meta_path.read_text(encoding="utf-8"))

                    content_md = None
                    content_path = topic_dir / "content.md"
                    if content_path.exists():
                        raw = content_path.read_text(encoding="utf-8").strip()
                        # Skip frontmatter (--- ... ---)
                        if raw.startswith("---"):
                            parts = raw.split("---", 2)
                            content_md = parts[2].strip() if len(parts) >= 3 else raw
                        else:
                            content_md = raw

                    upsert_topic(db, meta, content_md)
                    total_topics += 1

            db.commit()
            print(f"  [sync] {subject_id}: upserted")
        except Exception as exc:
            db.rollback()
            errors.append(f"{subject_id}: {exc}")
        finally:
            db.close()

    print(f"\n[sync] Finished: {total_subjects} subjects, {total_topics} topics upserted")
    if errors:
        print(f"[sync] {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("[sync] ✅ No errors. Database is in sync with Git content.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync SKONGA Library content into Postgres")
    parser.add_argument(
        "--content-dir",
        default=os.environ.get("LIBRARY_CONTENT_DIR", "content"),
        help="Path to the content/ directory of the skonga-library repo",
    )
    args = parser.parse_args()
    sync(Path(args.content_dir))
