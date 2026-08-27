import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
import os

# Standalone script to bring together the climate classification and biome/ecoregion data for a set of locations in a CSV file.
# Using geopandas, it performs spatial joins to determine the climate class and biome/ecoregion for each point based on its latitude and longitude.
# For the climate classification, it uses the Köppen-Geiger codes from the provided shapefile and maps them to descriptive labels using a predefined dictionary.
# For the biome/ecoregion, it uses the provided GeoPackage file and handles points that do not fall directly within a polygon by snapping them to the nearest polygon.
# The Köppen-Geiger shapefile (observed climate, 1976-2000) can be downloaded from https://koeppen-geiger.vu-wien.ac.at
# The biome/ecoregions GeoPackage (RESOLVE Ecoregions and Biomes) can be downloaded from https://hub.arcgis.com/datasets/esri::resolve-ecoregions-and-biomes/explore


# Configuration
CLIMATE_MAP_FILE = "c1976_2000_0/c1976_2000.shp"
BIOME_MAP_FILE = "Resolve_Ecoregions_-6779945127424040112.gpkg"
INPUT_CSV = "locations_for_climate.csv"
OUTPUT_CSV = "locations_for_climate_with_climate.csv"

# Mapping dictionary for Köppen-Geiger codes (Observed 1976-2000)
# These codes correspond to the numeric GRIDCODE values in the shapefile
koppen_map = {
    11: "Af (Tropical rainforest)",
    12: "Am (Tropical monsoon)",
    13: "As (Tropical savanna dry summer)",
    14: "Aw (Tropical savanna dry winter)",
    21: "BWk (Arid desert cold)",
    22: "BWh (Arid desert hot)",
    26: "BSk (Arid steppe cold)",
    27: "BSh (Arid steppe hot)",
    31: "Cfa (Humid subtropical)",
    32: "Cfb (Temperate oceanic)",
    33: "Cfc (Subpolar oceanic)",
    34: "Csa (Hot-summer Mediterranean)",
    35: "Csb (Warm-summer Mediterranean)",
    36: "Csc (Cool-summer Mediterranean)",
    37: "Cwa (Monsoon-influenced humid subtropical)",
    38: "Cwb (Subtropical highland)",
    39: "Cwc (Cold subtropical highland)",
    41: "Dfa (Hot-summer humid continental)",
    42: "Dfb (Warm-summer humid continental)",
    43: "Dfc (Subarctic)",
    44: "Dfd (Extremely cold subarctic)",
    45: "Dsa (Dry-summer continental hot summer)",
    46: "Dsb (Dry-summer continental warm summer)",
    47: "Dsc (Dry-summer continental cool summer)",
    48: "Dsd (Dry-summer continental extremely cold)",
    49: "Dwa (Dry-winter continental hot summer)",
    50: "Dwb (Dry-winter continental warm summer)",
    51: "Dwc (Dry-winter continental cool summer)",
    52: "Dwd (Dry-winter continental extremely cold)",
    61: "EF (Polar frost/Ice cap)",
    62: "ET (Polar tundra)",
}


def classify_climate():
    # 1. Validation
    if not os.path.exists(CLIMATE_MAP_FILE):
        print(f"Error: Shapefile not found at {CLIMATE_MAP_FILE}")
        return
    if not os.path.exists(BIOME_MAP_FILE):
        print(f"Error: Biome/ecoregions file not found at {BIOME_MAP_FILE}")
        return
    if not os.path.exists(INPUT_CSV):
        print(f"Error: Input file '{INPUT_CSV}' not found.")
        return

    # 2. Load Data
    print("Loading climate classification map (this may take a moment)...")
    climate_gdf = gpd.read_file(CLIMATE_MAP_FILE)

    print("Loading biome/ecoregions map (this may take a moment)...")
    biome_gdf = gpd.read_file(BIOME_MAP_FILE)[
        ["BIOME_NUM", "BIOME_NAME", "geometry"]
    ]

    print(f"Reading {INPUT_CSV}...")
    df = pd.read_csv(INPUT_CSV)

    # 3. Create Spatial Points from CSV
    # Longitude is X, Latitude is Y. standard WGS84 is EPSG:4326.
    geometry = [
        Point(lon, lat) for lon, lat in zip(df["Longitude"], df["Latitude"])
    ]
    points_gdf = gpd.GeoDataFrame(
        df.copy(), geometry=geometry, crs="EPSG:4326"
    )

    # 4. Determine the biome for each point
    # The ecoregions/biome polygons don't perfectly cover every coastal or
    # boundary point, so anything that doesn't fall directly 'within' a
    # polygon is snapped to the nearest one instead (same approach used by
    # app.py for single-point ecoregion lookups).
    print("Performing spatial join to determine biomes...")
    biome_points = (
        points_gdf
        if points_gdf.crs == biome_gdf.crs
        else points_gdf.to_crs(biome_gdf.crs)
    )
    biome_joined = gpd.sjoin(
        biome_points, biome_gdf, predicate="within", how="left"
    )
    # A point can straddle more than one polygon boundary and match twice;
    # keep only the first match so the row count stays 1:1 with the input.
    biome_joined = biome_joined[~biome_joined.index.duplicated(keep="first")]
    unmatched_idx = biome_joined.index[biome_joined["BIOME_NAME"].isna()]
    if len(unmatched_idx) > 0:
        # Project to Equal Earth (EPSG:6933) so distance is in metres.
        unmatched_points = biome_points.loc[unmatched_idx].to_crs(epsg=6933)
        projected_biome_gdf = biome_gdf.to_crs(epsg=6933)
        nearest = gpd.sjoin_nearest(unmatched_points, projected_biome_gdf)
        nearest = nearest[~nearest.index.duplicated(keep="first")]
        biome_joined.loc[nearest.index, "BIOME_NUM"] = nearest["BIOME_NUM"]
        biome_joined.loc[nearest.index, "BIOME_NAME"] = nearest["BIOME_NAME"]
    # Reindex explicitly (rather than relying on row order) so the values
    # line up correctly regardless of how sjoin ordered its output.
    biome_joined = biome_joined.reindex(biome_points.index)
    # Assign onto points_gdf (not df) so the columns survive into the
    # climate join below and end up in the final output.
    points_gdf["Biome_Number"] = biome_joined["BIOME_NUM"]
    points_gdf["Biome_Name"] = biome_joined["BIOME_NAME"]

    # 5. Align Projections
    if points_gdf.crs != climate_gdf.crs:
        points_gdf = points_gdf.to_crs(climate_gdf.crs)

    # 6. Perform Spatial Join
    print("Performing spatial join to determine climate classes...")
    # Matches each point to the climate polygon it is 'within'
    joined_gdf = gpd.sjoin(
        points_gdf, climate_gdf, predicate="within", how="left"
    )

    # 7. Map Descriptions and Cleanup
    # Standard shapefile uses 'GRIDCODE' for the numeric class
    if "GRIDCODE" in joined_gdf.columns:
        joined_gdf = joined_gdf.rename(
            columns={"GRIDCODE": "Koppen_Geiger_Code"}
        )

        # Add the descriptive label using our lookup dictionary
        joined_gdf["Koppen_Description"] = joined_gdf[
            "Koppen_Geiger_Code"
        ].map(koppen_map)
    else:
        print(
            "Warning: 'GRIDCODE' column not found in shapefile. Checking alternatives..."
        )
        # Fallback if the column has a different name
        for col in ["GRID_CODE", "CLASS", "Class"]:
            if col in joined_gdf.columns:
                joined_gdf["Koppen_Description"] = joined_gdf[col].map(
                    koppen_map
                )
                break

    # Remove spatial geometry and index columns before saving to CSV
    final_df = pd.DataFrame(
        joined_gdf.drop(columns=["geometry", "index_right"], errors="ignore")
    )

    # 8. Save Result
    final_df.to_csv(OUTPUT_CSV, index=False)
    print(f"Success! Classification complete. File saved as: {OUTPUT_CSV}")


if __name__ == "__main__":
    classify_climate()
