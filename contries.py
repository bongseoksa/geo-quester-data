import os
import glob
import re

# geojson 폴더 경로
geojson_dir = "./geojson"

# 모든 geojson 파일 찾기
geojson_files = glob.glob(os.path.join(geojson_dir, "*.geojson"))

# 국가 3자 코드를 저장할 set (중복 제거)
country_codes = set()

# 파일명 패턴: gadm41_{COUNTRY3}_{NUM}.geojson
pattern = re.compile(r"gadm41_([A-Z]{3})_\d+\.geojson", re.IGNORECASE)

for file_path in geojson_files:
    filename = os.path.basename(file_path)
    match = pattern.match(filename)
    if match:
        country_codes.add(match.group(1).upper())  # 대문자로 통일

# 배열로 변환
country_list = list(country_codes)

print(country_list)
