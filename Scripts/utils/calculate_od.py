"""Compatibility helpers; new UI uses bioze.routing directly."""

import geopandas as gpd
import h3
import pandas as pd
from shapely.geometry import Point, Polygon

from bioze.routing import load_road_graph, road_distances


def cell_to_shapely_polygon(h3_index):
    return Polygon([(lon, lat) for lat, lon in h3.cell_to_boundary(h3_index)])


def cell_to_shaply_point(h3_index):
    lat, lon = h3.cell_to_latlng(h3_index)
    return Point(lon, lat)


def loi_to_gdf(loi):
    result = loi.copy()
    result["geometry"] = result.hex9.map(cell_to_shaply_point)
    return gpd.GeoDataFrame(result, geometry="geometry", crs=4326)


def calculate_od_matrix(farm_gdf, loi_gdf, cost_per_km, frequency_per_day=1, lifetime_in_days=1):
    """Legacy cost adapter. Preserve farm IDs, omit unreachable pairs."""

    def coordinates(frame):
        geo = frame.to_crs(4326)
        if not geo.geometry.geom_type.eq("Point").all():
            geo = geo.to_crs(28992)
            geo.geometry = geo.geometry.centroid
            geo = geo.to_crs(4326)
        return pd.DataFrame({"lon": geo.geometry.x, "lat": geo.geometry.y}, index=geo.index)

    distances = road_distances(coordinates(farm_gdf), coordinates(loi_gdf), load_road_graph())
    factor = cost_per_km * frequency_per_day * lifetime_in_days
    if factor < 0:
        raise ValueError("Transport costs must be nonnegative.")
    return {pair: value * factor for pair, value in distances.items()}, list(loi_gdf.index)
