import geopandas as gpd
import pandas as pd
import math
import os
from supabase import create_client, Client
import time # time.sleep用
import sys # Add sys import for path manipulation if config is in parent dir
from pathlib import Path # Use pathlib for robust path handling

# --- 設定 ---
# スクリプトの場所に基づいてGeoJSONファイルのデフォルトパスを設定
script_dir = Path(__file__).parent.resolve()
project_root = script_dir.parent # Assuming script is in 'scripts' dir
default_geojson_path = project_root / 'data' / 'N02-23_GML' / 'utf8' / 'N02-23_Station.geojson' # Example path relative to project root
# --- ユーザーは必要に応じてこのパスをDownloadsなどに変更してください ---
geojson_path = os.getenv('STATION_GEOJSON_PATH', str(default_geojson_path)) # Allow overriding via env var
# --- ここで実際のファイルパスを指定してください ---
geojson_path = '/Users/akatsuki18/Downloads/N02-23_GML/utf8/N02-23_Station.geojson' # <-- この行のコメント(#)を外す

if not Path(geojson_path).is_file():
    print(f"エラー: 指定されたGeoJSONファイルが見つかりません: {geojson_path}")
    print("スクリプト内の 'geojson_path' 変数を正しいパスに設定するか、")
    print("環境変数 'STATION_GEOJSON_PATH' を設定してください。")
    sys.exit(1) # Exit if file not found

source_file_name = Path(geojson_path).name # 保存するファイル名を抽出

# --- config.py をインポートするためにパスを追加 ---
# config.py がプロジェクトルートにあると仮定
sys.path.append(str(project_root))

# --- デバッグ出力 ---
print("--- Debug Info ---")
print(f"Project Root Path added to sys.path: {project_root}")
print(f"Current Working Directory (CWD): {os.getcwd()}")
print("sys.path contents:")
for p in sys.path:
    print(f"  - {p}")
print("------------------")
# --- デバッグ出力ここまで ---

try:
    from config import settings
except ModuleNotFoundError:
    print(f"エラー: config.py が見つかりません。プロジェクトルートを確認してください: {project_root}")
    sys.exit(1)

# 国土数値情報の仕様に基づく可能性のある列名 (要確認・調整)
station_name_col = 'N02_005'
railway_line_col = 'N02_003'
operator_type_col = 'N02_004'
# 乗降客数列は N02 データには通常含まれない
passenger_col = 'N05_001' # 仮の列名 (N05データ用)

# Supabase設定
SUPABASE_URL = settings.SUPABASE_URL
SUPABASE_KEY = settings.SUPABASE_KEY
TABLE_NAME = 'stations'

# --- End Configuration ---

def init_supabase_client() -> Client | None:
    """Supabaseクライアントを初期化"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("エラー: SupabaseのURLまたはキーが.envファイルに設定されていません。")
        return None
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Supabaseクライアントの初期化に成功しました。")
        return supabase
    except Exception as e:
        print(f"Supabaseクライアントの初期化中にエラーが発生しました: {e}")
        return None

def process_and_save_stations(filepath: str, supabase: Client):
    """GeoJSONを処理し、Supabaseにデータを保存する"""
    try:
        # --- GeoJSON読み込み ---
        print(f"GeoJSONファイルを読み込んでいます: {filepath}")
        try:
            gdf = gpd.read_file(filepath, encoding='utf-8')
        except UnicodeDecodeError:
            print("UTF-8での読み込みに失敗。Shift_JISで再試行...")
            gdf = gpd.read_file(filepath, encoding='shift_jis')
        except Exception as read_err:
            print(f"ファイル読み込みエラー: {read_err}")
            return False

        print(f"\n--- GeoDataFrame情報 ({filepath}) ---")
        print(f"CRS: {gdf.crs}, 駅数: {len(gdf)}")
        print(f"列名: {gdf.columns.tolist()}")
        print("-" * 20)

        # --- データ抽出と整形 ---
        stations_to_upsert = []
        stations_processed = 0
        stations_skipped_no_name = 0
        stations_skipped_invalid_geom = 0

        # 乗降客数列の存在確認
        passenger_col_exists = passenger_col in gdf.columns
        if not passenger_col_exists:
            print(f"警告: 乗降客数列 '{passenger_col}' が見つかりません。passengersはNULLで保存されます。")

        for index, row in gdf.iterrows():
            geometry = row['geometry']

            # 駅名 (必須)
            station_name = row.get(station_name_col)
            if not station_name or (isinstance(station_name, str) and not station_name.strip()):
                stations_skipped_no_name += 1
                continue
            station_name = station_name.strip()

            # 座標 (必須)
            latitude, longitude = None, None
            if geometry is None or not hasattr(geometry, 'geom_type'):
                # print(f"警告: 駅 '{station_name}' (Index: {index}) は無効なジオメトリ。スキップ。")
                stations_skipped_invalid_geom += 1
                continue
            if geometry.geom_type == 'Point':
                longitude, latitude = geometry.x, geometry.y
            elif geometry.geom_type == 'MultiPoint':
                 # print(f"警告: 駅 '{station_name}' (Index: {index}) は MultiPoint。最初の点を使用。")
                 try:
                     point = geometry.geoms[0]
                     longitude, latitude = point.x, point.y
                 except IndexError:
                     print(f"警告: 駅 '{station_name}' (Index: {index}) のMultiPointが空。スキップ。")
                     stations_skipped_invalid_geom += 1
                     continue
            else:
                # print(f"警告: 駅 '{station_name}' (Index: {index}) は {geometry.geom_type}。Centroidを使用。")
                try:
                    centroid = geometry.centroid
                    longitude, latitude = centroid.x, centroid.y
                except Exception as centroid_err:
                    print(f"警告: 駅 '{station_name}' のCentroid計算失敗 ({centroid_err})。スキップ。")
                    stations_skipped_invalid_geom += 1
                    continue

            if latitude is None or longitude is None:
                 # print(f"警告: 駅 '{station_name}' (Index: {index}) の座標取得失敗。スキップ。")
                 stations_skipped_invalid_geom += 1
                 continue

            # 乗降客数 (任意)
            passengers = None
            if passenger_col_exists:
                passenger_value = row.get(passenger_col)
                if passenger_value is not None and not (isinstance(passenger_value, float) and math.isnan(passenger_value)):
                    try:
                        # 空文字列なども考慮
                        if str(passenger_value).strip():
                            passengers = int(float(passenger_value)) # float経由で整数変換
                        else:
                            pass # 空文字列はNULL
                    except (ValueError, TypeError):
                         # print(f"警告: 駅 '{station_name}' の乗降客数 '{passenger_value}' を整数変換できず。")
                         pass # NULLのまま

            # その他情報 (参考用)
            raw_line = row.get(railway_line_col)
            raw_op = row.get(operator_type_col)

            station_data = {
                'name': station_name, # このnameでupsertする想定
                'latitude': latitude,
                'longitude': longitude,
                'passengers': passengers, # NULL許容
                'raw_name': str(row.get(station_name_col, '')), # 元のデータも保持
                'raw_line_name': str(raw_line) if raw_line else None,
                'raw_operator_type': str(raw_op) if raw_op else None,
                'source_file': source_file_name
                # created_at, updated_at はDB側で自動設定される想定
            }
            stations_to_upsert.append(station_data)
            stations_processed += 1

        print("-" * 20)
        print(f"抽出処理完了。")
        print(f"  - 処理対象駅数: {stations_processed}")
        print(f"  - スキップ (駅名なし): {stations_skipped_no_name}")
        print(f"  - スキップ (無効ジオメトリ/座標): {stations_skipped_invalid_geom}")
        print("-" * 20)

        if not stations_to_upsert:
            print("Supabaseに保存するデータがありません。")
            return True # 処理自体は成功とみなす

        # --- Upsert前にDataFrameに変換して重複を削除 ---
        df_stations = pd.DataFrame(stations_to_upsert)
        print(f"Upsert前のレコード数: {len(df_stations)}")
        # 'name' 列を基準に重複を削除し、最初に出現したものを残す
        df_stations_dedup = df_stations.drop_duplicates(subset=['name'], keep='first')
        print(f"重複削除後のレコード数: {len(df_stations_dedup)}")
        # DataFrameを辞書のリストに戻す
        stations_to_upsert_dedup = df_stations_dedup.to_dict('records')
        # ---------------------------------------------- #

        # --- SupabaseへUpsert --- (重複削除後のデータを使用)
        chunk_size = 500
        total_upserted = 0
        total_failed = 0

        print(f"SupabaseへのUpsertを開始します (チャンクサイズ: {chunk_size})...")

        # ループで使うリストを重複削除後のものに変更
        for i in range(0, len(stations_to_upsert_dedup), chunk_size):
            chunk = stations_to_upsert_dedup[i:i + chunk_size]
            print(f"  チャンク {i // chunk_size + 1}/{math.ceil(len(stations_to_upsert_dedup) / chunk_size)} ({len(chunk)}件) を処理中...")
            try:
                # upsertを実行
                response = supabase.table(TABLE_NAME).upsert(
                    chunk,
                    on_conflict='name'
                ).execute()
                # エラーチェック (PostgRESTの仕様やライブラリバージョンで応答が変わる可能性あり)
                # data属性が存在するか、エラーがないかで判断を試みる
                response_data = getattr(response, 'data', None)
                response_error = getattr(response, 'error', None) # V2 では error 属性があるかも

                if response_data and not response_error:
                     upserted_count = len(response_data)
                     print(f"    -> 成功: {upserted_count}件")
                     total_upserted += upserted_count
                # elif response_error:
                #      print(f"    -> APIエラー: {response_error}")
                #      total_failed += len(chunk)
                else:
                    # 成功したがデータが空、または未知の応答形式
                    print(f"    -> 完了 (応答データなしまたは未知の形式)。レスポンス: {response}")
                    # ここでは成功としてカウント（必要に応じて調整）
                    total_upserted += len(chunk)

            except Exception as e:
                print(f"    -> Upsert中に予期せぬエラー発生: {e}")
                total_failed += len(chunk)
                # エラーによってはリトライ処理などを検討
                print("      エラーのため、1秒待機して次のチャンクへ...")
                time.sleep(1)

            # APIリミット等を考慮して少し待機 (任意だが推奨)
            time.sleep(0.2)

        print("-" * 20)
        print("SupabaseへのUpsert完了。")
        print(f"  - 成功/完了件数 (目安): {total_upserted}")
        print(f"  - 失敗件数 (目安): {total_failed}")
        print("-" * 20)

        return total_failed == 0 # 全て成功した場合 True

    except FileNotFoundError:
        print(f"エラー: ファイルが見つかりません: {filepath}")
        return False
    except KeyError as ke:
         print(f"エラー: 予期した列が見つかりません: {ke}。GeoJSONファイルを確認してください。")
         return False
    except Exception as e:
        print(f"予期せぬエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        return False

# --- メイン処理 ---
if __name__ == "__main__":
    supabase_client = init_supabase_client()

    if supabase_client:
        print(f"処理を開始します。対象ファイル: {geojson_path}")
        success = process_and_save_stations(geojson_path, supabase_client)
        if success:
            print("\nスクリプトは正常に完了しました。")
        else:
            print("\nスクリプトの実行中にエラーが発生しました。ログを確認してください。")
    else:
        print("\nSupabaseクライアントを初期化できなかったため、処理を中止しました。")
        sys.exit(1)