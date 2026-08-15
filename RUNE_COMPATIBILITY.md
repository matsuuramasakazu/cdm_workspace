# Runeランタイム互換性パッチ & `cdm_compat` ライブラリ 詳細解説

本文書は、`finos-cdm` (v7.1.0) および `rune-runtime` (v2.0.1+) を Python (Pydantic v2) 環境で使用する際に発生する型解決・メタデータシリアライズの問題点と、それを解消するために開発された再利用可能ライブラリ **`cdm_compat`** のアーキテクチャ・動作原理について解説します。

---

## 1. 背景とアーキテクチャ

FINOS CDM (Common Domain Model) は、金融取引のライフサイクルおよび商品構造を標準化するオープンソースモデルです。
CDM の Python SDK (`finos-cdm`) は、Rosetta DSL（モデリング言語）からコードジェネレータ（Rune）を介して自動生成されており、内部データモデルの基盤として **Pydantic v2** および **`rune-runtime`** を採用しています。

### なぜパッチが必要なのか？

`rune-runtime` のメタデータ処理層（`rune.runtime.metadata`）および型バインディング機構には、Pydantic v2 のバリデーションパイプラインとの組み合わせにおいて、以下の課題・エッジケースが存在します：

1. **オプショナルな複合型（ComplexType）フィールドで `None` が渡された時のバリデーションエラー**
2. **基本型メタデータ（`StrWithMeta` 等）のリストに対するシリアライザの適用範囲のズレ（JSON出力時クラッシュ）**
3. **オプショナルな Enum 型フィールドで `None` が渡された時のメタデータ初期化エラー**
4. **クラス継承時における親クラスフィールドの遅延型解決（`NoneType` 縮退）**

これらを完全に解消し、ユーザーが依存関係や個別モデルのハードコーディングを意識することなく利用できるように設計されたパッケージが **`cdm_compat`** です。

---

## 2. `cdm_compat` ライブラリの使い方

### クイックスタート

CDM モデルを利用するスクリプトの冒頭で `import cdm_compat` を実行するだけで、全ランタイムパッチの適用および **FINOS CDM に含まれる全 180+ モデルのスキーマ修復が自動的かつ一括で完了**します。

```python
import cdm_compat
from finos.cdm.event.common.Trade import Trade
from finos.cdm.event.common.TradeIdentifier import TradeIdentifier
from finos.cdm.event.position.Position import Position

# パッチおよび全モデル修復が自動適用済みのため、そのまま通常通りモデル構築・シリアライズ・検証が可能
trade_id = TradeIdentifier(
    assignedIdentifier=[{"identifier": {"@data": "TRADE-001"}, "version": 1}],
    identifierType="UniqueTransactionIdentifier"
)
```

### パッケージ構成

```text
cdm_compat/
├── __init__.py           # パッケージエントリポイント（自動一括修復、公開APIエクスポート）
├── patch_metadata.py     # rune.runtime.metadata に対する低レベルランタイムパッチ
└── rebuild_models.py     # 完全汎用モデル修復エンジン（ゼロ・ハードコーディング）
```

### 公開 API リファレンス

| 関数名 | 引数 | 説明 |
| :--- | :--- | :--- |
| `apply_patches()` | なし | 全メタデータパッチの適用および全CDMモデルの一括修復を実行（冪等）。 |
| `is_patched()` | なし | パッチが既に適用されているか否か（`bool`）を返す。 |
| `rebuild_all_cdm_models()` | なし | `finos._bundle` 内に存在する全 180+ の CDM モデルを動的に検出し、一括修復。 |
| `rebuild_cdm_model(cls, force=True, types_namespace=None)` | `cls: Type[BaseModel]` | 任意のCDMモデルクラスに対して親クラスフィールドの自動復元とPydanticコアスキーマ再構築を実行。 |
| `rebuild_cdm_models(*classes)` | `*classes: Type[BaseModel]` | 複数のモデルクラスを一括再構築。 |
| `sync_parent_fields(cls)` | `cls: Type[BaseModel]` | `cls.__mro__` を探索し、サブクラスで `NoneType` に縮退した親クラスの `model_fields` を自動復元。 |

---

## 3. モデル修復エンジンの汎用化設計（Zero Hardcoding）

### 従来の課題
従来の個別修復では、`PriceQuantity` のような前方参照型や、`Trade` / `TradeIdentifier` などの継承型に対して依存関係の順序（`PriceQuantity` → `TradeLot` → `TradableProduct` → `Trade`）を人間が把握してハードコードする必要がありました。

### 汎用化アーキテクチャの実現
`cdm_compat/rebuild_models.py` では以下の2つの汎用機構により、特定のモデル名に一切依存しない完全な自動修復を実現しています：

1. **`finos._bundle` 型名前空間の自動注入**:
   - Pydantic v2 の `model_rebuild(force=True, _types_namespace=finos._bundle.__dict__)` を活用することで、`PriceQuantity` や `Observable` などの遅延文字列アノテーションを Pydantic が自動的に正しい型に解決します。型名のハードコードは不要です。
2. **MRO 自動走査による親クラスフィールドの復元 (`sync_parent_fields`)**:
   - `Trade` (親: `TradableProduct`), `TradeIdentifier` (親: `Identifier`), `Position` (親: `PositionBase`), `CollateralPosition` (親: `PositionBase`), `MarginCallExposure` (親: `MarginCallBase`) などのあらゆる継承クラスにおいて、親クラスの MRO を動的に探索し、`NoneType` に縮退したフィールドを親から自動同期します。
3. **全モデルの自動検出・一括修復 (`rebuild_all_cdm_models`)**:
   - `finos._bundle` に登録されているすべてのクラスを動的に検査し、1回で全モデルを修復します（全 187 モデルの残存 `NoneType` フィールド数: 0）。

---

## 4. 各パッチの技術的詳細

### パッチ 1: `ComplexTypeMetaDataMixin.deserialize` の `None` ガード

#### 発生するエラー
```text
pydantic_core._pydantic_core.ValidationError: 1 validation error for BusinessDayAdjustments
businessCenters.businessCentersReference
  Expected either <class 'finos.cdm.base.datetime.BusinessCenters.BusinessCenters'> or dict but got <class 'NoneType'>. [type=Input Validation Error, input_value=None, input_type=NoneType]
```

#### 原因
オプショナルな複合型フィールドにデフォルト値 `None` が渡された際、元の `ComplexTypeMetaDataMixin.deserialize` に `obj is None` の判定が存在しないため、`dict` 判定に落ちて検証例外が発生していました。

#### 対策
```python
orig_complex_deserialize = rmeta.ComplexTypeMetaDataMixin.deserialize

@classmethod
def _patched_complex_deserialize(cls, obj, allowed_meta: set[str]):
    if obj is None:
        return None
    return orig_complex_deserialize.__func__(cls, obj, allowed_meta)
```

---

### パッチ 2: `BasicTypeMetaDataMixin` のリストシリアライズ対応

#### 発生するエラー
```text
pydantic_core._pydantic_core.PydanticSerializationError: Error calling function `StrWithMeta.serialise`: 
AttributeError: 'list' object has no attribute 'serialise_meta'
```

#### 原因
`BusinessCenters.businessCenter` などのリスト型フィールド（`list[StrWithMeta]`）において、ジェネレータが単一要素用のシリアライザをリスト全体に付与しているため、`model_dump_json()` 時に `list` オブジェクトに対して `serialise_meta()` を呼び出してクラッシュしていました。

#### 対策
`deserialize` および `serialise` で `obj` が `list` / `tuple` の場合に各要素を再帰処理するよう拡張しました。

---

### パッチ 3: `EnumWithMetaMixin.deserialize` の `None` ガード

#### 発生するエラー
```text
AttributeError: 'NoneType' object has no attribute '_init_meta'
```

#### 原因
Enum 型フィールドが `None` の場合、`model._init_meta(allowed_meta)` で `None._init_meta()` が呼ばれてクラッシュしていました。

#### 対策
```python
@classmethod
def _patched_enum_deserialize(cls, obj, allowed_meta: set[str]):
    if obj is None:
        return None
    return orig_enum_deserialize.__func__(cls, obj, allowed_meta)
```

---

## 5. テストと品質保証

本パッケージには、メタデータパッチ、往復JSONシリアライズ、および汎用モデル修復機能を網羅した単体テストが付属しています。

```powershell
# 単体テストの実行
.\.venv\Scripts\python.exe -m unittest discover tests
```

**テスト項目:**
1. `test_patch_status`: パッチの自動適用と冪等性の検証
2. `test_complex_type_none_handling`: `None` を含む複合型モデルの生成検証
3. `test_basic_type_list_serialization_roundtrip`: `businessCenter` 等の `StrWithMeta` リストの往復検証
4. `test_trade_identifier_creation`: `TradeIdentifier` の UTI バリデーション検証
5. `test_price_quantity_rebuilding`: `PriceQuantity` の数量・価格スケジュール検証
6. `test_trade_roundtrip_validation`: `Trade` オブジェクトの完全な構築および JSON 往復パース検証
7. `test_generic_rebuild_cdm_model`: 任意の継承モデルに対する汎用修復機能の動作検証
