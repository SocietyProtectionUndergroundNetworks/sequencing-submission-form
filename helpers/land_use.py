import ee
import json
import logging
from helpers.ecoregions import return_ecoregion

# Define the path to the service account JSON
service_account_key = "/google_auth_file/key_file.json"
# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")


# Authenticate and initialize Earth Engine
def initialize_earth_engine():
    with open(service_account_key, "r") as file:
        service_account_info = json.load(file)
        service_account_email = service_account_info["client_email"]

    credentials = ee.ServiceAccountCredentials(
        service_account_email, service_account_key
    )
    ee.Initialize(credentials)


# Function to get land cover classification for given coordinates
def get_land_use(longitude, latitude):
    # Initialize Earth Engine (if not initialized globally)
    # initialize_earth_engine()

    # Load the ESA WorldCover dataset
    dataset = ee.Image("ESA/WorldCover/v200/2021")

    # Define the point geometry for the specified coordinates
    point = ee.Geometry.Point([longitude, latitude])

    # Sample the dataset at the specified point
    land_cover_value = (
        dataset.sample(region=point, scale=10).first().get("Map")
    )

    # Map land cover codes to their descriptions
    land_cover_dict = {
        10: "Tree cover",
        20: "Shrubland",
        30: "Grassland",
        40: "Cropland",
        50: "Built-up",
        60: "Bare / sparse vegetation",
        70: "Snow and ice",
        80: "Permanent water bodies",
        90: "Herbaceous wetland",
        95: "Mangroves",
        100: "Moss and lichen",
    }

    # Retrieve the land cover class and return the description
    try:
        land_cover_code = land_cover_value.getInfo()
        land_cover = land_cover_dict.get(land_cover_code, "Unknown land cover")
        return land_cover
    except Exception as e:
        return f"Error retrieving land cover data: {e}"


def get_resolve_ecoregion(longitude, latitude):
    """Get the resolved ecoregion name using the Geopandas container."""
    coordinates_list = [(latitude, longitude)]  # Ensure correct format
    result = return_ecoregion(coordinates_list)

    try:
        output = json.loads(result)  # Parse the JSON string

        if isinstance(output, list) and output:
            ecoregion_data = output[0]  # Extract the first result

            if (
                "ecoregion" in ecoregion_data
                and "ECO_NAME" in ecoregion_data["ecoregion"]
            ):
                return ecoregion_data["ecoregion"][
                    "ECO_NAME"
                ]  # Return the ecoregion name
            else:
                logger.error("Unexpected response format: Missing 'ECO_NAME'")
                return None
        else:
            logger.error("Unexpected response format from Geopandas")
            return None
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Geopandas response: {e}")
        return None


def get_baileys_ecoregion(longitude, latitude):
    # Load the UNEP-WCMC Baileys Ecoregions of the World dataset
    ecoregions = ee.FeatureCollection(
        "projects/spun-geospatial/assets/baileysEcoregions"
    )

    # Define the point geometry for the specified coordinates
    point = ee.Geometry.Point([longitude, latitude])

    # Filter the dataset to find the ecoregion at the given point
    ecoregion_info = ecoregions.filterBounds(point).first()

    # Try retrieving the province description, handling any errors
    try:
        biome_name = ecoregion_info.get("pro_desc").getInfo()
        return biome_name
    except Exception as e:
        # Log the error and return None
        logger.error(
            f"Error retrieving Baileys ecoregion"
            f" data for coordinates ({latitude}, {longitude}): {e}"
        )
        return None


# Function to get elevation for given coordinates
def get_elevation(longitude, latitude):
    # Load the SRTM Digital Elevation Model (DEM) dataset
    srtm = ee.Image("USGS/SRTMGL1_003")

    # Define the point geometry for the specified coordinates
    point = ee.Geometry.Point([longitude, latitude])

    # Sample the SRTM dataset at the given point and get the elevation
    elevation_value = (
        srtm.sample(region=point, scale=30).first().get("elevation")
    )

    # Retrieve the elevation value
    try:
        elevation = elevation_value.getInfo()
        return elevation
    except Exception as e:
        return f"Error retrieving elevation data: {e}"
