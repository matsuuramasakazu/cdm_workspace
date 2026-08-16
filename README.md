# CDM Workspace (`cdm-workspace`)

FINOS CDM (Common Domain Model v7.1.0) を使用した金利スワップ（IRS）取引データ構築および Rune / Pydantic v2 ランタイム互換性レイヤーを提供する Python ライブラリ・ワークスペースです。

---

## 📁 ディレクトリ構成

```text
cdm_workspace/
├── docs/
│   └── RUNE_COMPATIBILITY.md       # Rune/Pydantic v2 互換性パッチの詳細技術ドキュメント
├── src/
│   ├── cdm_workspace/              # プロジェクト本体パッケージ
│   │   ├── __init__.py             # パッケージエントリポイント
│   │   └── create_irs_trade.py     # プレーン・バニラ IRS 取引構築・JSONシリアライズ
│   └── cdm_compat/                 # 汎用 CDM ランタイム互換性レイヤー (再利用可能モジュール)
│       ├── __init__.py             # 自動パッチ適用・モデル一括修復
│       ├── patch_metadata.py       # rune.runtime.metadata に対する低レベルパッチ
│       ├── rebuild_models.py       # Pydantic v2 スキーマ修復・継承フィールド同期エンジン
│       └── py.typed                # PEP 561 型ヒントマーカー
├── tests/                          # 単体テスト (pytest)
│   ├── conftest.py                 # pytest 共通設定
│   ├── cdm_workspace/
│   │   └── test_create_irs_trade.py # IRS 取引生成・JSON出力の単体テスト
│   └── cdm_compat/
│       └── test_cdm_compat.py       # 互換レイヤー・スキーマ修復の単体テスト
├── irs_trade.json                  # 生成サンプル JSON
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

詳細な技術的背景やアーキテクチャについては [docs/RUNE_COMPATIBILITY.md](docs/RUNE_COMPATIBILITY.md) を参照してください。

---

## 🧪 テストの実行

pytest を使用して全テストを実行します。

```bash
pytest -v
```
