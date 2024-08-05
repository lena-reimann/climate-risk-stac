#%% NOTES %%#
#

import pystac
from pystac import RelType
from pystac.extensions.scientific import ScientificExtension
from pystac.extensions.projection import ProjectionExtension
import pandas as pd
from datetime import datetime
import numpy as np
import os
#import json

# File paths
dir = 'C:/Users/lrn238/OneDrive - Vrije Universiteit Amsterdam/Documents/GitHub/climate-risk-stac/'
haz = 'csv/hazard.csv'
exv = 'csv/expvul.csv'

# Read data sheets
hazard = pd.read_csv(haz, encoding='utf-8')
expvul = pd.read_csv(exv, encoding='utf-8')

# Function to parse year range
def parse_year_range(year_str):
     # If the string contains a dash, it's a range
    if '-' in year_str:
        start, end = year_str.split('-')
        
        # Determine the length of the start and end strings to parse correctly
        if len(start) == 4 and len(end) == 4:
            start_year, end_year = int(start), int(end)
            return datetime(start_year, 1, 1), datetime(end_year, 12, 31)
        elif len(start) == 4 and len(end) == 3:
            start_year = int(start)
            end_year = datetime.now().year
            end_month = datetime.now().month
            end_day = datetime.now().day
            return datetime(start_year, 1, 1), datetime(end_year, end_month, end_day)
        # if start date BC (can handle any year until 10000 BC, but not year 0):
        elif len(start) > 4 and len(end) == 4:
            start_year = int(start.replace('BC', '')) - 1 # 1 BC is year 0; 2 BC is year 1 etc.
            end_year = int(end)
            return datetime(start_year, 1, 1), datetime(end_year, 12, 31)
        else:
            raise ValueError("Invalid year range format")
    
    # If there's no dash, it's a single year
    else:
        if len(year_str) == 4:
            year = int(year_str)
            return datetime(year, 1, 1), datetime(year, 12, 31)
        else:
            raise ValueError("Invalid year format")
        
# Function to make keywords based on subcategory and risk data type
def parse_keywords(subc, rdata):
    # separate strings
    keyw = subc.split(',') if ',' in subc else [subc]
    # use rdata if expvul
    keywords = keyw if rdata == 'hazard' else [rdata, subc]
    print(f"new keywords: {keywords}")
    return keywords

# Function to update existing keywords
def update_keywords(ext_key, keywords):
    ext_key = set(ext_key)
    # Add missing keywords from the existing keywords list
    for keyword in keywords:
        ext_key.add(keyword)
        # update keywords
        upd_key = list(ext_key)
    return upd_key

# Function to update providers ## DOES NOT WORK YET ##
def update_providers(provider1, provider2):
    # check whether both providers are equal
    print(provider1)
    print(provider2)
    check=(
        provider1 == provider2 #and
        #provider1[1] == provider2[1] and
        #provider1[2] == provider2[2]
    )
    if not check:
        providers = [provider1, provider2]
    else:
        providers = provider1
    return providers

# Create the main catalog
catalog_main = pystac.Catalog(
    id="climate-risk-data",
    title="Climate Risk Data",
    description="Community catalog containing datasets for the three risk drivers Hazard, Exposure, and Vulnerability."
)

# Function to create collections and items
def create_catalog_from_csv(indicator, catalog_main, dir):
    for row_num in range(len(indicator)):
        item = indicator.iloc[row_num]
        
        # Extract values from the row
        catalog_id = item['catalog']
        category_id = item['category']
        
      
        ## CATALOGS ##
        # Create or retrieve the first-level catalog
        if catalog_id not in [cat.id for cat in catalog_main.get_children()]:
            catalog1 = pystac.Catalog(id=catalog_id, 
                                      title=catalog_id.capitalize(), 
                                      description=catalog_id) #adjust here once it works
            catalog_main.add_child(catalog1)
        else:
            catalog1 = catalog_main.get_child(catalog_id)

        # Create or retrieve the second-level catalog
        if category_id not in [cat.id for cat in catalog1.get_children()]:
            catalog2 = pystac.Catalog(id=category_id, 
                                      title=category_id.capitalize(), 
                                      description=category_id) #adjust here once it works
            catalog1.add_child(catalog2)
        else:
            catalog2 = catalog1.get_child(category_id)   
        

        # Process bbox (needed for collections and items)
        bbox = item['bbox']
        bbox_list = [float(coord.strip()) for coord in bbox.split(',')]

        # Process temporal resolution ## this needs to be changed to account for the total range of all items ##
        start, end = parse_year_range(str(item['temporal_resolution']))

        ## COLLECTIONS ##
        # combine title and short title
        title_collection = (item['title_collection'] + ' (' + item['title_short'] + ')' if not pd.isna(item['title_short'])
                            else (item['title_collection'])
                            )

        # make keywords
        keywords = parse_keywords(item['subcategory'], item['risk_data_type'])
        
        # Create or retrieve the collection 
        if title_collection not in [col.id for col in catalog2.get_children()]:
                    
            # create basic collection
            collection = pystac.Collection(
                id=title_collection,
                title=title_collection,
                description= str(item['description_collection']),#description_collection,
                extent=pystac.Extent(
                    spatial=pystac.SpatialExtent([bbox_list]), # needs to be updated based on all items in the collection
                    temporal=pystac.TemporalExtent([[start, end]]), # needs to be updated based on all items in the collection
                ),
                license=item['license'],
                keywords=keywords, # add further if needed
                extra_fields={
                    'risk data type': item['risk_data_type'],
                    'subcategory': item['subcategory']                    
                }
            )

            # Create and add a Provider         
            provider = pystac.Provider(
                 name=item['provider'],
                 roles= item['provider_role'], # change role: pystac.provider.ProviderRole.HOST ## DOES NOT WORK ##
                 url=item['link_website']
                )
            collection.providers = [provider]
            
            catalog2.add_child(collection)

        else:
            # retrieve collection
            collection = catalog2.get_child(title_collection)
            
            # Update keywords
            # retrieve existing keywords
            key_col = collection.keywords
            # update keywords
            new_key = update_keywords(key_col, keywords)
            # add to collection
            collection.keywords = new_key

            # # Update providers -> relevant when more than one weblink per collection provided: needs to be fixed to account for the option that several providers are already present. These need to be compared one by one
            # # retrieve existing provider
            # provider1 = collection.providers
            # # create potential new provider from current row
            # provider2 = pystac.Provider(
            #      name=item['provider'],
            #      roles=item['provider_role'],
            #      url=item['link_website']
            #     )
            # new_pro = update_providers(provider1, provider2)
            # # add to collection
            # collection.providers = new_pro
   
        print('collection ', row_num, ' ', title_collection, ' successful')

        ## ITEMS ##
       
        # define item attributes that can deviate per item
        temporal_resolution = f"{item['temporal_resolution']} ({item['temporal_interval']})" if np.nan_to_num(item['temporal_interval']) else f"{item['temporal_resolution']}"
        scenarios = item['scenarios'] if np.nan_to_num(item['scenarios']) else None
        spatial_resolution = f"{item['spatial_resolution']} {item['spatial_resolution_unit']}" if np.nan_to_num(item['spatial_resolution_unit']) else f"{item['spatial_resolution']}"
        analysis_type = item['analysis_type'] if np.nan_to_num(item['analysis_type']) else None
        underlying_data = item['underlying_data'] if np.nan_to_num(item['underlying_data']) else None
        code =  f"{item['code_type']} (link in Additional Resources)" if np.nan_to_num(item['code_link']) else None
        usage_notes = item['usage_notes'] if np.nan_to_num(item['usage_notes']) else None
        
        # condition for publication
        if str(item['publication_link']).startswith('10.'):
            publication = f"{item['publication_type']} (DOI below)" 
        elif np.nan_to_num(item['publication_link']): 
            publication = f"{item['publication_type']} (link in Additional Resources)"
        else:
            publication = None

        # Create basic item
        item_stac = pystac.Item(
            id=item['title_item'],
            geometry=None,  # Add geometry if available
            bbox=bbox_list,
            datetime=None, #datetime.now(),
            start_datetime=start,
            end_datetime=end,
            properties={
                'title': item['title_item'],
                'description': item['description_item'],
                'risk data type': item['risk_data_type'],
                'subcategory': item['subcategory'],
                'spatial scale': item['spatial_scale'],
                'reference period': item['reference_period'],
                'temporal resolution': temporal_resolution, # combination of resolution and interval
                'scenarios': scenarios,
                'data type': item['data_type'],
                'data format': item['format'],
                'coordinate system': str(item['coordinate_system']),
                'spatial resolution': spatial_resolution, # combination of resolution and unit
                'data calculation type': item['data_calculation_type'],
                'analysis type': analysis_type,
                'underlying data': underlying_data,
                'publication': publication,
                'code': code,
                'usage notes': usage_notes
            }
            # extra_fields={ # are part of the json, but not shown in the browser
            #         'subcategory': str(item['subcategory']), #remove str() again once subcategory fixed
            #         'risk data type': item['risk_data_type']
            #     }
        )

        # add projection extension
        proj_ext = ProjectionExtension.ext(item_stac, add_if_missing=True)
        # Add projection properties
        proj_ext.epsg = 4326
        proj_ext.wkt2 = "GEOGCRS[...]"
        proj_ext.proj_bbox = [125.0, 10.0, 126.0, 11.0]
        proj_ext.shape = [1000, 1000]
        proj_ext.transform = [
                0.1, 0, 125.0,
                0, -0.1, 11.0,
                0, 0, 1
        ]

        # Publication: Add scientific extension if DOI is present
        if str(item['publication_link']).startswith('10.'):
            print("doi available")
            sci_ext = ScientificExtension.ext(item_stac, add_if_missing=True)
            sci_ext.doi = item['publication_link'] # adjust condition here for links that are not dois
        elif np.nan_to_num(item['publication_link']):
            print("weblink available")
            link = pystac.Link(
                rel="cite-as",  # Relationship of the link
                target=item['publication_link'],  # Target URL
                title="Publication link",  # Optional title
                )
            item_stac.add_link(link)

        # Code: add link if available
        if code != None:
            print("code available")
            link = pystac.Link(
                rel="cite-as",  # Relationship of the link
                target=item['code_link'],  # Target URL
                title="Code link",  # Optional title
                )
            item_stac.add_link(link)

        # Add item to collection
        collection.add_item(item_stac)
        
        # confirmation item added
        print('item ', row_num, ' ', item['title_item'], ' successful')
    
    # update collection properties based on all items belonging to the collection ## NOT FINISHED YET ##
    #collection_interval = sorted([collection_item.datetime, collection_item2.datetime])
    #temporal_extent = pystac.TemporalExtent(intervals=[collection_interval])


    catalog_main.describe()

    # Normalize hrefs and save the catalog
    catalog_main.normalize_hrefs(os.path.join(dir, "stac"))
    catalog_main.save(catalog_type=pystac.CatalogType.SELF_CONTAINED)
    #catalog_main.save(catalog_type=pystac.CatalogType.RELATIVE_PUBLISHED)
   

# Create catalogs from both hazard and exposure-vulnerability CSVs
create_catalog_from_csv(hazard, catalog_main, dir)
#create_catalog_from_csv(expvul, catalog_main, dir)


# # Function to ensure directory exists
# def ensure_dir(file_path):
#     directory = os.path.dirname(file_path)
#     if not os.path.exists(directory):
#         os.makedirs(directory)

# # Ensure the directory exists
# ensure_dir(dir)


# # Ensure directories for all items
# for item in catalog_main.get_all_items():
#     item_href = item.get_self_href()
#     ensure_dir(item_href)

# # Save all items
# for item in catalog_main.get_all_items():
#     item.save_object(include_self_link=False)