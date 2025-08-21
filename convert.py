import os
import glob
import zipfile
import json
import geopandas as gpd

def convert_shapefiles_from_zips(input_root="./shapefile", output_root="./geojson", temp_extract="./temp_shp"):
    """
    1. 입력 폴더 내 모든 .zip 파일 압축 해제
    2. 압축 해제 폴더 안의 Shapefile을 GeoJSON으로 변환
    3. 출력은 ./geojson 폴더에 저장
    """
    os.makedirs(output_root, exist_ok=True)
    os.makedirs(temp_extract, exist_ok=True)

    # 입력 폴더 내 모든 zip 파일 탐색
    zip_files = glob.glob(os.path.join(input_root, "**", "*.zip"), recursive=True)
    if not zip_files:
        print("압축 파일이 없습니다.")
        return

    success_count = 0
    skip_count = 0
    already_exist_count = 0

    for zip_path in zip_files:
        # 임시 폴더에 압축 해제
        extract_path = os.path.join(temp_extract, os.path.splitext(os.path.basename(zip_path))[0])
        os.makedirs(extract_path, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)

        # 압축 해제된 폴더 내 모든 .shp 파일 변환
        shapefile_paths = glob.glob(os.path.join(extract_path, "**", "*.shp"), recursive=True)
        for shp_path in shapefile_paths:
            base = os.path.splitext(os.path.basename(shp_path))[0]
            geojson_file = os.path.join(output_root, base + ".geojson")

            # 이미 변환된 파일이 있으면 스킵
            if os.path.exists(geojson_file):
                print(f"이미 존재하여 스킵: {geojson_file}")
                already_exist_count += 1
                continue

            required_files = [os.path.join(os.path.dirname(shp_path), base + ext) for ext in [".shp", ".shx", ".dbf"]]
            missing_files = [f for f in required_files if not os.path.exists(f)]
            if missing_files:
                print(f"필수 파일 누락: {missing_files}, 변환 스킵")
                skip_count += 1
                continue

            try:
                gdf = gpd.read_file(shp_path)

                # CRS 없으면 강제 지정 (보통 GADM은 EPSG:4326)
                if gdf.crs is None:
                    print(f"CRS 없음 → EPSG:4326으로 설정: {shp_path}")
                    gdf = gdf.set_crs(epsg=4326)
                else:
                    gdf = gdf.to_crs(epsg=4326)

                gdf.to_file(geojson_file, driver="GeoJSON")
                print(f"변환 완료: {geojson_file}")
                success_count += 1
            except Exception as e:
                print(f"변환 실패: {shp_path}, 에러: {e}")
                skip_count += 1

    print(f"\n총 {len(zip_files)}개 압축 파일 처리 완료")
    print(f"성공적으로 변환된 Shapefile: {success_count}")
    print(f"이미 존재하여 스킵된 파일: {already_exist_count}")
    print(f"기타 스킵된 파일: {skip_count}")


def validate_and_repair_geojson_files(geojson_folder="./geojson", shapefile_root="./temp_shp"):
    """
    1. geojson_folder 내 모든 GeoJSON 파일 검증
    2. 오류 발생 시 -> shapefile_root에서 같은 이름의 Shapefile을 찾아 다시 변환 시도
    """
    geojson_files = glob.glob(os.path.join(geojson_folder, "*.geojson"))
    if not geojson_files:
        print("검증할 GeoJSON 파일이 없습니다.")
        return

    valid_count = 0
    repaired_count = 0
    failed_count = 0

    for geojson_path in geojson_files:
        filename = os.path.basename(geojson_path)
        basename = os.path.splitext(filename)[0]

        try:
            # Step 1: JSON 파싱
            with open(geojson_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "type" not in data:
                raise ValueError("필드 'type' 없음")

            # Step 2: GeoPandas 로딩
            gdf = gpd.read_file(geojson_path)
            if gdf.empty:
                raise ValueError("GeoDataFrame 비어 있음")

            # Step 3: CRS 확인
            if gdf.crs is None:
                raise ValueError("CRS 없음")

            # Step 4: 좌표 범위 확인 (EPSG:4326일 경우)
            if gdf.crs.to_epsg() == 4326:
                minx, miny, maxx, maxy = gdf.total_bounds
                if not (-180 <= minx <= 180 and -180 <= maxx <= 180 and -90 <= miny <= 90 and -90 <= maxy <= 90):
                    raise ValueError(f"좌표 범위 이상: {minx}, {miny}, {maxx}, {maxy}")

            print(f"✅ 정상: {filename}, features={len(gdf)}, CRS={gdf.crs}")
            valid_count += 1
            continue  # 정상 파일은 건너뜀

        except Exception as e:
            print(f"❌ 오류: {filename}, 이유: {e}")

            # ---- 오류 발생 시 shapefile 기반 재변환 시도 ----
            shp_path = None
            for root, dirs, files in os.walk(shapefile_root):
                for f in files:
                    if f.endswith(".shp") and os.path.splitext(f)[0] == basename:
                        shp_path = os.path.join(root, f)
                        break
                if shp_path:
                    break

            if not shp_path:
                print(f"   ⚠️ 원본 Shapefile({basename})을 찾을 수 없어 복구 불가")
                failed_count += 1
                continue

            try:
                gdf = gpd.read_file(shp_path)

                if gdf.crs is None:
                    print(f"   ⚠️ CRS 없음 → EPSG:4326으로 설정")
                    gdf = gdf.set_crs(epsg=4326)
                else:
                    gdf = gdf.to_crs(epsg=4326)

                gdf.to_file(geojson_path, driver="GeoJSON")
                print(f"   🔄 복구 성공: {filename}")
                repaired_count += 1

            except Exception as e2:
                print(f"   ❌ 복구 실패: {filename}, 에러: {e2}")
                failed_count += 1

    print("\n===== 검증 및 복구 요약 =====")
    print(f"총 파일 수: {len(geojson_files)}")
    print(f"정상 파일: {valid_count}")
    print(f"복구된 파일: {repaired_count}")
    print(f"실패한 파일: {failed_count}")


# 실행
convert_shapefiles_from_zips()
validate_and_repair_geojson_files("./geojson", "./temp_shp")
