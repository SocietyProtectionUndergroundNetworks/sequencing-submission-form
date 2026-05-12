import geopandas as gpd
import pandas as pd
import json
import sys
from shapely.geometry import Point


def create_gpkg(input_json_path, output_gpkg_path):
    with open(input_json_path, "r") as f:
        data = json.load(f)

    if not data:
        print(json.dumps({"error": "No data provided"}))
        sys.exit(1)

    df = pd.DataFrame(data)

    df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")

    df = df.dropna(subset=["Latitude", "Longitude"])
    df = df[~((df["Latitude"] == 0) & (df["Longitude"] == 0))]

    if df.empty:
        print(json.dumps({"error": "No samples with valid coordinates"}))
        sys.exit(1)

    geometry = [
        Point(row["Longitude"], row["Latitude"]) for _, row in df.iterrows()
    ]

    gdf = gpd.GeoDataFrame(
        df.drop(columns=["Latitude", "Longitude"]),
        geometry=geometry,
        crs="EPSG:4326",
    )

    # GeoPackage field names are limited to 63 chars; truncate any that exceed
    gdf.columns = [c[:63] for c in gdf.columns]

    gdf.to_file(output_gpkg_path, driver="GPKG", layer="samples")

    print(json.dumps({"status": "success", "file": output_gpkg_path}))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(
            json.dumps(
                {
                    "error": (
                        "Usage: python create_gpkg.py "
                        "<input_json> <output_gpkg>"
                    )
                }
            )
        )
        sys.exit(1)

    create_gpkg(sys.argv[1], sys.argv[2])
