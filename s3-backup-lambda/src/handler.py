import os
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

s3 = boto3.client("s3")

def _iter_objects(bucket: str, prefix: str):
    """list_objects_v2 をページングしながら列挙"""
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            yield obj

def _exists_same_size(bucket: str, key: str, size: int) -> bool:
    """同一サイズのオブジェクトが既にあるか（軽い差分判定）"""
    try:
        head = s3.head_object(Bucket=bucket, Key=key)
        return head.get("ContentLength") == size
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") in ("404", "NotFound", "NoSuchKey"):
            return False
        raise

def handler(event, context):
    """
    S3 -> S3 の“世代バックアップ”
    - SOURCE_BUCKET / SOURCE_PREFIX の内容を
    - DEST_BUCKET / DEST_PREFIX/YYYY-MM-DD/ にコピー
    - 同サイズが既にあればスキップ（無駄コピー防止の簡易策）
    """
    src_bucket = os.environ["SOURCE_BUCKET"]
    src_prefix = os.environ.get("SOURCE_PREFIX", "").lstrip("/")
    dst_bucket = os.environ["DEST_BUCKET"]
    dst_prefix = os.environ.get("DEST_PREFIX", "daily-backup").strip("/")

    today = datetime.now().strftime("%Y-%m-%d")

    copied = 0
    skipped = 0

    # prefix の正規化（相対キー計算用）
    norm_src_prefix = src_prefix + "/" if src_prefix and not src_prefix.endswith("/") else src_prefix

    for obj in _iter_objects(src_bucket, src_prefix):
        src_key = obj["Key"]
        size = obj["Size"]

        # “相対パス”を作る（prefixをはがす）
        if norm_src_prefix and src_key.startswith(norm_src_prefix):
            rel_key = src_key[len(norm_src_prefix):]
        else:
            rel_key = src_key

        # 宛先: DEST_PREFIX/2025-09-14/rel_key
        dst_key = f"{dst_prefix}/{today}/{rel_key}"

        # 既に同サイズがあればスキップ
        if _exists_same_size(dst_bucket, dst_key, size):
            print(f"[SKIP] s3://{src_bucket}/{src_key} -> s3://{dst_bucket}/{dst_key} (same size)")
            skipped += 1
            continue

        # コピー実行
        s3.copy(
            {"Bucket": src_bucket, "Key": src_key},
            dst_bucket,
            dst_key,
            ExtraArgs={"MetadataDirective": "COPY"}  # 既存メタデータを維持
        )
        print(f"[COPY] s3://{src_bucket}/{src_key} -> s3://{dst_bucket}/{dst_key}")
        copied += 1

    result = {"copied": copied, "skipped": skipped}
    print(result)
    return result
