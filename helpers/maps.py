import requests
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
