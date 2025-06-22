import requests
import pandas as pd
import json
import numpy as np
import geocoder
import math
from typing import Tuple
import time
import streamlit as st

with open('keys.json', 'r') as KeysFile:
    data = json.load(KeysFile)

FR24Key = data['FR24Key']
DEFAULT_LOCATION = [40.69131095346322, -74.38958047019509]
EARTH_RADIUS = 6371e3


def getLocation():
    lat, lon = geocoder.ip('me').latlng
    return lat, lon

def getBounds(radius_miles: float) -> Tuple[float, float, float, float]:
    """
    Return the (north_lat, south_lat, east_lon, west_lon) that bound
    a circle of *radius_m* centred on (lat_deg, lon_deg).

    All angles are in decimal degrees.  Longitudes are normalized to [-180, 180].
    """
    lat_deg, lon_deg = getLocation()
    EARTH_RADIUS_M = 6378137  # mean radius in metres (WGS-84)

    radius_meters = radius_miles * 1609.34 
    # Convert centre point to radians
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)

    # Angular distance on the Earth’s surface
    ang_dist = radius_meters / EARTH_RADIUS_M      # radians

    # Latitude bounds are simple great-circle shifts north/south
    lat_north = lat + ang_dist
    lat_south = lat - ang_dist

    # Longitude bounds shrink with latitude (meridians converge toward the poles)
    # guard against cos(lat)=0 near the poles
    if abs(math.cos(lat)) < 1e-12:
        # At the poles every direction is “east/west”; set lon bounds to full range
        lon_east = math.pi
        lon_west = -math.pi
    else:
        delta_lon = math.asin(math.sin(ang_dist) / math.cos(lat))
        lon_east = lon + delta_lon
        lon_west = lon - delta_lon

    # Convert back to degrees and normalise longitudes to [-180, 180]
    def wrap(deg: float) -> float:
        """Wrap longitude from radians into the interval [-180, 180]°."""
        deg = math.degrees(deg)
        return (deg + 180) % 360 - 180

    north = str(round(math.degrees(lat_north), 3))
    south = str(round(math.degrees(lat_south), 3))
    east  = str(round(wrap(lon_east), 3))
    west  = str(round(wrap(lon_west), 3))

    return ','.join([north, south, west, east])


def getDistance(lat2, lon2):
    lat1, lon1 = getLocation()
    phi1 = lat1*np.pi/180           # φ, λ in radians
    phi2 = lat2*np.pi/180
    del_phi = (lat2 - lat1)*np.pi/180
    del_lambda = (lon2 - lon1)*np.pi/180

    a = np.sin(del_phi/2)*np.sin(del_phi/2) + \
        np.cos(phi1)*np.cos(phi2)*np.sin(del_lambda/2)*np.sin(del_lambda/2)

    c = 2*np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    d = EARTH_RADIUS*c;            # in meters
    return d/1600                  # convert to miles

def getFlightsFR24(miles):
    url = "https://fr24api.flightradar24.com/api/live/flight-positions/full"
    params = {'bounds': getBounds(miles), 'altitude_ranges': '50-60000', 'categories': 'P,C,M,J,T'}
    headers = {'Accept': 'application/json',
    'Accept-Version': 'v1',
    'Authorization': f'Bearer {FR24Key}'
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json().get('data', [])
        df = pd.DataFrame(columns=['Airline', 'FlightNo', 'Type', 'Orig', 'Dest', 'Alt', 'Lat', 'Lon', 'Track', 'Timestamp', 'ETA'])
        for case in data:
            new_case = {'Airline': case.get('painted_as', ''),
                        'FlightNo': case.get('flight', ''),
                        'Type': case.get('type', ''),
                        'Orig': case.get('orig_iata', ''),
                        'Dest': case.get('dest_iata', ''),
                        'Alt': case.get('alt', ''),
                        'Lat': case.get('lat', ''),
                        'Lon': case.get('lon', ''),
                        'Track': case.get('track', ''),
                        'Timestamp': case.get('timestamp', ''),
                        'ETA': case.get('eta', '')
                        }
            df.loc[len(df)] = new_case
        
        df['Distance'] = round(getDistance(df['Lat'], df['Lon']), 1)
        return df.dropna(subset=['Airline', 'FlightNo', 'Orig']).sort_values('Distance')
        
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
    except Exception as err:
        print(f"An error occurred: {err}")

df = getFlightsFR24(miles=20)



st.set_page_config(page_title="Flights Overhead", layout="wide")

st.title("Flights Overhead")

for row in df.itertuples():
    st.write(f"{row.Airline} {row.Type} from {row.Orig} to {row.Dest} at {row.Alt}ft {row.Distance} miles away")
    time.sleep(2)
