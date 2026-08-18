# Runeランタイム互換性パッチ & `cdm_compat` ライブラリ 詳細解説

本文書は、`finos-cdm` (v6.22.0+ / v7.x) および `rune-runtime` (v2.0.0+) を Python (Pydantic v2) 環境で使用する際に発生する型解決・メタデータシリアライズ・JSONデシリアライズの問題点と、それを解消するために開発された再利用可能ライブラリ **`cdm_compat`** のアーキテクチャ・動作原理について解説します。

> [!NOTE]
> `finos-cdm` v7.1.0 から v6.22.0 へのダウングレードに伴う非互換仕様（`PriceQuantity.quantity` のリスト型化やシリアライズ差分）の詳細については、[CDM_VERSION_DOWNGRADE_6_22.md](file:///e:/dev/python/cdm_workspace/docs/CDM_VERSION_DOWNGRADE_6_22.md) をご参照ください。

---

## 1. 背景とアーキテクチャ

FINOS CDM (Common Domain Model) は、金融取引のライフサイクルおよび商品構造を標準化するオープンソースモデルです。
CDM の Python SDK (`finos-cdm`) は、Rosetta DSL（モデリング言語）からコードジェネレータ（Rune）を介して自動生成されており、内部データモデルの基盤として **Pydantic v2** および **`rune-runtime`** を採用しています。

### なぜパッチが必要なのか？

`rune-runtime` のメタデータ処理層（`rune.runtime.metadata`）および型バインディング機構には、Pydantic v2 のバリデーションパイプラインおよび **Rosetta CDM 公式標準 JSON 仕様（ISDA リファレンスデータ等）** との組み合わせにおいて、以下の課題・エッジケースが存在します：

1. **オプショナルな複合型（ComplexType）フィールドで `None` が渡された時のバリデーションエラー**
2. **基本型メタデータ（`StrWithMeta` 等）のリストに対するシリアライザの適用範囲のズレ（JSON出力時クラッシュ）**
3. **オプショナルな Enum 型フィールドで `None` が渡された時のメタデータ初期化エラー**
4. **クラス継承時における親クラスフィールドの遅延型解決（`NoneType` 縮退）**
5. **Rosetta CDM 公式 JSON（`value` / `meta` / `globalKey` / `globalReference` / `address`）と Rune 内部形式（`@data` / `@key` / `@ref`）のスキーマ不一致による `KeyError` およびバリデーション失敗**
6. **複合型における `FieldWithMeta` エンベロープ（`{"value": {...fields...}, "meta": {...}}`）構造による Pydantic 型不一致**

これらを完全に解消し、ユーザーが内部の形式差異や個別モデルのハードコーディングを意識することなく利用できるように設計されたパッケージが **`cdm_compat`** です。

---

## 2. `cdm_compat` ライブラリの使い方

### クイックスタート

CDM モデルを利用するスクリプトの冒頭で `import cdm_compat` を実行するだけで、全ランタイムパッチの適用および **FINOS CDM に含まれる全 180+ モデルのスキーマ修復が自動的かつ一括で完了**します。

```python
import cdm_compat
from finos.cdm.event.common.Trade import Trade
from finos.cdm.event.common.TradeState import TradeState

# 1. Rune 形式・Rosetta 公式 JSON 形式のいずれも自動認識・デシリアライズ可能
trade_state = TradeState.model_validate_json(raw_json_data)

# 2. モデル構築とシリアライズ
print(f"Trade Date: {trade_state.trade.tradeDate}")
json_output = trade_state.model_dump_json(indent=2, exclude_none=True)
```

### パッケージ構成

```text
cdm_compat/
├── __init__.py           # パッケージエントリポイント（自動一括修復、公開APIエクスポート）
├── patch_metadata.py     # rune.runtime.metadata / BaseDataClass に対する低レベルランタイムパッチ
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
`cdm_compat/rebuild_models.py` では以下の3つの汎用機構により、特定のモデル名に一切依存しない完全な自動修復を実現しています：

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
`obj is None` のガード節を追加し、安全に `None` を返却するよう修復しました。

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
`obj is None` のガード節を追加し、安全に `None` を返却するよう修復しました。

---

### パッチ 4: Rosetta CDM 標準 JSON（`value` / `meta`）と Rune ランタイム形式の双方向互換対応

#### 発生するエラー
```text
KeyError: '@data'
Value error, Allowed meta {'@key', '@key:external'} differs from the currently existing meta slots: {'@globalKey'}
```

#### 原因
Rune ランタイムの `deserialize` は内部的に `{"@data": "..."}` や `{"@key": "..."}` を前提としていますが、ISDA / FINOS CDM 公式の標準 JSON（Rosetta JSON）では基本型や Enum が `{"value": "...", "meta": {"globalKey": "..."}}` の構造を持ちます。
また、`@data` をメタデータとしてスロットに登録してしまい、スロット制限チェック（`_init_meta`）でバリデーションエラーが発生していました。

#### 対策
1. **メタデータスロットの正規化 (`_normalize_rosetta_meta`)**:
   - `globalKey` → `@key`
   - `externalKey` → `@key:external`
   - `location` → `@key:scoped`
   - `scheme` → `@scheme`
   - `@data`（データ本体）をメタデータ辞書から除外。
2. **参照タグの透過抽出 (`_extract_rosetta_ref`)**:
   - `globalReference`, `externalReference`, `address`（Scoped Reference）を検出し、Rune の `UnresolvedReference` へ自動マッピング。
3. `BasicTypeMetaDataMixin` / `EnumWithMetaMixin` において、`@data` と `value` の両方を値として透過的に抽出・格納。

---

### パッチ 5: 複合型（ComplexType）における `FieldWithMeta` エンベロープの自動アンラップ

#### 発生するエラー
```text
pydantic_core._pydantic_core.ValidationError: 4 validation errors for finos_cdm_event_common_TradeState
trade.tradeLot.0.priceQuantity.0.quantity.0.value
  Decimal input should be an integer, float, string or Decimal object [type=decimal_type, input_value={'value': 50000000.0, 'unit': ...}]
```

#### 原因
Rosetta CDM JSON では、複合型オブジェクト（`NonNegativeQuantitySchedule`, `PriceSchedule`, `Observable` 等）にメタデータが付与される際、`{"value": {...actual fields...}, "meta": {...}}` というエンベロープ（ラッパー）で表現されます。
一方、Python の `finos-cdm` モデルでは複合型自身が `ComplexTypeMetaDataMixin` を継承してフィールドとメタデータを直接保持するため、Pydantic がエンベロープの `value`（辞書）をモデルのフィールド `value: Decimal` に割り当てようとして型検証エラーとなっていました。

#### 対策
`BaseDataClass._deserialize_refs` および `ComplexTypeMetaDataMixin.deserialize` において、データが `{"value": dict, "meta": ...}` の構造を持つ場合に内部のフィールド辞書を展開（アンラップ）し、メタデータを付与した上で Pydantic バリデーションに渡す機構を追加しました。

---

### パッチ 6: Rosetta 生成関数の型解決パッチ (`patch_rosetta_function_types`)

#### 発生するエラー
```text
NameError: name 'finos_cdm_product_template_EconomicTerms' is not defined
```

#### 原因
Rosetta DSL から Python コードを自動生成する際、`finos.cdm.product.qualification.functions.*` 内の関数引数型アノテーション（例: `economicTerms: finos_cdm_product_template_EconomicTerms`）で参照されている内部クラス名がモジュール内でインポートされていません。
Pydantic の `@validate_call` デコレータが型ヒントを動的評価する際に `NameError` が発生し、関数のインポート自体が失敗していました。

#### 対策
`cdm_compat.patch_functions.patch_rosetta_function_types` により、`finos._bundle` に登録されている全 CDM モデル名を `builtins` に安全に注入し、Pydantic の型ヒント解決がグローバルスコープで成功するように修復しました。

---

### パッチ 7: `rune.runtime.utils.rune_all_elements` のスカラー比較パッチ (`patch_rune_all_elements`)

#### 発生するエラー
```text
# 2レグあるスワップで Qualify_AssetClass_InterestRate が False になる
Qualify_AssetClass_InterestRate(economicTerms) -> False
```

#### 原因
`rune-runtime` の `rune_all_elements(lhs, op, rhs)` は、2つのリストの長さが完全一致することを前提とした実装になっていました：
```python
# rune-runtime 元の実装
def rune_all_elements(lhs, op, rhs) -> bool:
    cmp = _cmp[op]
    op1 = _to_list(lhs)
    op2 = _to_list(rhs)
    return all(cmp(el1, el2) for el1, el2 in zip(op1, op2)) if len(op1) == len(op2) else False
```
DSL が「リストの全要素が `True` か」を判定するために `rune_all_elements([True, True], "=", True)` を呼び出すと、`rhs` 側の長さが 1 であるため `len(op1) == len(op2)` が `False` となり、常に `False` が返ってしまう重大な不具合が存在していました。

#### 対策
`rhs` がスカラー値の場合には、`lhs` のすべての要素に対して `cmp(el, rhs)` をブロードキャスト評価するようにパッチを適用しました。

---

### パッチ 8: `FuncProxy.__call__` の `raw_function` 優先実行パッチ (`patch_func_proxy_call`)

#### 発生するエラー
```text
pydantic_core._pydantic_core.ValidationError: Allowed meta {'@ref:scoped'} differs from existing meta slots: {'@key:scoped'}
```

#### 原因
Rosetta 生成関数は `@replaceable`（`FuncProxy`）と `@validate_call` で装飾されています。`cdm_compat.resolve_model_references` で参照解決済みのモデルオブジェクトを渡すと、`@validate_call` が引数を再バリデーションする際に内部メタデータスロットの不一致エラーを引き起こしていました。

#### 対策
`FuncProxy.__call__` において、`self._func` の `@validate_call` ラッパーの下にある `raw_function`（素の Python 関数）を直接呼び出すようにパッチし、再バリデーションのオーバーヘッドとメタデータ衝突をバイパスして安全かつ高速に判定関数を実行可能にしました。

---

## 5. テストと品質保証

本パッケージには、メタデータパッチ、往復JSONシリアライズ、汎用モデル修復、Rosetta関数実行、および公式 IRS サンプル JSON（`ird-ex01-vanilla-swap.json`）の商品判定を網羅した自動テストスイートが付属しています。

```powershell
# 全テストスイートの実行（全30テスト）
.venv\Scripts\python.exe -m pytest -v
```

**テスト項目（抜粋）:**
1. `test_patch_status`: パッチの自動適用と冪等性の検証
2. `test_complex_type_none_handling`: `None` を含む複合型モデルの生成検証
3. `test_basic_type_list_serialization_roundtrip`: `businessCenter` 等の `StrWithMeta` リストの往復検証
4. `test_trade_identifier_creation`: `TradeIdentifier` の UTI バリデーション検証
5. `test_price_quantity_rebuilding`: `PriceQuantity` の数量・価格スケジュール検証
6. `test_trade_roundtrip_validation`: `Trade` オブジェクトの完全な構築および JSON 往復パース検証
7. `test_generic_rebuild_cdm_model`: 任意の継承モデルに対する汎用修復機能の動作検証
8. `test_deserialize_trade_state_from_file`: `ird-ex01-vanilla-swap.json` ファイルからの完全デシリアライズ検証
9. `test_function_patches_and_qualification_function_execution`: Rosetta 関数型解決および `rune_all_elements` パッチの検証
10. `test_qualify_vanilla_swap_from_file`: `ird-ex01-vanilla-swap.json` を入力したバニラ固定/変動金利スワップ判定の完全検証
11. `test_qualify_created_irs_trade_ois`: JPY TONA OIS スワップの判定検証
12. `test_is_vanilla_fixed_float_swap_helper`: 簡易判定ヘルパー関数の検証

