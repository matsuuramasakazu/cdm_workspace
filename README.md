# CDM Workspace (`cdm-workspace`)

FINOS CDM (Common Domain Model v6.22.0+ / v7.x) を使用した金利スワップ（IRS）取引データ構築および Rune / Pydantic v2 ランタイム互換性レイヤーを提供する Python ライブラリ・ワークスペースです。

---

## 📁 ディレクトリ構成

```text
cdm_workspace/
├── .agents/
│   ├── agents/                     # 専門カスタムサブエージェント (Quant & Python Architect)
│   ├── rules/                      # 不変のコーディング・設計規約 (Constraints & Rules)
│   └── skills/                     # 運用手順書 (Runbooks & Skills)
├── docs/
│   ├── AGENT_HARNESS.md            # AI エージェントハーネスの設計思想 & 活用ガイド
│   ├── CDM_VERSION_DOWNGRADE_6_22.md # FINOS CDM v6.22.0 ダウングレード・非互換仕様ガイド
│   ├── IRS_BUSINESS_EVENTS.md      # 金利スワップの TradeState & ビジネスイベント仕様書
│   └── RUNE_COMPATIBILITY.md       # Rune/Pydantic v2 互換性パッチの詳細技術ドキュメント
├── src/
│   ├── cdm_workspace/              # プロジェクト本体パッケージ
│   │   ├── __init__.py             # パッケージエントリポイント & 公開API
│   │   ├── create_irs_trade.py     # プレーン・バニラ IRS 取引構築・JSONシリアライズ
│   │   ├── agent_harness.py        # AI エージェント用ハーネス CLI ラッパー
│   │   └── harness/                # 汎用 AI エージェントハーネス (Core & CDM Plugin)
│   │       ├── __init__.py
│   │       ├── core.py             # 汎用環境診断 (doctor), 検証 (verify), 安全実行 (exec)
│   │       ├── cdm_plugin.py       # CDM モデル検査 (inspect), イベント一覧, IRS生成
│   │       └── cli.py              # 統合 CLI エントリポイント
│   └── cdm_compat/                 # 汎用 CDM ランタイム互換性レイヤー (再利用可能モジュール)
│       ├── __init__.py             # 自動パッチ適用・モデル一括修復
│       ├── patch_metadata.py       # rune.runtime.metadata に対する低レベルパッチ
│       ├── rebuild_models.py       # Pydantic v2 スキーマ修復・継承フィールド同期エンジン
│       └── py.typed                # PEP 561 型ヒントマーカー
├── tests/                          # 単体テスト (pytest)
│   ├── conftest.py                 # pytest 共通設定
│   ├── cdm_workspace/
│   │   ├── test_create_irs_trade.py # IRS 取引生成・JSON出力の単体テスト
│   │   └── test_harness.py          # AI エージェントハーネスの単体テスト
│   └── cdm_compat/
│       └── test_cdm_compat.py       # 互換レイヤー・スキーマ修復の単体テスト
├── irs_trade.json                  # 生成サンプル JSON
├── AGENTS.md                       # AI エージェント用運用ルール & ガイドライン
├── pyproject.toml                  # PEP 517/518/621 パッケージ設定 & pytest 設定
├── .gitignore
└── README.md
```

---

## 🚀 インストール & セットアップ

### 開発モードでのインストール
```bash
pip install -e .
```

---

## 🤖 AI Agent Harness（高速診断・実行・検証）

AI Agent および開発者が本ワークスペースで迅速かつ安全に作業するための統合ハーネスを提供しています。

```bash
# 1. 環境診断（仮想環境、依存関係、cdm_compat の健全性を 1 秒未満で確認）
python -m cdm_workspace.harness doctor

# 2. 自動検証パイプライン（テスト実行と結果サマリー）
python -m cdm_workspace.harness verify

# 3. CDM モデル高速インスペクター（循環インポートを起こさずクラス定義・フィールド・型を表示）
python -m cdm_workspace.harness inspect Trade
python -m cdm_workspace.harness inspect TradeState

# 4. IRS ライフサイクルビジネスイベント一覧表示
python -m cdm_workspace.harness events

# 5. IRS サンプル取引生成・JSON検証
python -m cdm_workspace.harness irs
```

---

## 💡 使い方

### 1. Plain Vanilla IRS 取引の生成

```python
from cdm_workspace.create_irs_trade import create_plain_irs_trade

# デフォルト設定 (JPY 固定 vs. TONA OIS、10億円、5年物)
trade = create_plain_irs_trade()

# JSON にシリアライズ
json_data = trade.model_dump_json(indent=2, exclude_none=True)
print(json_data)
```

### 2. JSON ファイル出力とバリデーション

```bash
# スクリプトとして直接実行 (irs_trade.json を出力・検証)
python -m cdm_workspace.create_irs_trade
```

### 3. CDM 互換レイヤー (`cdm_compat`) の単体利用

`finos-cdm` モデルを利用する前に `import cdm_compat` を実行するだけで、Rune 2.0.1+ および Pydantic v2 のスキーマ欠損・メタデータシリアライズ問題が自動で修復されます。

```python
import cdm_compat
from finos.cdm.event.common.Trade import Trade
from finos.cdm.event.common.TradeIdentifier import TradeIdentifier
```

---

## 📚 ドキュメント

- [AGENTS.md](AGENTS.md): AI Agent 運用ルール・環境制約・コマンド実行ガイドライン
- [docs/IRS_BUSINESS_EVENTS.md](docs/IRS_BUSINESS_EVENTS.md): 金利スワップ（IRS）における `TradeState` の構造および全ライフサイクルビジネスイベント（リセット、利払い、中途解約、ノベーション、指標移行等）の仕様解説
- [docs/RUNE_COMPATIBILITY.md](docs/RUNE_COMPATIBILITY.md): Rune/Pydantic v2 互換性パッチの詳細技術ドキュメント

---

## 🧪 テストの実行

pytest を使用して全テストを実行します。

```bash
pytest -v
```

