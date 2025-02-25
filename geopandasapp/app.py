import geopandas as gpd
import json
import os
import sys
from shapely.geometry import Point

# Path to the .gpkg file
GPKG_FILE = "Resolve_Ecoregions_-6779945127424040112.gpkg"


def get_ecoregions(coords):
    """Returns the ecoregions for a list of coordinates."""

    # Check if the GPKG file exists
    if not os.path.exists(GPKG_FILE):
        print(
            json.dumps(
                {
                    "error": (
                        "Missing file, please download the gpkg "
                        "file (GeoPackage) it from "
                        "https://hub.arcgis.com/datasets/esri::"
                        "resolve-ecoregions-and-biomes/explore and place it "
                        "in the geopandasapp directory"
                    )
                }
            )
        )
        return

    # Load the GeoDataFrame (only once to optimize performance)
    global ecoregions
    if "ecoregions" not in globals():
        ecoregions = gpd.read_file(GPKG_FILE)

    # Create a GeoDataFrame for the input points
    points = gpd.GeoDataFrame(
        geometry=[Point(lon, lat) for lat, lon in coords], crs=ecoregions.crs
    )

    # Perform spatial join to find matching ecoregions
    matched = gpd.sjoin(points, ecoregions, predicate="within")

    results = []
    for i, (lat, lon) in enumerate(coords):
        if i in matched.index:
            ecoregion_info = matched.loc[i].drop("geometry").to_dict()
            results.append(
                {"lat": lat, "lon": lon, "ecoregion": ecoregion_info}
            )
        else:
            results.append(
                {
                    "lat": lat,
                    "lon": lon,
                    "message": "No matching ecoregion found",
                }
            )

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    if len(sys.argv) < 3 or len(sys.argv) % 2 == 0:
        print(
            json.dumps(
                {
                    "error": (
                        "Usage: python app.py <lat1> <lon1> <lat2> <lon2> ..."
                    )
                }
            )
        )
    else:
        # Parse the coordinates from command-line arguments
        coords = [
            (float(sys.argv[i]), float(sys.argv[i + 1]))
            for i in range(1, len(sys.argv), 2)
        ]
        get_ecoregions(coords)
