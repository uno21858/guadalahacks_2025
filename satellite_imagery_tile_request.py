import requests
import math


def lat_lon_to_tile(lat, lon, zoom):
    """
    Convert latitude and longitude to tile indices (x, y) at a given zoom level.
    
    :param lat: Latitude in degrees
    :param lon: Longitude in degrees
    :param zoom: Zoom level (0-19)
    :return: Tuple (x, y) representing the tile indices
    """
    # Convert latitude and longitude to radians
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    
    # Calculate n (number of tiles at the given zoom level)
    n = 2.0 ** zoom
    
    # Calculate x and y tile indices
    x = int((lon_rad - (-math.pi)) / (2 * math.pi) * n)
    y = int((1 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2 * n)
    
    return (x, y)

def tile_coords_to_lat_lon(x, y, zoom):
    n = 2.0 ** zoom
    lon_deg = x / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1-2 * y/n)))
    lat_def = math.degrees(lat_rad)
    return (lat_def, lon_deg)

def get_tile_bounds(x, y, zoom):
    lat1, lon1 = tile_coords_to_lat_lon(x,y,zoom)
    lat2, lon2 = tile_coords_to_lat_lon(x+1, y, zoom)
    lat3, lon3 = tile_coords_to_lat_lon(x+1,y+1,zoom)
    lat4, lon4 = tile_coords_to_lat_lon(x,y+1,zoom)
    return (lat1, lon1), (lat2, lon2), (lat3, lon3), (lat4, lon4)

def create_wkt_polygon(bounds):
    (lat1, lon1), (lat2, lon2), (lat3, lon3), (lat4, lon4) = bounds
    wkt = f"POLYGON(({lon1} {lat1}, {lon2} {lat2}, {lon3} {lat3}, {lon4} {lat4}, {lon1} {lat1}))"
    return wkt



def get_satellite_tile(lat,lon,zoom,tile_format,api_key):

    x,y =lat_lon_to_tile(lat, lon, zoom)


    # Construct the URL for the map tile API
    url = f'https://maps.hereapi.com/v3/base/mc/{zoom}/{x}/{y}/{tile_format}&style=satellite.day&size={tile_size}?apiKey={api_key}'

    # Make the request
    response = requests.get(url)

    # Check if the request was successful
    if response.status_code == 200:
        # Save the tile to a file
        with open(f'satellite_tile.{tile_format}', 'wb') as file:
            file.write(response.content)
        print('Tile saved successfully.')
    else:
        print(f'Failed to retrieve tile. Status code: {response.status_code}')

    bounds = get_tile_bounds(x,y, zoom)
    wkt_polygon = create_wkt_polygon(bounds)
    return wkt_polygon

##########################################################
### EXECUTION
##########################################################
# Define the parameters for the tile request
api_key = 'API'
latitude = 51.94347 
longitude = 8.51692 
zoom_level = 16  # Zoom level
tile_size = 512  # Tile size in pixels
tile_format = 'png'  # Tile format

# Execute request and save tile
wkt_bounds = get_satellite_tile(latitude,longitude,zoom_level,tile_format,api_key)
print(wkt_bounds)

