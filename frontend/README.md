# frontend (Streamlit) — Web 3画面

backend API を叩く薄いWebクライアント。Webhookは扱わず、状態はすべて backend 越しに取得する。

| 画面 | 役割 |
|---|---|
| オンボーディング設定 | 開発プロセス定義（repo/issue/通知/検証環境/承認フロー）。デフォルト：GitHub＋Jira＋Slack＋Docker |
| 対話チャット | ミッション入力・要件構造化・生成物の説明/レビュー・自然言語修正 |
| 進捗ダッシュボード | Issue/PR/ビルド/承認の状態を一覧 |

Sprint 0 では「対話チャット」だけを立ち上げ、要件構造化を一周させる。
