import os
import csv
import geopandas as gpd
from shapely.geometry import LineString
import requests
from io import BytesIO
from PIL import Image, ImageDraw
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# HERE Maps API configuration
ZOOM = 18
TILE_SIZE = 512
TILE_FMT = "png"
LIMIT = 5  # Maximum number of POIs to process (adjustable)

# Get API key from environment or use default for testing
# In production, use environment variables instead of hardcoded keys
API_KEY = os.getenv('HERE_API_KEY', '')
if not API_KEY:
    logger.warning("HERE_API_KEY environment variable not set, using default value for testing")
    API_KEY = 'API'

# 1) Check directory and files
def list_working_dir():
    """List working directory contents for debugging"""
    cwd = os.getcwd()
    files = os.listdir(cwd)
    logger.info(f"Current directory: {cwd}")
    logger.info(f"Available files: {files}")

# 2) Dynamically detect column names
def detect_columns(gdf):
    """Detect link_id and name columns case-insensitively"""
    cols = list(gdf.columns)
    link_cols = [c for c in cols if c.lower() == 'link_id']
    name_cols = [c for c in cols if c.lower() in ('st_name', 'name')]

    link_col = link_cols[0] if link_cols else None
    name_col = name_cols[0] if name_cols else None

    return link_col, name_col

# 3) Convert lat/lon to HERE tile coordinates
def lat_lon_to_tile(lat, lon, zoom):
    """Convert latitude/longitude to tile coordinates at specified zoom level"""
    import math
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.log(math.tan(lat_rad) + 1/math.cos(lat_rad)) / math.pi) / 2.0 * n)
    return x, y

# 4) Download satellite tile
def get_sat_tile(lat, lon):
    """Download satellite tile image centered on specified coordinates"""
    x, y = lat_lon_to_tile(lat, lon, ZOOM)
    url = (
        f"https://maps.hereapi.com/v3/base/mc/{ZOOM}/{x}/{y}/{TILE_FMT}"
        f"?style=satellite.day&size={TILE_SIZE}&apiKey={API_KEY}"
    )

    try:
        resp = requests.get(url)
        resp.raise_for_status()  # Raise exception for HTTP errors
        return Image.open(BytesIO(resp.content))
    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading satellite image: {e}")
        return None

def main():
    """Main function to process POIs and generate satellite images"""
    list_working_dir()

    # Output directory for images
    output_dir = 'poi_images'
    os.makedirs(output_dir, exist_ok=True)

    # 5) Load POI CSV
    poi_csv = 'DBs/POI_4815440.csv'
    try:
        with open(poi_csv, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            # Find the appropriate column name for link_id
            first_row = next(reader, None)
            if not first_row:
                raise ValueError(f"Empty CSV file: {poi_csv}")

            # Reset file pointer and re-read
            f.seek(0)
            reader = csv.DictReader(f)

            # Try to find link_id column
            link_id_col = next((col for col in reader.fieldnames if col.lower() == 'link_id'), None)
            if not link_id_col:
                raise KeyError(f"Could not find link_id column in {poi_csv}")

            poi_ids = [row.get(link_id_col) for row in reader]
    except FileNotFoundError:
        logger.error(f"POI CSV file not found: {poi_csv}")
        return
    except Exception as e:
        logger.error(f"Error reading POI CSV: {e}")
        return

    # Limit the number of POIs to process
    poi_ids = poi_ids[:LIMIT]
    logger.info(f"Processing {len(poi_ids)} POIs: {poi_ids}")

    # 6) Load streets GeoJSON
    geojson_path = 'DBs/SREETS_NAMING_ADDRESSING_4815440.geojson'
    try:
        if not os.path.exists(geojson_path):
            raise FileNotFoundError(f"File not found: {geojson_path}")
        calles = gpd.read_file(geojson_path)
        if calles.crs is None:
            calles.set_crs('EPSG:4326', inplace=True)
    except Exception as e:
        logger.error(f"Error loading GeoJSON: {e}")
        return

    # 7) Detect correct columns
    link_col, name_col = detect_columns(calles)
    if not link_col:
        logger.error("Could not find link_id column in GeoJSON streets data")
        return
    if not name_col:
        logger.error("Could not find name column in GeoJSON streets data")
        return
    logger.info(f"Using columns: LINK='{link_col}', NAME='{name_col}'")

    # 8) Process POIs
    results = []
    for lid in poi_ids:
        mask = calles[link_col].astype(str) == str(lid)
        street = calles.loc[mask]
        if street.empty:
            logger.warning(f"WARNING: LINK_ID {lid} not found")
            continue

        geom = street.geometry.values[0]
        if not isinstance(geom, LineString) or geom.is_empty or not geom.is_valid:
            logger.warning(f"WARNING: Invalid geometry for LINK_ID {lid}")
            continue

        # Calculate midpoint of the street segment
        midpoint = geom.interpolate(geom.length / 2)
        lon, lat = midpoint.x, midpoint.y
        street_name = str(street[name_col].values[0])

        results.append({
            'link_id': lid,
            'st_name': street_name,
            'lat': lat,
            'lon': lon
        })

    # 9) Export CSV with coordinates
    out_csv = 'POI_with_coords_limited.csv'
    try:
        with open(out_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['link_id', 'st_name', 'lat', 'lon'])
            writer.writeheader()
            writer.writerows(results)
        logger.info(f"CSV saved to {out_csv}")
    except Exception as e:
        logger.error(f"Error writing output CSV: {e}")

    # 10) Download images and mark POIs
    for item in results:
        img = get_sat_tile(item['lat'], item['lon'])
        if img is None:
            logger.error(f"Could not download image for POI {item['link_id']}")
            continue

        # Draw red marker at center of image
        draw = ImageDraw.Draw(img)
        cx, cy = TILE_SIZE//2, TILE_SIZE//2
        r = 8  # Marker radius
        draw.ellipse((cx-r, cy-r, cx+r, cy+r), outline='red', width=3)

        # Add text label with street name
        draw.text((cx+r+5, cy), item['st_name'], fill='green', anchor='lt')

        # Save image
        outname = os.path.join(output_dir, f"tile_{item['link_id']}.png")
        img.save(outname)
        logger.info(f"Saved {outname} for POI {item['link_id']} on {item['st_name']}")

if __name__ == '__main__':
    main()