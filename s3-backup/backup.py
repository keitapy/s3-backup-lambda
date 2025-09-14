import os
import json
import hashlib
import mimetypes
from datetime import datetime
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

def load_config():
    with open("parameters.json", "r", encoding="utf-8") as f:
        return json.load(f)

def iter_files(root: Path, include_exts, skip_hidden=True):
    for p in root.rglob("*"):
        if p.is_file():
            if skip_hidden and any(part.startswith(".") for part in p.parts):
                continue
            if include_exts and p.suffix.lower() not in [e.lower() for e in include_exts]:
                continue
            yield p

def s3_key_for(dest_prefix: str, base_dir: Path, file_path: Path, date_prefix: str):
    # 例: daily-backup/2025-08-08/subdir/file.csv
    rel = file_path.relative_to(base_dir).as_posix()
    return f"{dest_prefix}/{date_prefix}/{rel}"

def object_exists_with_same_size(s3, bucket, key, size):
    try:
        head = s3.head_object(Bucket=bucket, Key=key)
        return head.get("ContentLength") == size
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return False
        raise

def main():
    cfg = load_config()
    bucket = cfg["bucket"]
    dest_prefix = cfg["dest_prefix"]
    source_dir = Path(cfg["source_dir"]).expanduser().resolve()
    include_exts = cfg.get("include_extensions", [])
    skip_hidden = cfg.get("skip_hidden", True)

    s3 = boto3.client("s3")
    date_prefix = datetime.now().strftime("%Y-%m-%d")

    uploaded, skipped, failed = 0, 0, 0

    for file_path in iter_files(source_dir, include_exts, skip_hidden):
        key = s3_key_for(dest_prefix, source_dir, file_path, date_prefix)
        size = file_path.stat().st_size

        # 既に同サイズがあるならスキップ（差分アップロードっぽく動く）
        if object_exists_with_same_size(s3, bucket, key, size):
            print(f"[SKIP] {file_path} -> s3://{bucket}/{key} (same size)")
            skipped += 1
            continue

        ctype, _ = mimetypes.guess_type(str(file_path))
        extra_args = {"ContentType": ctype} if ctype else {}

        try:
            s3.upload_file(str(file_path), bucket, key, ExtraArgs=extra_args)
            print(f"[OK]   {file_path} -> s3://{bucket}/{key}")
            uploaded += 1
        except Exception as e:
            print(f"[ERR]  {file_path}: {e}")
            failed += 1

    print(f"\nDone. uploaded={uploaded}, skipped={skipped}, failed={failed}")

if __name__ == "__main__":
    main()