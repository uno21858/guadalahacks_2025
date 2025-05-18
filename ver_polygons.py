import os
import geopandas as gpd
import matplotlib.pyplot as plt
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_polygons(path):
    if not os.path.exists(path):
        logger.error(f"El archivo no existe: {path}")
        return None
    try:
        gdf = gpd.read_file(path)
        if gdf.crs is None:
            gdf.set_crs('EPSG:4326', inplace=True)
        logger.info(f"Se cargaron {len(gdf)} polígonos desde {path}")
        return gdf
    except Exception as e:
        logger.error(f"Error al cargar los polígonos: {e}")
        return None

def plot_polygons(gdf, output_path=None):
    fig, ax = plt.subplots(figsize=(12, 10))
    gdf.plot(ax=ax, facecolor='none', edgecolor='blue', linewidth=1)
    for idx, row in gdf.iterrows():
        if 'L11_Tile_ID' in row:
            centroid = row.geometry.centroid
            ax.text(centroid.x, centroid.y, str(row['L11_Tile_ID']), fontsize=7, ha='center', color='black')
    ax.set_title("Visualización de Polígonos (L11 Tiles)")
    ax.set_xlabel("Longitud")
    ax.set_ylabel("Latitud")
    ax.set_aspect('equal')
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=300)
        logger.info(f"Mapa guardado en: {output_path}")
    else:
        plt.show()
    plt.close()

def main():
    # Ruta al archivo GeoJSON con los polígonos
    polygons_path = "DBs/HERE_L11_Tiles.geojson"
    gdf = load_polygons(polygons_path)
    if gdf is not None:
        plot_polygons(gdf)

if __name__ == '__main__':
    main()