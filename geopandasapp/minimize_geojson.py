import geopandas as gpd

# Load the GeoJSON
gdf = gpd.read_file("resolve_ecoregions_min.geojson")

# Simplify polygons (tolerance can be adjusted for more compression)
gdf["geometry"] = gdf["geometry"].simplify(tolerance=0.01, preserve_topology=True)

keep_columns = ["ECO_NAME", "BIOME_NAME", "REALM", "geometry"]
gdf = gdf[keep_columns]

# Save the minimized GeoJSON
gdf.to_file("resolve_ecoregions_simplified.geojson", driver="GeoJSON")
