import requests
import os
import folium
import logging
from folium.plugins import MarkerCluster
from helpers.statistics import get_samples_per_cohort_type_data
from models.db_model import ExternalSamplingTable
from helpers.dbm import session_scope

logger = logging.getLogger("my_app_logger")

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


def generate_samples_map():
    from helpers.statistics import get_samples_per_cohort_type_data

    data = get_samples_per_cohort_type_data()

    color_map = {
        "SpunLed": "red",
        "ThirdParty": "blue",
        "UE": "green",
        "Other": "gray",
    }

    m = folium.Map(location=[20, 0], zoom_start=2)
    feature_groups = {
        key: folium.FeatureGroup(name=key) for key in color_map.keys()
    }

    for item in data:
        lat, lon = item["Latitude"], item["Longitude"]
        cohort_group = item["cohort_group"]
        sample_id = item["SampleID"]
        project_id = item["project_id"]
        cohort = item["cohort"]  # Full cohort name if needed

        color = color_map.get(cohort_group, "gray")

        # Create a popup with additional information
        popup_text = f"""
        <b>Sample ID:</b> {sample_id}<br>
        <b>Project ID:</b> {project_id}<br>
        <b>Cohort:</b> {cohort}<br>
        <b>Cohort Group:</b> {cohort_group}
        """

        marker = folium.CircleMarker(
            location=[lat, lon],
            radius=5,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.7,
            popup=folium.Popup(popup_text, max_width=300),
        )

        feature_groups[cohort_group].add_child(marker)

    for group in feature_groups.values():
        m.add_child(group)

    folium.LayerControl().add_to(m)

    # Save the map
    map_path = "static/map.html"
    m.save(map_path)

def generate_samples_map_full():
    data = get_samples_per_cohort_type_data()

    color_map = {
        "SpunLed": "red",
        "ThirdParty": "blue",
        "UE": "green",
        "Other": "gray",
        "ITS": "purple",  # Color for ITS markers
        "SSU": "orange",  # Color for SSU markers
    }

    m = folium.Map(location=[20, 0], zoom_start=2)
    feature_groups = {
        key: folium.FeatureGroup(name=key) for key in color_map.keys()
    }

    # Add markers from get_samples_per_cohort_type_data
    for item in data:
        lat, lon = item["Latitude"], item["Longitude"]
        cohort_group = item["cohort_group"]
        sample_id = item["SampleID"]
        project_id = item["project_id"]
        cohort = item["cohort"]

        color = color_map.get(cohort_group, "gray")

        popup_text = f"""
        <b>Sample ID:</b> {sample_id}<br>
        <b>Project ID:</b> {project_id}<br>
        <b>Cohort:</b> {cohort}<br>
        <b>Cohort Group:</b> {cohort_group}
        """

        marker = folium.CircleMarker(
            location=[lat, lon],
            radius=5,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.7,
            popup=folium.Popup(popup_text, max_width=300),
        )

        feature_groups[cohort_group].add_child(marker)

    # Add markers from ExternalSamplingTable
    with session_scope() as session:
        external_samples = session.query(ExternalSamplingTable).all()
        for sample in external_samples:
            if sample.longitude and sample.latitude:  # Check if coordinates exist
                dna_region = sample.dna_region
                lat, lon = sample.latitude, sample.longitude
                color = color_map.get(dna_region, "gray")

                popup_text = f"""
                <b>DNA Region:</b> {dna_region}<br>
                <b>Latitude:</b> {lat}<br>
                <b>Longitude:</b> {lon}
                """

                marker = folium.CircleMarker(
                    location=[lat, lon],
                    radius=5,
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.7,
                    popup=folium.Popup(popup_text, max_width=300),
                )

                feature_groups[dna_region].add_child(marker)

    for group in feature_groups.values():
        m.add_child(group)

    folium.LayerControl().add_to(m)

    map_path = "static/map_full.html"
    m.save(map_path)


def generate_samples_map_full_clustered():
    data = get_samples_per_cohort_type_data()

    m = folium.Map(location=[20, 0], zoom_start=2)

    # Marker clusters
    cohort_cluster = MarkerCluster().add_to(m)
    external_cluster = MarkerCluster().add_to(m)

    # Add markers from get_samples_per_cohort_type_data
    for item in data:
        lat, lon = item["Latitude"], item["Longitude"]
        cohort_group = item["cohort_group"]
        sample_id = item["SampleID"]
        project_id = item["project_id"]
        cohort = item["cohort"]

        popup_text = f"""
        <b>Sample ID:</b> {sample_id}<br>
        <b>Project ID:</b> {project_id}<br>
        <b>Cohort:</b> {cohort}<br>
        <b>Cohort Group:</b> {cohort_group}
        """

        folium.CircleMarker(
            location=[lat, lon],
            radius=5,
            popup=folium.Popup(popup_text, max_width=300),
        ).add_to(cohort_cluster)

    # Add markers from ExternalSamplingTable
    with session_scope() as session:
        external_samples = session.query(ExternalSamplingTable).all()
        for sample in external_samples:
            if sample.longitude and sample.latitude:
                dna_region = sample.dna_region
                lat, lon = sample.latitude, sample.longitude

                popup_text = f"""
                <b>DNA Region:</b> {dna_region}<br>
                <b>Latitude:</b> {lat}<br>
                <b>Longitude:</b> {lon}
                """

                folium.CircleMarker(
                    location=[lat, lon],
                    radius=5,
                    popup=folium.Popup(popup_text, max_width=300),
                ).add_to(external_cluster)

    folium.LayerControl().add_to(m)

    map_path = "static/map_full_clustered.html"
    m.save(map_path)    