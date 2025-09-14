# s3-backup-lambda

S3 上のある場所（バケット/プレフィックス）を、**毎日** `DEST_PREFIX/YYYY-MM-DD/` の世代フォルダにコピーする Lambda（EventBridge トリガー）。

- 例）`s3://src-bucket/logs/app1/a.csv`  
  → `s3://dst-bucket/daily-backup/2025-09-14/logs/app1/a.csv`

## 特徴
- **簡易差分**：同サイズのオブジェクトがすでにある場合はスキップ
- **サーバーレス**：Lambda + EventBridge だけで完結
- **運用楽**：ログ保持日数はテンプレートのパラメータで管理

## アーキテクチャ
- EventBridge（スケジュール） → Lambda（S3 list/copy）

## デプロイ（SAM）
```bash
# 1) 依存のビルド
sam build

# 2) 初回デプロイ（対話）
sam deploy --guided \
  --stack-name s3-backup-lambda \
  --capabilities CAPABILITY_IAM
