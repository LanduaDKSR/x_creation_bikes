import pandas as pd
import geopandas as gpd
import streamlit as st
import ast
from shapely import centroid
from shapely.geometry import LineString
from shapely.wkt import loads
from shapely.ops import unary_union
from typing import List

@st.cache_data
def load_data() -> (gpd.GeoDataFrame, pd.DataFrame, gpd.GeoDataFrame):
    plz = gpd.read_file('data/raw/plz_areas.geojson')
    #edge_data = pd.read_csv('data/raw/edge_data.csv')
    edge_data = pd.read_parquet('data/raw/edge_data_reduced.parquet.gz')
    edge_data['shape'] = edge_data['shape'].apply(lambda x: ast.literal_eval(x))
    #edge_data['geo'] = edge_data['shape'].apply(lambda x: LineString(x['coordinates']))
    schools = pd.read_csv('data/raw/schools.csv')
    schools['geometry'] = schools['geometry'].apply(lambda x: centroid(loads(x)))
    schools = gpd.GeoDataFrame(schools, geometry='geometry' ,crs="EPSG:4326")

    return plz, edge_data, schools


def get_prio(edge_data: pd.DataFrame, length: float, geometry: dict, option: str, plz: gpd.GeoDataFrame, Innenstadt: List[int]) -> gpd.GeoDataFrame:
    length = length#*1000
    shortlist = edge_data[(edge_data['edge_length'] > 0.01) & (edge_data['cycle_roads']==0)]
    shortlist = shortlist.sort_values('count',ascending=False,ignore_index=True)
    shortlist['shape'] = shortlist['shape'].apply(lambda x: LineString(x['coordinates']))

    if option == 'Main roads':
        shortlist = shortlist[shortlist['main_roads']==1].reset_index(drop=True)
    elif option == 'Small roads':
        shortlist = shortlist[shortlist['small_roads']==1].reset_index(drop=True)
    elif option == 'Inner city':
        geometry = unary_union(list(plz[plz['name'].isin(Innenstadt)]['geometry']))
    elif option == 'Outskirts':
        geometry = unary_union(list(plz[~plz['name'].isin(Innenstadt)]['geometry']))
    elif option == 'School children':
        shortlist = shortlist[shortlist['school_distance'] < 0.3].reset_index(drop=True)

    try:    
        shortlist = shortlist[[x.within(geometry) for x in shortlist['shape']]].reset_index(drop=True)
    except:
        pass

    minimum = shortlist['edge_length'].min()
    drop_list = []
    for i in range(len(shortlist.index)):
        if shortlist['edge_length'][i] < length: 
            length -= shortlist['edge_length'][i]
        else:
            drop_list.append(i)
        if length < minimum:
            break
    try:
        shortlist = shortlist.head(i)
        shortlist = shortlist.drop(index=drop_list).reset_index(drop=True)
        shortlist = gpd.GeoDataFrame(shortlist, geometry='shape', crs='EPSG:4326')
        shortlist.reset_index(inplace=True,names='priority')
        shortlist['priority'] +=1
    except:
        shortlist = gpd.GeoDataFrame(pd.DataFrame({'shape':[], 'name':[], 'priority':[], 'edge_length':[]}), geometry='shape', crs='EPSG:4326')
    return shortlist
