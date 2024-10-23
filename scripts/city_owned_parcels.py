import pandas as pd
import geopandas as gpd
import folium
import requests
import json
from shapely.geometry import Polygon
import os

print(os.getcwd()) 

from pathlib import Path

# Get the absolute path of the current script's directory
script_dir = Path(__file__).parent

# Construct the relative path to the file
file_path = script_dir / 'scripts' / 'myfile.txt'

#Load function for locating and filtering data within our NL boundary
def within_nl(df):
    within_list = []
    for x in df['geometry']:
        withinQ = x.within(test['geometry'].values[0])
        #print( withinQ )
        within_list.append(withinQ)

    # update values in the that column, values: True/False
    df['withinNL'] = within_list

    df_nl = df[df['withinNL']==True].reset_index(drop=True)

    return df_nl

#Open NL boundary shapefile
with open("shapefiles/northlawndale_census_geography.json",'r') as file:
    test = json.load(file)

test = gpd.GeoDataFrame.from_features(test['features'],crs='EPSG:4326')
test['Label'] = 'North Lawndale'
test['Description'] = 'Inclusive Census Tract Boundary'
test

# Pull data from Chicago Block Builder 
r = requests.get('https://datamade.carto.com/api/v2/sql?q=SELECT%20cartodb_id%2Caddress%2Czip_code%2Ccommunity_%2Cparcel%2Csqft%2Cward_2023%2Czoning%2Cstatus_fla%2Csold_date%2Cvalue_1%2Creason_1%2Creason_2%2Capplication_use%2Csale_program%2Cgrouped_parcels%2Capplication_deadline%2Capply_url%2C%20ST_asGeoJSON(the_geom)%20as%20geom%20FROM%20cbb_cols_data_live%20&api_key=l18oJEbswxpG8XYUG5DyPw')
data = r.json()

#Load the json as a dataframe
chi_parcels = pd.json_normalize(data['rows'])

#Filter city owned lots to relevant statuses, either a accepting applications, seeing, interest, having recieved applications, or no status. Filter out Missing Middle properties because they have non-applicable conditions for purchase.
chi_avail = chi_parcels[(chi_parcels['status_fla']=='')|(chi_parcels['status_fla']=='Application(s) Received')|(chi_parcels['status_fla']=='Interest')|(chi_parcels['status_fla']=='Offered')|(chi_parcels['status_fla']=='Apply')&(chi_parcels['application_use']!='Missing Middle')].reset_index(drop=True)

#Reformat the geom column (currently in json) to make it geopandas accessible (geometry/polygon)
chi_avail['geom'] = chi_avail['geom'].apply(json.loads)
pars = [Polygon(item['coordinates'][0][0]) for item in chi_avail['geom']]
chi_avail['geometry'] = pars

#Turn it into a geodataframe for mapping
chi_avail_geo = gpd.GeoDataFrame(chi_avail,geometry='geometry')
chi_avail_geo = chi_avail_geo.set_crs(crs='EPSG:4326')

#Filter all chicago parcels down to just those available in North Lawndale
parcels_nl = within_nl(chi_avail_geo)

#Create a copy of parcels_nl to buffer the geometries for merging touching parcels
test2 = parcels_nl.copy()
test2['geometry'] = test2.geometry.buffer(0.0001)

#Merge parcels that touch with buffered boundarie3s 
merged_parcels = gpd.geoseries.GeoSeries([geom for geom in test2.geometry.unary_union.geoms])
merged_parcels = merged_parcels.reset_index().rename(columns={'index':'merged_parcel_id'})

#Get rid of buffer applied to individual parcels above 
merged_parcels[0] = merged_parcels[0].buffer(-0.0001)
merged_parcels = merged_parcels.set_crs(crs='EPSG:4326')

#Calculate area in meters, convert to acres, of merged parcels 
merged_parcels = merged_parcels.to_crs({'proj':'cea'})
merged_parcels['area'] = merged_parcels[0].area/4047 #takes square meters area and divides by 4047 to give you acres 

#Make a folium map of both the individual and merged parcel layers, save to html 
m = parcels_nl.explore(name='available parcels',tooltip=['address','status_fla'],popup=['status_fla','zoning','reason_1','application_use','value_1'])
merged_layer = merged_parcels.explore(m=m,name='merged parcels')

folium.LayerControl().add_to(m)

m.save("docs/index.html")

m