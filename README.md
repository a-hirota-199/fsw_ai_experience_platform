# fsw_ai_experience_platform

衛星FSW特化 AI開発プラットフォームの **体験版プロトタイプ**。
「オンボーディング → 要件をチャットで構造化 → cFSコード生成 → GitHubにPR → Issue起票 → AIレビュー → ビルド → Slack通知 → 人間が承認」という**プラットフォーム全体の一気通貫を、薄く・本物として体験**することを目的とする学習用プロトタイプ。

> 設計・計画の詳細は別リポジトリ `fsw_ai_driven_development`（mkdocsドキュメント）の
> `docs/plan/experience-prototype-plan.md` を参照。本リポジトリはその実装。

## 目的（1文）

生成AIでソフトウェア開発を行う体験そのものをチームで掴み、**AI駆動FSW開発のどこが効いて・どこで詰まるかを学ぶ**こと。プロダクトではなく実験台であり、判断基準は「信用」より「学び」。

## アーキテクチャ（最小構成）

`docker-compose` で以下を一括起動する想定:

| 要素 | 採用 | 役割 |
|---|---|---|
| backend | FastAPI (Python) | AIオーケストレーション＋外部抽象化レイヤー＋状態管理＋Webhook受け口 |
| frontend (Web) | Streamlit | オンボ設定 / 対話チャット / 進捗ダッシュボード の3画面 |
| frontend (IDE) | VSCode拡張 (TypeScript) | Issue選択→実装、Webの会話文脈を `project_id` 経由で共有 |
| 自動化 | n8n (セルフホスト) | サービス間の配線とトリガ（③〜⑧）。ロジックは持たず backend API を叩く |
| 状態 | PostgreSQL | 設定・プロジェクト状態・Issue/PR紐付け・会話を永続 |
| LLM | swappable境界（mock / Claude / Gemini） | provider非依存。BYOK/差し替えは provider 追加だけ |

## ディレクトリ構成

```
backend/            FastAPI: AI・外部抽象化・状態管理
  api/                チャット・生成・レビュー・Webhook受け口
  flow/               要件構造化 / コード生成 / 自己レビュー
  integrations/       外部サービス抽象化レイヤー（github/jira/slack/redmine）
  llm/                swappable LLM 境界（client + providers）
  templates/          cFSアプリ骨格（穴あきテンプレ; skeleton_app基点）
frontend/           Streamlit: オンボ設定 / チャット / 進捗 の3画面
vscode-extension/   TypeScript: backend APIを叩く薄いIDEクライアント
n8n/                ワークフロー定義（③〜⑧のパイプライン）
cfs-build/          軽量検証用 Dockerイメージ（ビルド段）
sessions/           会話ログ・つまずき記録（= 学びの成果物）
```

## 開発の進め方（Sprint）

| Sprint | 内容 |
|---|---|
| 0 | 基盤とチャットの背骨（要件→構造化JSON、swappable LLM境界） |
| 1 | コード生成＋GitHub実接続（要件確定→PRが立つ） |
| 2 | n8n導入＋自動化パイプライン（③〜⑥、イベントはポーリング既定） |
| 3 | 軽量検証＋Slack通知＋承認（⑦⑧⑨） |
| 4 | オンボーディング設定＋外部抽象化レイヤーの実証（GitHub⇄Jira切替） |
| 5 | 進捗ダッシュボード |
| 6 | VSCode拡張（IDE実装層）＋全体の振り返り |

## ローカル実行（Sprint 0：ローカルvenv先行）

Sprint 0 は APIキー不要のモック provider で動く（`LLM_PROVIDER=mock`）。

```bash
make install        # .venv 作成＋依存インストール（pip install -e ".[dev]"）
make test           # 要件構造化フローの一周をpytestで検証
make backend        # FastAPI を :8000 で起動
make frontend       # 別ターミナルで Streamlit チャットを起動
```

ブラウザで Streamlit を開き、「姿勢データを5Hzでテレメトリ送出したい」等を入力すると、
AIが質問を返し、2ターン目以降で構造化要件（JSON）が確定する。

`.env` は backend / frontend 起動時に**自動読込**される（手動 source 不要）。provider を
切り替えるには `.env` の `LLM_PROVIDER` を変える（**既定は `mock` なので、実LLMを使うには必ず変更が必要**）。

### 実 Claude（Anthropic API）で試す

```bash
cp .env.example .env   # 初回のみ
# .env を編集:
#   LLM_PROVIDER=anthropic            # ← mock から変更（必須）
#   ANTHROPIC_API_KEY=sk-ant-...      # 自分のキー（BYOK）
#   ANTHROPIC_MODEL=claude-opus-4-8   # 最も高性能を試すなら claude-fable-5
make backend                         # 別ターミナルで make frontend
```

キー未設定のまま anthropic を選ぶと、500 ではなくチャットに「LLM呼び出しエラー: ANTHROPIC_API_KEY が未設定です」と表示される。

### 実 Google Gemini で試す

```bash
cp .env.example .env   # 初回のみ
# .env を編集:
#   LLM_PROVIDER=gemini               # ← mock から変更（必須）
#   GEMINI_API_KEY=...                # 自分のキー（GOOGLE_API_KEY でも可; BYOK）
#   GEMINI_MODEL=gemini-2.5-flash     # 既定
make backend                         # 別ターミナルで make frontend
```

APIキーは [Google AI Studio](https://aistudio.google.com/apikey) で発行する。

### 実 GitHub に公開する（生成物を branch+PR に）

既定は `mock`（実接続しない）。実GitHubに公開するには、公開先の**既存リポジトリ**（サンドボックス推奨）と PAT を用意する:

```bash
# .env を編集:
#   GITHUB_PROVIDER=github            # ← mock から変更（必須）
#   GITHUB_TOKEN=ghp_...              # repo スコープの PAT（fine-grained なら contents:write + pull_requests:write）
#   GITHUB_REPO=owner/name            # 公開先の既存リポジトリ
make backend                         # 別ターミナルで make frontend
```

チャットで要件確定 → 「🛠 コード生成」→ 「🚀 GitHubにPRを作成」を押すと、`feat/<app>` ブランチに
生成物をコミットし、既定ブランチ宛の PR を起票して PR リンクを表示する。PAT未設定のまま github を
選ぶと、500 ではなくUIに「GitHub公開エラー: GITHUB_TOKEN が未設定です」と表示される。

PAT は [GitHub Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens) で発行する。

### 現在の provider を確認する

```bash
curl -s localhost:8000/health      # {"status":"ok","llm_provider":"gemini","github_provider":"github"} のように表示
```

`llm_provider` が `mock` のままなら `.env` の `LLM_PROVIDER` が未変更（または別シェルで
backend を起動して `.env` を読めていない）。mock は定型応答（app_name が `sample_tlm_app`）で見分けられる。

## ステータス

- **Sprint 0 完了**: チャット→要件構造化。swappable LLM境界（mock / Claude / Gemini）。UIは design system 準拠でモダン化済み。
- **Sprint 1（生成）完了**: 構造化要件 → cFSアプリ骨格を生成（決定論テンプレ＋LLM穴埋め）。チャットで「🛠 コード生成」→ ファイル表示＋ZIPダウンロード。
  - 決定論側（templates/cfs_app.py）: app名・コマンドコード・テレメトリ構造体・配線・ディスパッチ・HK送出。
  - 非決定論側（穴）: HK値詰め・各コマンドハンドラ本体を LLM が埋める（未生成はスタブ補完）。
- **Sprint 1 後半（GitHub実接続）完了**: 生成物を指定リポジトリに `feat/<app>` ブランチでコミットし PR を起票（「🚀 GitHubにPRを作成」）。
  - swappable な GitHub 境界（integrations/）: 既定 `mock`（キー不要）、`GITHUB_PROVIDER=github` で実GitHub（PATでオプトイン）。
- **次**: Sprint 2（n8n自動化パイプライン、イベントはポーリング既定）。
- 後回し: 軽量ビルド検証（Sprint 3）、n8n自動化、docker-compose 一括起動。
