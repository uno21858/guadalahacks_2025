import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Point, LineString, MultiLineString
from shapely.ops import linemerge
import glob
import os

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
gdf_links["link_id"] = gdf_links["link_id"].astype(str)

# 🔍 Filtrar calles MULTIDIGIT
multidig_links = gdf_links[gdf_links["MULTIDIGIT"] == "Y"]

# ----------------------
# Leer POIs
# ----------------------
pois_files = glob.glob(os.path.join(POIS_DIR, "*.csv"))
df_pois = pd.concat([pd.read_csv(f, low_memory=False) for f in pois_files], ignore_index=True)
df_pois["LINK_ID"] = df_pois["LINK_ID"].astype(str)
df_pois = df_pois[df_pois["PERCFRREF"].notna() & df_pois["POI_ST_SD"].isin(["L", "R"])]
df_pois["PERCFRREF"] = pd.to_numeric(df_pois["PERCFRREF"], errors='coerce')

# ----------------------
# Unir con geometrías de calles
# ----------------------
merged = df_pois.merge(gdf_links[["link_id", "geometry"]], left_on="LINK_ID", right_on="link_id")
merged["link_geometry"] = merged["geometry"]  # 🔒 Guardar copia antes de modificarla

# ----------------------
# Calcular geometría de cada POI
# ----------------------
def get_point_along_link(row):
    geom = row["link_geometry"]
    if geom.geom_type == "MultiLineString":
        merged_geom = linemerge(geom)
        if isinstance(merged_geom, LineString):
            line = merged_geom
        elif isinstance(merged_geom, MultiLineString):
            line = list(merged_geom.geoms)[0]
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
# Verificar si el POI está del lado correcto del link
# ----------------------
def verificar_lado_correcto(row):
    geom = row["geometry"]
    line = row["link_geometry"]

    if line.geom_type == "MultiLineString":
        merged = linemerge(line)
        if isinstance(merged, LineString):
            line = merged
        elif isinstance(merged, MultiLineString):
            line = list(merged.geoms)[0]
        else:
            return "indeterminado"

    start, end = list(line.coords)[0], list(line.coords)[-1]
    v_link = (end[0] - start[0], end[1] - start[1])
    v_poi = (geom.x - start[0], geom.y - start[1])
    cross = v_link[0] * v_poi[1] - v_link[1] * v_poi[0]

    lado_real = "L" if cross > 0 else ("R" if cross < 0 else "Eje")
    return "correcto" if lado_real == row["POI_ST_SD"] else "lado_incorrecto"

# Detectar violaciones por lado incorrecto
gdf_pois["lado_valido"] = gdf_pois.apply(verificar_lado_correcto, axis=1)

# ----------------------
# Diagnóstico
# ----------------------
print("POIs correctos:", len(gdf_pois[gdf_pois["lado_valido"] == "correcto"]))
print("POIs incorrectos:", len(gdf_pois[gdf_pois["lado_valido"] == "lado_incorrecto"]))
print("Geometrías vacías:", gdf_pois.geometry.is_empty.sum())
print("Geometrías nulas:", gdf_pois.geometry.isna().sum())

# ----------------------
# Visualización condicional
# ----------------------
if len(gdf_pois[gdf_pois["lado_valido"] == "correcto"]) > 0:
    fig, ax = plt.subplots(figsize=(12, 12))
    gdf_links.plot(ax=ax, color="lightgray", linewidth=0.5)
    gdf_pois[gdf_pois["lado_valido"] == "correcto"].plot(ax=ax, color="green", markersize=6, label="POIs correctos")
    gdf_pois[gdf_pois["lado_valido"] == "lado_incorrecto"].plot(ax=ax, color="blue", markersize=8, label="Lado incorrecto")
    plt.legend()
    plt.title("Verificación de lado de POIs respecto al Link")
    plt.axis("equal")
    plt.grid(True)
    plt.show()
else:
    print("❗ Todos los POIs están marcados como incorrectos. Revisa la lógica del lado.")