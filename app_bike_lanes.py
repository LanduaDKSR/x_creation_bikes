import streamlit as st
import pandas as pd
import numpy as np
import geopandas as gpd
import ast
import folium
from streamlit_folium import st_folium, folium_static
from streamlit_keplergl import keplergl_static
from keplergl import KeplerGl
from PIL import Image
from shapely import centroid
from shapely.geometry import LineString
from shapely.wkt import loads
from shapely.ops import unary_union
from src import count_config

st.set_page_config(layout="wide")

image = Image.open('data/raw/Logo.png')
config = count_config.config

Innenstadt = [55118, 55116, 55122, 55131]

base_zoom = 13
base_lat = 49.99
base_lon = 8.26

divider_color = 'red'

@st.cache_data
def load_data():
    plz = gpd.read_file('data/raw/plz_areas.geojson')
    edge_data = pd.read_csv('data/raw/edge_data.csv')
    edge_data['shape'] = edge_data['shape'].apply(lambda x: ast.literal_eval(x))
    #edge_data['geo'] = edge_data['shape'].apply(lambda x: LineString(x['coordinates']))
    schools = pd.read_csv('data/raw/schools.csv')
    schools['geometry'] = schools['geometry'].apply(lambda x: centroid(loads(x)))
    schools = gpd.GeoDataFrame(schools, geometry='geometry' ,crs="EPSG:4326")

    return plz, edge_data, schools

def get_prio(edge_data, length, geometry, option):
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


plz, edge_data, schools = load_data()
lat = base_lat
lng = base_lon
zoom = base_zoom
geometry = {}
geometry_2 = {}


header1, header2 = st.columns([5,1])
with header1:
    st.write("""
    # X-Creation
    ### Bike Lanes
    How can we improve our cities' cycability?  
    This tool shows a quantitative approach that helps urban planners to find the most suitable streets for new cycle paths. 
    """)

with header2:
    st.image(image)

st.subheader("", divider=divider_color)

choice12, choice3 = st.columns([2,1])

with choice12:
    choice_text1, choice_text2 = st.columns([1,1])
    with choice_text1:
        st.write("""
            #### :red[1]
            Is there a financial, political or any other limitation on the new bike infrastructure? Use the slider to decide on a total length of new cycle paths to be built.
            """)

    with choice_text2:
        st.write("""
            #### :red[2]
            _(optional)_
            Should the results be focused on a specific user group or street type? 
            """)

    choice1, choice2 = st.columns([1,1])

    with choice1:
        st.write("""
                 """)
        length = st.slider('Length of new bike lanes [km]', 1, 30, 5, 1)

    with choice2:
        option = st.selectbox(
                "Focus",
                ("School children", "Inner city", "Outskirts", "Main roads", "Small roads"),
                index=None,
                placeholder="is there a particular focus?"
                )

with choice3:
    st.write("""
        #### :red[3]
        _(optional)_ Do you want to limit your results on a specific neighborhood?
        Click on any area in the map for filtering.
        """)

    map = folium.Map([base_lat, base_lon], zoom_start=10)
    popup = folium.GeoJsonPopup(
        fields=["name", "plz_name"],
        localize=True,
        #labels=True,
        #style="background-color: yellow;",
    )
    style_function = None#lambda feature: {'fillColor': ("green" if "e" in str(feature["properties"]["name"]).lower() else "#ffff00")}

    folium.GeoJson(plz, popup=popup, style_function=style_function, popup_keep_highlighted=True).add_to(map)
    st_data = st_folium(map, height=250, returned_objects=["last_active_drawing"], use_container_width=True)

    try:
        selection = st_data['last_active_drawing']['properties']['name']
        coords = st_data['last_active_drawing']['properties']['geo_point_2d']
        geometry = plz[plz['name']==selection]
        geometry.reset_index(drop=True, inplace=True)
        geometry = geometry['geometry'][0]
        lat = coords['lat']
        lng = coords['lon']
        if lat != base_lat:
            zoom = 12
    except:
        lat = base_lat
        lng = base_lon
        zoom = base_zoom
        geometry = {}

    b1, b2 = st.columns([2,3])
    with b2:
        if st.button("Deselect"):
            lat = base_lat
            lng = base_lon
            zoom = base_zoom
            geometry = {}

st.subheader("", divider=divider_color)


col1, col2, col3 = st.columns([1,8,1])

with col2:

    st.write("""
    #### Algorithm recommendation   
    These are the streets with the highest potential for new cycle paths:
    """)


    shortlist = get_prio(edge_data, length, geometry, option)
    print(len(shortlist.index))

    col11, col12 = st.columns([3,1])
    with col11:
        map_2 = folium.Map([lat, lng], zoom_start=zoom)

        popup_2 = folium.GeoJsonPopup(
        fields=["name", "priority", "edge_length"],
        #localize=True,
        labels=True,
        #style="background-color: yellow;",
        )
        if len(shortlist.index) > 0:
            folium.GeoJson(shortlist, popup=popup_2, style_function=lambda feature: {"weight": 4, "color": "red"}).add_to(map_2)       
        if option == "School children":
            folium.GeoJson(schools).add_to(map_2)
        if geometry != {}:
            folium.GeoJson(geometry, style_function=lambda feature: {'fillColor': 'yellow', 'color': 'black', 'weight': 1, "dashArray": "5, 5"}).add_to(map_2)
        
        #st_folium(map_2, height=500, width=800, returned_objects=None)
        folium_static(map_2)#, height=500, width=800)

    with col12:
        #st.dataframe(edge_counts.sort_values('count',ascending=False).head())
        st.dataframe(shortlist[['priority','name','edge_length']], hide_index=True, use_container_width=True)#.drop('shape',axis=1))


    st.subheader("", divider=divider_color)
    st.write("""
    #### The status quo
    Where do these recommendations come from?
    * Different data sets were used in the algorithm that provides the highest cycle potentials as shown above. 
    * One of them was gathered from IoT-devices within rental bikes.
    * The analysis of the rider path results in macroscopic movement patterns. 
    * The map below shows these moving patterns for the month of April '24 in the german city Mainz. 
     
    Feel free to explore the data inside the map.
    """)

    map_0 = KeplerGl(height=400, data={'edges': edge_data}, config=config)
    keplergl_static(map_0)

st.subheader("", divider=divider_color)

st.write("""
© 2024 DKSR GmbH
""")