# FINOS CDM v7.1.0 から v6.22.0 へのダウングレード対応と非互換仕様ガイド

本文書は、`finos-cdm` パッケージのバージョンを **7.1.0 から 6.22.0 にダウングレード**した際に発生した問題点、**重大な非互換仕様（Breaking Changes）**、および `cdm_compat` 互換レイヤーにおける改修内容を詳細に記録したドキュメントです。

---

## 1. 概要と背景

`finos-cdm` は Rosetta DSL から自動生成された Python パッケージであり、バージョン間（v6.x 系と v7.x 系）で Rosetta スキーマ定義や生成される Pydantic v2 / Rune ランタイムのアノテーション構造に一部破壊的変更が存在します。

v7.1.0 から v6.22.0 へのダウングレードに伴い、モデルの多重度（Cardinality）定義や `rune-runtime` のメタデータシリアライズ処理において実行時エラーおよび検証エラーが発生しました。本ワークスペースでは、**`cdm_compat` 互換レイヤーのパッチ拡張**および **ドメイン生成コードの型調整** を行うことで、v6.22.0 環境において全単体テストをパスさせ、安定動作を確立しました。

---

## 2. ⚠️ 重大な非互換仕様と注意点（Breaking Differences）

### ① `PriceQuantity.quantity` の多重度（Cardinality）がリスト型（`list`）

> [!CAUTION]
> **最重要の非互換点**: `PriceQuantity` における `quantity` の型定義が異なります。

* **v7.1.0**: `quantity` フィールドが単一インスタンス（スカラー型）または単一参照として扱われる場合があった。
* **v6.22.0**: `quantity` フィールドは **`Optional[list[NonNegativeQuantitySchedule | None]]` （リスト型）** として定義されています。

#### 発生するエラー（旧コードをそのまま実行した場合）
単一の `NonNegativeQuantitySchedule` インスタンスを `quantity=notional_quantity` として渡すと、Pydantic v2 がモデル内部のイテレータを走査して `(field_name, field_value)` のタプルとして展開しようとし、以下の検証例外が発生します：

```text
pydantic_core._pydantic_core.ValidationError: 5 validation errors for finos_cdm_observable_asset_PriceQuantity
quantity.0
  Input should be a valid dictionary or instance of NonNegativeQuantitySchedule [type=model_type, input_value=('value', Decimal('1000000000')), input_type=tuple]
quantity.1
  Input should be a valid dictionary or instance of NonNegativeQuantitySchedule [type=model_type, input_value=('unit', UnitType(...)), input_type=tuple]
```

#### 必須の修正対応
```python
# ❌ 旧コード (v7.1.0 で動作していた形式)
price_quantity = PriceQuantity(quantity=notional_quantity, price=[price])

# ✅ v6.22.0 対応コード (リストとして渡す)
price_quantity = PriceQuantity(quantity=[notional_quantity], price=[price])

# 参照時のアクセス
# ❌ notional = trade.tradeLot[0].priceQuantity[0].quantity.value
# ✅ notional = trade.tradeLot[0].priceQuantity[0].quantity[0].value
```

---

### ② `EnumWithMetaMixin` におけるリスト型フィールドの JSON シリアライズ破損

> [!WARNING]
> **Rune ランタイムの不具合**: `rune.runtime.metadata.EnumWithMetaMixin.serialise` がリスト型 Enum フィールドに対応していない。

* **原因**:
  `BusinessCenters.businessCenter` などのフィールドは `list[BusinessCenterEnum]` 型です。
  しかし、Rosetta 生成コードはフィールド全体に対して `WrapSerializer(EnumWithMetaMixin.serialise)` をアノテーションします。
  Rune 2.x の元の `EnumWithMetaMixin.serialise` は引数 `obj` が単一の `_EnumWrapper` であることのみを想定しており、`obj.serialise_meta()` を直呼びするため、リストが渡されるとクラッシュします。

#### 発生するエラー
```text
pydantic_core._pydantic_core.PydanticSerializationError: Error calling function `serialise`: 
AttributeError: 'list' object has no attribute 'serialise_meta'
```

#### `cdm_compat` による自動修復
`cdm_compat.patch_metadata` において、`EnumWithMetaMixin.serialise` および `deserialize` を再帰処理対応に拡張しました：
* `obj is None` の場合: `None` を返却
* `isinstance(obj, (list, tuple))` の場合: 各要素に対して再帰的にシリアライズ/デシリアライズを実行
* 単一の `_EnumWrapper` / `Enum` の場合: `@data` メタデータを付与してシリアライズ

---

### ③ `EnumWithMetaMixin.serializer` の戻り値型警告（`return_type=Any`）

> [!NOTE]
> Rune 2.x では `WrapSerializer` の戻り値型に `return_type=dict` がハードコードされていました。
> フィールドがリスト（`list[dict]`）を返すと、Pydantic v2 が `PydanticSerializationUnexpectedValue` 警告を出力します。

#### `cdm_compat` による対策
`EnumWithMetaMixin.serializer` および `ComplexTypeMetaDataMixin.serializer` の `return_type` を `Any` に書き換えるパッチを適用し、警告を完全に抑止しました。

---

### ④ テスト実行・インポート順序（`conftest.py` での `cdm_compat` 先行初期化）

> [!IMPORTANT]
> `finos.cdm.*` のいずれかのモジュールがインポートされる前に、必ず `import cdm_compat` が実行されていなければなりません。

* **理由**:
  モジュールインポート時にクラスアノテーション内の `validator(...)` や `serializer()` が評価され、Pydantic / Rune のキャッシュに登録されます。
  `cdm_compat` が後からインポートされると、一部の Enum や複合型のキャッシュにパッチ前の関数が残り、`AttributeError: 'NoneType' object has no attribute '_init_meta'` が発生します。

#### 対策
`tests/conftest.py` の最上部で `import cdm_compat` を実行することで、全 pytest テストスイートでパッチが先行適用されるよう保証しました。

---

## 3. 変更・改修ファイル一覧

| ファイル | 区分 | 改修内容 |
| :--- | :--- | :--- |
| [`src/cdm_compat/patch_metadata.py`](file:///e:/dev/python/cdm_workspace/src/cdm_compat/patch_metadata.py) | **互換レイヤー** | `EnumWithMetaMixin` および `ComplexTypeMetaDataMixin` に再帰的リスト処理、`None` ガード、`return_type=Any` パッチを追加。 |
| [`src/cdm_compat/__init__.py`](file:///e:/dev/python/cdm_workspace/src/cdm_compat/__init__.py) | **互換レイヤー** | ドキュメント・対応バージョン表記を `v6.22.0+ / v7.x` に更新。 |
| [`src/cdm_workspace/create_irs_trade.py`](file:///e:/dev/python/cdm_workspace/src/cdm_workspace/create_irs_trade.py) | **ドメイン生成** | `TradeLot.priceQuantity[0]` 内の `PriceQuantity(quantity=[notional_quantity])` をリスト形式に修正。 |
| [`tests/cdm_compat/test_cdm_compat.py`](file:///e:/dev/python/cdm_workspace/tests/cdm_compat/test_cdm_compat.py) | **単体テスト** | `PriceQuantity.quantity` のリストアサーション（`quantity[0].value`）およびメタデータ往復テストの更新。 |
| [`tests/cdm_workspace/test_create_irs_trade.py`](file:///e:/dev/python/cdm_workspace/tests/cdm_workspace/test_create_irs_trade.py) | **単体テスト** | `create_irs_trade` の `quantity[0]` リストアクセス修正および `import cdm_compat` 先行インポートの追加。 |
| [`tests/conftest.py`](file:///e:/dev/python/cdm_workspace/tests/conftest.py) | **テスト基盤** | 全体フィクスチャで `import cdm_compat` を先行インポート。 |
| [`tests/cdm_workspace/test_harness.py`](file:///e:/dev/python/cdm_workspace/tests/cdm_workspace/test_harness.py) | **ハーネステスト** | `import cdm_compat` の明示的インポートを追加。 |
| [`pyproject.toml`](file:///e:/dev/python/cdm_workspace/pyproject.toml) | **プロジェクト設定** | `finos-cdm>=6.22.0`, `rune-runtime>=2.0.0`, `pydantic>=2.10.3` に更新。 |

---

## 4. 動作検証結果

Virtual Environment 内の Python インタプリタ (`.venv\Scripts\python.exe`) を使用し、全テストスイートの正常動作を確認済みです。

```powershell
# テスト実行コマンド
.\.venv\Scripts\python.exe -m pytest -v
```

```text
============================= test session starts =============================
platform win32 -- Python 3.13.2, pytest-9.1.1, pluggy-1.6.0
rootdir: E:\dev\python\cdm_workspace
configfile: pyproject.toml
testpaths: tests
collected 19 items

tests\cdm_compat\test_cdm_compat.py .......                              [ 36%]
tests\cdm_workspace\test_create_irs_trade.py .....                       [ 63%]
tests\cdm_workspace\test_harness.py .......                              [100%]

============================= 19 passed in 7.93s ==============================
```

```powershell
# ハーネス診断
.\.venv\Scripts\python.exe -m cdm_workspace.harness doctor
# => Overall Status: HEALTHY - All checks passed
```

---

## 5. 🔮 将来 FINOS CDM v7 系列へ再移行する際の移行容易性と手順

本ワークスペースにおける非互換対応の設計により、**将来 `finos-cdm` を v7 系列（7.1.0 等）に戻す際の作業は極めて限定的かつ容易**です。

### 互換性の維持（戻す必要のない部分）
* **`cdm_compat` 互換レイヤーのパッチ**:
  `patch_metadata.py`（`EnumWithMetaMixin` / `ComplexTypeMetaDataMixin` の再帰リスト処理や `return_type=Any`）および `rebuild_models.py`（MRO 継承フィールド復元）は、**v7 系列でもそのまま完全互換で安全に動作**します。巻き戻しや削除は不要です。
* **`conftest.py` の先行初期化**:
  `cdm_compat` の先行インポート構造も v7 系列でそのまま有効です。

### 再移行時に唯一修正が必要な箇所
Rosetta モデルスキーマの多重度差分に起因する修正は **`PriceQuantity.quantity` のみ** です。

| 対象ファイル | v6.22.0（現在） | v7 系列に戻す場合 |
| :--- | :--- | :--- |
| [`src/cdm_workspace/create_irs_trade.py`](file:///e:/dev/python/cdm_workspace/src/cdm_workspace/create_irs_trade.py) | `PriceQuantity(quantity=[notional_quantity])` | `PriceQuantity(quantity=notional_quantity)` |
| [`tests/cdm_compat/test_cdm_compat.py`](file:///e:/dev/python/cdm_workspace/tests/cdm_compat/test_cdm_compat.py) | `PriceQuantity(quantity=[quantity])`<br>`assert reloaded.quantity[0].value == ...` | `PriceQuantity(quantity=quantity)`<br>`assert reloaded.quantity.value == ...` |
| [`tests/cdm_workspace/test_create_irs_trade.py`](file:///e:/dev/python/cdm_workspace/tests/cdm_workspace/test_create_irs_trade.py) | `tradeLot[0].priceQuantity[0].quantity[0]` | `tradeLot[0].priceQuantity[0].quantity` |
| [`pyproject.toml`](file:///e:/dev/python/cdm_workspace/pyproject.toml) | `"finos-cdm>=6.22.0"` | `"finos-cdm>=7.1.0"` |

### 再移行チェックリスト
1. `pip install finos-cdm==7.1.0` を実行。
2. `pyproject.toml` の `finos-cdm` 依存バージョン要件を更新。
3. `create_irs_trade.py` およびテストコードの `PriceQuantity.quantity` をスカラー（単一インスタンス）指定に変更。
4. `pytest -v` を実行して全テスト通過を確認。

