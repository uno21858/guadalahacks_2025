import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString
import matplotlib.pyplot as plt
import glob
import os
from shapely.ops import linemerge
from shapely.geometry import MultiLineString


# ----------------------
# Rutas
# ----------------------
BASE_DIR = "data"
POIS_DIR = os.path.join(BASE_DIR, "POIs")
STREETS_NAV_DIR = os.path.join(BASE_DIR, "STREETS_NAV")

# ----------------------
# Leer STREETS_NAV
# ----------------------
streets_files = glob.glob(os.path.join(STREETS_NAV_DIR, "*.geojson"))
gdf_links = gpd.GeoDataFrame(pd.concat(
    [gpd.read_file(f) for f in streets_files],
    ignore_index=True),
    crs="EPSG:4326"
)

# Asegurar que LINK_ID sea string para evitar problemas de join
gdf_links["link_id"] = gdf_links["link_id"].astype(str)

# ----------------------
# Leer POIs
# ----------------------
pois_files = glob.glob(os.path.join(POIS_DIR, "*.csv"))
df_pois = pd.concat([pd.read_csv(f) for f in pois_files], ignore_index=True)
df_pois["LINK_ID"] = df_pois["LINK_ID"].astype(str)

# Filtrar solo los necesarios (con PERCFRREF válido)
df_pois = df_pois[df_pois["PERCFRREF"].notna() & df_pois["POI_ST_SD"].isin(["L", "R"])]
df_pois["PERCFRREF"] = pd.to_numeric(df_pois["PERCFRREF"], errors='coerce')

# ----------------------
# Unir POIs con LINKS
# ----------------------
merged = df_pois.merge(gdf_links[["link_id", "geometry"]], left_on="LINK_ID", right_on="link_id")

# ----------------------
# Calcular geometría de los POIs
# ----------------------
def get_point_along_link(row):
    geom = row["geometry"]

    # Si es MultiLineString, convertirlo en LineString
    if geom.geom_type == "MultiLineString":
        merged = linemerge(geom)
        if isinstance(merged, LineString):
            line = merged
        elif isinstance(merged, MultiLineString):
            line = list(merged.geoms)[0]  # tomar el primero
        else:
            return None
    elif isinstance(geom, LineString):
        line = geom
    else:
        return None

    perc = min(max(row["PERCFRREF"], 0), 1)
    point = line.interpolate(perc, normalized=True)

    try:
        if row["POI_ST_SD"] == "R":
            offset = line.parallel_offset(0.0001, 'right', join_style=2)
        elif row["POI_ST_SD"] == "L":
            offset = line.parallel_offset(0.0001, 'left', join_style=2)
        else:
            return point

        if offset.is_empty:
            return point
        elif isinstance(offset, LineString):
            return offset.interpolate(offset.length * perc)
        elif isinstance(offset, MultiLineString):
            return list(offset.geoms)[0].interpolate(list(offset.geoms)[0].length * perc)
        else:
            return point
    except Exception:
        return point

merged["geometry"] = merged.apply(get_point_along_link, axis=1)
gdf_pois = gpd.GeoDataFrame(merged, geometry="geometry", crs="EPSG:4326")

# ----------------------
# Visualizar
# ----------------------
fig, ax = plt.subplots(figsize=(12, 12))
gdf_links.plot(ax=ax, color="lightgray", linewidth=0.5)
gdf_pois.plot(ax=ax, color="red", markersize=8, alpha=0.7)
plt.title("Visualización de POIs calculados sobre red vial - CDMX")
plt.axis("equal")
plt.grid(True)
plt.show()
