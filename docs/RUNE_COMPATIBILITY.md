# Runeランタイム互換性パッチ & `cdm_compat` ライブラリ 詳細解説

本文書は、`finos-cdm` (v6.x / v6.22.0+ / v6.99.99+ / v7.x) および `rune-runtime` (v2.0.0+ / v2.2.0+) を Python (Pydantic v2) 環境で使用する際に発生する型解決・メタデータシリアライズ・JSONデシリアライズ・Rosetta DSL 関数実行の問題点と、それを解消するために開発された再利用可能ライブラリ **`cdm_compat`** のアーキテクチャ・設定管理・動作原理について解説します。

> [!NOTE]
> `finos-cdm` v7.1.0 から v6 系列への仕様差分（`PriceQuantity.quantity` のリスト型化やシリアライズ差分）の詳細については、[CDM_VERSION_DOWNGRADE_6_22.md](file:///e:/dev/python/cdm_workspace/docs/CDM_VERSION_DOWNGRADE_6_22.md) をご参照ください。

---

## 1. 背景とアーキテクチャ

FINOS CDM (Common Domain Model) は、金融取引のライフサイクルおよび商品構造を標準化するオープンソースモデルです。
CDM の Python SDK (`finos-cdm`) は、Rosetta DSL（モデリング言語）からコードジェネレータ（`rune-python-generator`）を介して自動生成されており、内部データモデルの基盤として **Pydantic v2** および **`rune-runtime`** を採用しています。

### なぜパッチが必要なのか？

`rune-runtime` のメタデータ処理層（`rune.runtime.metadata`）、型バインディング機構、および Rosetta DSL 生成コードには、Pydantic v2 のバリデーションパイプラインや **Rosetta CDM 公式標準 JSON 仕様（ISDA リファレンスデータ等）** との組み合わせにおいて、以下の課題・エッジケースが存在します：

1. **オプショナルな複合型（ComplexType）フィールドで `None` が渡された時のバリデーションエラー**
2. **基本型メタデータ（`StrWithMeta` 等）のリストに対するシリアライザの適用範囲のズレ（JSON出力時クラッシュ）**
3. **オプショナルな Enum 型フィールドで `None` が渡された時のメタデータ初期化エラー**
4. **Rosetta CDM 公式 JSON（`value` / `meta` / `globalKey` / `globalReference` / `externalReference` / `address`）と Rune 内部形式（`@data` / `@key` / `@ref`）のスキーマ不一致による `KeyError` およびバリデーション失敗**
5. **複合型における `FieldWithMeta` エンベロープ（`{"value": {...fields...}, "meta": {...}}`）構造による Pydantic 型不一致**
6. **多態 JSON（`@type: "cdm.product.asset.InterestRatePayout"`）が Choice / Union ラッパー型（`Payout` 等）に渡された際のマッピング失敗（`None` 化）**
7. **Rosetta 生成関数実行時の未インポートシンボル（関数・Enum・モデル）による `NameError`**（例: `ConvertPeriodToNumberOfDays`, `PeriodEnum`）
8. **Rosetta 生成コードにおける異なる Enum 型インスタンスのキャスト失敗および `None` 渡しエラー**（例: `PeriodEnum(PeriodExtendedEnum.M)`, `PeriodEnum(None)`）
9. **Rune ネイティブ関数（`AddDays`, `DateDifference`, `LeapYearDateDifference` 等）の実装未登録による `NotImplementedError`**
10. **`rune_all_elements` のスカラー RHS 比較バグ**（2レグスワップの商品判定で常に `False` を返す）
11. **`finos._bundle` 外で独立定義された standalone モデル（`InterestRateIndex` 等）のスキーマ未同期**

これらを完全に解消し、ユーザーが内部の形式差異や個別モデルのハードコーディングを意識することなく利用できるように設計されたパッケージが **`cdm_compat`** です。

---

## 2. PR #265（Issue #259）の影響と不要化されたパッチ

[finos/rune-python-generator#265](https://github.com/finos/rune-python-generator/pull/265) において、循環参照モデルに対する **3段階（Phase）生成メカニズム** がジェネレータに導入されました：

- **Phase 1 (Class Definition)**: クラス定義時は一時的に `field: None = Field(None, ...)` を出力。
- **Phase 2 (Delayed Annotation Updates)**: 全クラス定義後、`_bundle.py` 末尾で `cls.model_fields["field"].annotation = ActualType` を代入してアノテーションを上書き。
- **Phase 3 (Topological Rebuild)**: 依存関係グラフ（DAG）順に `cls.model_rebuild(force=True)` を `_bundle.py` 末尾で自動実行。

### 判定と整理

| 従来のパッチ | PR #265 以前の役割 | 現在の状態と判定 |
| :--- | :--- | :--- |
| **`sync_parent_fields`** | MROを走査して `NoneType` に退化したフィールドを親から手動復元 | 🟢 **不要 (OBSOLETE) / デフォルト: `false`**<br/>Phase 2 でジェネレータが直接アノテーションを上書きするため通常運用では不要。 |
| **`rebuild_all_bundle_models`** | `_bundle.py` 内の全 300+ クラスを手動走査して一括リビルド | 🟢 **不要 (OBSOLETE) / デフォルト: `false`**<br/>Phase 3 でトポロジカルソート順に自動再構築されるため手動全件走査は不要。 |
| **`rebuild_standalone_models`** | `_bundle` 外の standalone モデル（`InterestRateIndex` 等）のリビルド | 🔴 **必須 (REQUIRED) / デフォルト: `true`**<br/>`_bundle` 外のクラスは Phase 3 の自動再構築リストに含まれないため、これらのみを軽量にリビルド。 |

---

## 3. `cdm_compat` ライブラリの使い方

### クイックスタート

CDM モデルを利用するスクリプトの冒頭で `import cdm_compat` を実行するだけで、設定ファイル（`cdm_compat.json`）またはデフォルト推奨値に基づき、全ランタイムパッチが自動適用されます。

```python
import cdm_compat
from finos.cdm.event.common.Trade import Trade
from finos.cdm.event.common.TradeState import TradeState

# 1. Rune 形式・Rosetta 公式 JSON 形式のいずれも自動認識・デシリアライズ可能
trade_state = TradeState.model_validate_json(raw_json_data)

# 2. 参照ポインタの双方向解決（UnresolvedReference -> 実体オブジェクト）
trade_state = cdm_compat.resolve_model_references(trade_state)

# 3. モデル構築と安全な JSON シリアライズ（循環参照・メタデータスロット自動保護）
json_output = trade_state.model_dump_json(indent=2, exclude_none=True)
```

---

## 4. 個別オン/オフ設定機能 (`cdm_compat.json` / `config.py`)

各パッチを個別にオン/オフ切り替えできるように、柔軟な設定管理レイヤーを提供しています。

### 設定ファイル (`cdm_compat.json`)
プロジェクトルートに配置します：

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "description": "Configuration for cdm_compat runtime monkey patches and utilities",
  "patch_rune_all_elements": true,
  "patch_metadata_mixins": true,
  "patch_rosetta_function_types": true,
  "patch_func_proxy_call": true,
  "rebuild_standalone_models": true,
  "sync_parent_fields": false,
  "rebuild_all_bundle_models": false
}
```

### 設定読み込みの優先順位
1. **明示的なコード指定**: `cdm_compat.configure(...)` または `apply_patches(config=...)`
2. **環境変数（パス指定）**: `CDM_COMPAT_CONFIG=/path/to/custom_config.json`
3. **環境変数（個別フラグ）**: `CDM_COMPAT_PATCH_RUNE_ALL_ELEMENTS=0` / `1`
4. **設定ファイル**: プロジェクトルートまたはカレントディレクトリの `cdm_compat.json`
5. **デフォルト設定**: 推奨デフォルト値

### 動的な設定変更 (Python API)
```python
import cdm_compat

# パッチ設定を動的に変更して再適用
cdm_compat.configure(
    patch_rune_all_elements=True,
    sync_parent_fields=False,
    rebuild_standalone_models=True
)

# 現在の設定を取得
config = cdm_compat.get_config()
print("Rune all elements patch:", config.patch_rune_all_elements)
```

---

## 5. パッケージ構成 & 公開 API リファレンス

```text
cdm_compat/
├── __init__.py           # パッケージエントリポイント（自動一括初期化、公開APIエクスポート）
├── config.py             # 設定管理レイヤー（CdmCompatConfig、優先順位ハンドラ）
├── patch_functions.py     # Rune関数・Rosettaシンボル遅延解決・ネイティブ関数登録
├── patch_metadata.py      # rune.runtime.metadata / BaseDataClass 低レベルメタデータパッチ
└── rebuild_models.py      # Standalone モデル再構築 & レガシーリビルドエンジン
```

### 公開 API リファレンス

| 関数 / クラス | 引数 | 説明 |
| :--- | :--- | :--- |
| `apply_patches(config=None)` | `config: Optional[CdmCompatConfig]` | 設定に基づきメタデータパッチ、関数パッチ、モデル再構築を実行（冪等）。 |
| `configure(config_path=None, **kwargs)` | `**kwargs` | 設定ファイルを読み込むか、キーワード引数でパッチを動的設定して再適用。 |
| `get_config()` | なし | 現在有効な `CdmCompatConfig` インスタンスを取得。 |
| `load_config(path=None)` | `path: Optional[Path | str]` | 設定ファイルや環境変数から設定をロードして返却。 |
| `is_patched()` | なし | パッチが既に適用されているか否か（`bool`）を返す。 |
| `reset_patches()` | なし | パッチの適用状態をリセット（テスト用）。 |
| `resolve_model_references(root_obj)` | `root_obj: BaseModel` | モデル内の `UnresolvedReference` を実体オブジェクトへ再帰的に解決・バインド。 |
| `rebuild_standalone_models()` | なし | `finos._bundle` 外の standalone モデル（`InterestRateIndex` 等）を軽量に再構築。 |
| `rebuild_cdm_model(cls, force=True, ...)` | `cls: Type[BaseModel]` | 任意の CDM モデルに対してスキーマ再構築を実行。 |
| `rebuild_all_cdm_models()` | なし | レガシー用: `finos._bundle` 内の全 300+ モデルを一括走査して再構築。 |

---

## 6. 各パッチの技術的詳細

### パッチ 1: `ComplexTypeMetaDataMixin.deserialize` の `None` ガード

#### 発生するエラー
```text
pydantic_core._pydantic_core.ValidationError: 1 validation error for BusinessDayAdjustments
businessCenters.businessCentersReference
  Expected either <class 'finos.cdm.base.datetime.BusinessCenters.BusinessCenters'> or dict but got <class 'NoneType'>. [type=Input Validation Error, input_value=None, input_type=NoneType]
```

#### 対策
オプショナルな複合型フィールドに `None` が渡された際、元の `ComplexTypeMetaDataMixin.deserialize` に `obj is None` の判定が存在しないため、`dict` 判定に落ちて検証例外が発生していました。ガード節を追加し、安全に `None` を返却するよう修復しました。

---

### パッチ 2: `BasicTypeMetaDataMixin` のリストシリアライズ対応

#### 発生するエラー
```text
pydantic_core._pydantic_core.PydanticSerializationError: Error calling function `StrWithMeta.serialise`: 
AttributeError: 'list' object has no attribute 'serialise_meta'
```

#### 対策
`BusinessCenters.businessCenter` などのリスト型フィールド（`list[StrWithMeta]`）において、ジェネレータが単一要素用のシリアライザをリスト全体に付与しているためクラッシュしていました。`deserialize` および `serialise` で `obj` が `list` / `tuple` の場合に各要素を再帰処理するよう拡張しました。

---

### パッチ 3: Rosetta CDM 標準 JSON（`value` / `meta`）と Rune 形式の双方向互換対応

#### 発生するエラー
```text
KeyError: '@data'
Value error, Allowed meta {'@key', '@key:external'} differs from the currently existing meta slots: {'@globalKey'}
```

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

### パッチ 4: 複合型（ComplexType）における `FieldWithMeta` エンベロープの自動アンラップ

#### 発生するエラー
```text
pydantic_core._pydantic_core.ValidationError: 4 validation errors for finos_cdm_event_common_TradeState
trade.tradeLot.0.priceQuantity.0.quantity.0.value
  Decimal input should be an integer, float, string or Decimal object [type=decimal_type, input_value={'value': 50000000.0, 'unit': ...}]
```

#### 対策
Rosetta CDM JSON では複合型オブジェクトにメタデータが付与される際、`{"value": {...actual fields...}, "meta": {...}}` というエンベロープ（ラッパー）で表現されます。`BaseDataClass._deserialize_refs` および `ComplexTypeMetaDataMixin.deserialize` において、データが `{"value": dict, "meta": ...}` の構造を持つ場合に内部のフィールド辞書を展開（アンラップ）し、メタデータを付与した上で Pydantic バリデーションに渡す機構を追加しました。

---

### パッチ 5: Rosetta DSL 関数・Enum・モデルの遅延シンボル解決 (`patch_rosetta_function_types`)

#### 発生するエラー
```text
NameError: name 'ConvertPeriodToNumberOfDays' is not defined
NameError: name 'PeriodEnum' is not defined
ValueError: <PeriodExtendedEnum.M: 'M'> is not a valid PeriodEnum
```

#### 対策
1. **`_LazyRosettaSymbol` によるオンデマンド解決**:
   - `finos.cdm` 配下の全 2,300+ シンボル（関数・Enum・モデル）を検出し、`builtins` に遅延ローダープロキシとして登録。コード生成時にインポートが欠落しているシンボルが呼び出された瞬間に自動ロードして実行。
2. **柔軟な Enum 型変換 (`_patch_enum_cross_instantiation`)**:
   - Rosetta 生成コードが `PeriodEnum(PeriodExtendedEnum.M)` のように異なる Enum 型インスタンスを渡してキャストを試みた際、`.value` を自動展開して正しくマッチング。

---

### パッチ 6: Rosetta 組み込みネイティブ関数の自動登録

#### 発生するエラー
```text
NotImplementedError: Function cdm.base.datetime.functions.AddDays doesn't have an implementation! Available: <none>
NotImplementedError: Function cdm.base.datetime.functions.LeapYearDateDifference doesn't have an implementation!
```

#### 対策
Rune の `native_registry` に対し、標準的な日付計算・数学ネイティブ関数（`AddDays`, `DateDifference`, `LeapYearDateDifference`, `RoundToPrecision`, `Today`, `Now`）の実装を組み込みで登録し、日付演算やクオリフィケーション関数が追加設定なしで高速動作するようにしました。

---

### パッチ 7: `rune.runtime.utils.rune_all_elements` のスカラー比較パッチ (`patch_rune_all_elements`)

#### 発生するエラー
```text
# 2レグあるスワップで Qualify_AssetClass_InterestRate が False になる
Qualify_AssetClass_InterestRate(economicTerms) -> False
```

#### 対策
`rune-runtime` の `rune_all_elements(lhs, op, rhs)` は `len(lhs) == len(rhs)` を前提としており、スカラー RHS（`[True, True] == True`）の比較で常に `False` を返すバグがありました。`rhs` がスカラー値の場合には `lhs` の全要素に対して `cmp(el, rhs)` をブロードキャスト評価するように修正しました。

---

### パッチ 8: `FuncProxy.__call__` の `raw_function` 優先実行パッチ (`patch_func_proxy_call`)

#### 発生するエラー
```text
pydantic_core._pydantic_core.ValidationError: Allowed meta {'@ref:scoped'} differs from existing meta slots: {'@key:scoped'}
```

#### 対策
Rosetta 生成関数は `@replaceable`（`FuncProxy`）と `@validate_call` で装飾されています。`resolve_model_references` 解決済みのモデルオブジェクトを渡した際、`@validate_call` の再バリデーションによるメタデータスロット衝突を回避するため、素の Python 関数（`raw_function`）を直接呼び出すように最適化しました。

---

## 7. テストと品質保証

本パッケージには、設定管理、メタデータパッチ、往復 JSON シリアライズ、Standalone モデル再構築、Rosetta 関数実行、および公式 IRS サンプル JSON（`ird-ex01-vanilla-swap.json`）の商品判定を網羅した自動テストスイートが付属しています。

```powershell
# 全テストスイートの実行（全33テスト）
.venv\Scripts\python.exe -m pytest -v

# AI Agent Harness による一括環境診断 & 検証
.venv\Scripts\python.exe -m cdm_workspace.harness doctor
.venv\Scripts\python.exe -m cdm_workspace.harness verify
```

**テスト項目一覧:**
1. `test_patch_status`: パッチの自動適用と冪等性の検証
2. `test_config_loading_and_defaults`: `cdm_compat.json` 設定読み込みとデフォルト値の検証
3. `test_config_env_override`: 環境変数による個別パッチ設定オーバーライドの検証
4. `test_standalone_model_validation`: `InterestRateIndex` standalone モデルのバリデーション検証
5. `test_complex_type_none_handling`: `None` を含む複合型モデルの生成検証
6. `test_basic_type_list_serialization_roundtrip`: `businessCenter` 等の `StrWithMeta` リストの往復検証
7. `test_trade_identifier_creation`: `TradeIdentifier` の UTI バリデーション検証
8. `test_price_quantity_rebuilding`: `PriceQuantity` の数量・価格スケジュール検証
9. `test_trade_roundtrip_validation`: `Trade` オブジェクトの完全な構築および JSON 往復パース検証
10. `test_generic_rebuild_cdm_model`: 任意の継承モデルに対する汎用修復機能の動作検証
11. `test_rosetta_reference_resolution_and_roundtrip`: 参照解決および JSON ラウンドトリップの完全検証
12. `test_function_patches_and_qualification_function_execution`: Rosetta 関数型解決、Enumキャスト、ネイティブ関数実行、および `rune_all_elements` パッチの検証
13. `test_qualify_vanilla_swap_from_file`: `ird-ex01-vanilla-swap.json` を入力したバニラ固定/変動金利スワップ判定の完全検証
14. `test_qualify_created_irs_trade_ois`: JPY TONA OIS スワップの判定検証
15. `test_is_vanilla_fixed_float_swap_helper`: 簡易判定ヘルパー関数の検証
