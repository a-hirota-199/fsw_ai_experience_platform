# vscode-extension (TypeScript) — IDE実装層

Issue一覧→選択→インラインでAIと実装・修正、を体験するための VSCode 拡張。**Webチャットの会話文脈を `project_id` 経由で引き継ぐ**（Web↔IDEの文脈共有）。

## 原則

- 拡張は **backend API を叩く薄いクライアント**に徹する。ロジックは backend に置く（Streamlitと同方針）。
- 文脈共有は `project_id` をキーに会話・要件・Issue を backend から取得するだけ。
- Marketplace公開はせず、**ローカル sideload** で動けばよい。

Sprint 6 で着手（backboneが固まってから）。
