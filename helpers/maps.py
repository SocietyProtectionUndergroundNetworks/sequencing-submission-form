import requests
import folium
import os


def get_elevations(locations):
    api_key = os.environ.get("GOOGLE_MAP_API_KEY")
    url = "https://maps.googleapis.com/maps/api/elevation/json"
    locations_str = "|".join([f"{lat},{lon}" for lat, lon in locations])
    params = {"locations": locations_str, "key": api_key}
    response = requests.get(url, params=params)
    elevations = []
    if response.status_code == 200:
        results = response.json()["results"]
        if results:
            elevations = [result["elevation"] for result in results]
    return elevations


def get_countries(locations):
    api_key = os.environ.get("GOOGLE_MAP_API_KEY")
    countries = []
    for lat, lon in locations:
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        url += f"?latlng={lat},{lon}&key={api_key}"
        response = requests.get(url)
        if response.status_code == 200:
            results = response.json()["results"]
            if results:
                for component in results[0]["address_components"]:
                    if "country" in component["types"]:
                        countries.append(component["long_name"])
                        break
        else:
            countries.append(None)  # or handle error as needed
    return countries


def generate_map_with_markers(data):
    # Create a base map centered at an approximate global position
    world_map = folium.Map(location=[20, 0], zoom_start=2)

    # Define colors for different cohort groups
    cohort_colors = {
        "SpunLed": "blue",
        "ThirdParty": "red",
        "UE": "green",
        "Other": "gray",
    }

    # Add markers for each sample
    for sample in data:
        lat, lon = sample["Latitude"], sample["Longitude"]
        cohort = sample["cohort_group"]
        project_id = sample["project_id"]
        sample_id = sample["SampleID"]

        # Get color for cohort group (default to gray if missing)
        color = cohort_colors.get(cohort, "gray")

        # Create a marker with a popup showing additional info
        folium.CircleMarker(
            location=[lat, lon],
            radius=5,  # Adjust the size if needed
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.7,
            popup=folium.Popup(
                (
                    f"Sample ID: {sample_id}<br>Project ID: "
                    f" {project_id}<br>Cohort: {cohort}"
                ),
                max_width=300,
            ),
        ).add_to(world_map)

    # Add the ecoregions layer
    folium.GeoJson(
        "geopandasapp/resolve_ecoregions_min.geojson",
        name="Ecoregions",
        style_function=lambda feature: {
            "fillColor": "#6baed6",
            "color": "#2171b5",
            "weight": 1,
            "fillOpacity": 0.4,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["ECO_NAME", "BIOME_NAME", "REALM"],
            aliases=["Ecoregion:", "Biome:", "Realm:"],
            localize=True,
        ),
        popup=folium.GeoJsonPopup(
            fields=["ECO_NAME", "BIOME_NAME", "REALM"],
            aliases=["Ecoregion:", "Biome:", "Realm:"],
            max_width=400,
        ),
    ).add_to(world_map)

    folium.LayerControl().add_to(world_map)

    world_map.save("static/map_with_ecoregions.html")

    return world_map
