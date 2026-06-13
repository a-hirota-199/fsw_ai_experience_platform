# integrations — 外部サービス抽象化レイヤー

「issue取得/更新/コメント・repo操作・通知」を**サービス非依存の共通インターフェース**(`base.py`)で定義し、各サービスのアダプタを差し替え可能にする。これが机上でなく本物だと示すのが Sprint 4 の狙い。

| ファイル | サービス | 位置づけ |
|---|---|---|
| `base.py` | — | 共通IF（抽象基底） |
| `github.py` | GitHub | **背骨**（repo / Issue / PR）。Sprint 1〜 |
| `jira.py` | Jira | 2つ目の実アダプタ（抽象化の実証）。Sprint 4 |
| `slack.py` | Slack | 通知（outbound専用） |
| `redmine.py` | Redmine | **口だけ**（NotImplemented）。需要が出たら実装 |

オンボーディング設定で issue バックエンドを GitHub ⇄ Jira に切り替えても、同じパイプラインが動くことを確認する。
