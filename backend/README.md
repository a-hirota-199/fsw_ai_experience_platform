# backend (FastAPI)

AIオーケストレーション・外部サービス抽象化レイヤー・状態管理・Webhook受け口を担う共有バックエンド。Web(Streamlit)とIDE(VSCode拡張)の両クライアントが、ここの同じプロジェクト状態を読む。

## サブモジュール

| ディレクトリ | 役割 |
|---|---|
| `api/` | チャット・生成・レビュー・Webhook のHTTPエンドポイント |
| `flow/` | `structure.py`（要件構造化）/ `generate.py`（コード生成）/ `review.py`（自己レビュー） |
| `integrations/` | 外部サービス抽象化レイヤー。`base.py` の共通IFに `github.py` / `jira.py` / `slack.py` / `redmine.py`(口だけ) を実装 |
| `llm/` | swappable LLM 境界。`client.py`（provider非依存IF）＋ `providers/`（anthropic ほか） |
| `templates/` | cFSアプリ骨格（穴あきテンプレ; skeleton_app基点） |

## 原則

- **n8n＝配線、backend＝中身**。AI呼び出しと外部呼び出しの実体はすべてここに置き、n8nはこのAPIを叩くだけ。
- **LLMはswappable**。生成・レビューは必ず `llm/client.py` 経由。providerをハードコードしない。
- **決定論と非決定論を分離**。LLMが触るのは「穴埋め」だけ。配線・MID・ビルド構成は決定論側。
