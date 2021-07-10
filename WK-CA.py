##---- libraries

import pandas as pd
import re
import datetime
import qgrid
from collections import defaultdict
from dateutil import relativedelta
import httplib2
from apiclient import errors
from apiclient.discovery import build
from oauth2client.client import OAuth2WebServerFlow
import requests
from bs4 import BeautifulSoup

##---- Insert here your Google Search Console

CLIENT_ID = ''
CLIENT_SECRET = ''
site = ''


##--- Insert here the date range

end_date = datetime.date.today()
start_date = end_date - relativedelta.relativedelta(months=3)

#---  Google Search Console API call


OAUTH_SCOPE = 'https://www.googleapis.com/auth/webmasters.readonly'
REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'

# Run through the OAuth flow and retrieve credentials
flow = OAuth2WebServerFlow(CLIENT_ID, CLIENT_SECRET, OAUTH_SCOPE, redirect_uri=REDIRECT_URI)
authorize_url = flow.step1_get_authorize_url()
print ('Go to the following link in your browser: ' + authorize_url)
code = input('Enter verification code: ').strip()
credentials = flow.step2_exchange(code)

# Create an httplib2.Http object and authorize it with our credentials
http = httplib2.Http()
http = credentials.authorize(http)

webmasters_service = build('webmasters', 'v3', http=http)


##----step5

def execute_request(service, property_uri, request):
    return service.searchanalytics().query(siteUrl=property_uri, body=request).execute()

request = {
    'startDate': datetime.datetime.strftime(start_date,"%Y-%m-%d"),
    'endDate': datetime.datetime.strftime(end_date,'%Y-%m-%d'),
    'dimensions': ['page','query'],
    'rowLimit': 25000 #up to 25.000 urls
}

#Adding a device filter to request
device_category = input('Enter device category: MOBILE, DESKTOP or TABLET (leave it blank for all devices): ').strip()
if device_category:
    request['dimensionFilterGroups'] = [{'filters':[{'dimension':'device','expression':device_category}]}]

#Request to SC API
response = execute_request(webmasters_service, site, request)


##----- Parsing the JSON returned

scDict = defaultdict(list)

for row in response['rows']:
    scDict['page'].append(row['keys'][0] or 0)
    scDict['query'].append(row['keys'][1] or 0)
    scDict['clicks'].append(row['clicks'] or 0)
    scDict['ctr'].append(row['ctr'] or 0)
    scDict['impressions'].append(row['impressions'] or 0)
    scDict['position'].append(row['position'] or 0)



##------  DataFrame of Search Console data

df = pd.DataFrame(data = scDict)

df['clicks'] = df['clicks'].astype('int')
df['ctr'] = df['ctr']*100
df['impressions'] = df['impressions'].astype('int')
df['position'] = df['position'].round(2)
df.sort_values('clicks',inplace=True,ascending=False)
df


##-----  Cleaning the DataFrame and sorting it by query




SERP_results = 8 #insert here your prefered value for SERP results
branded_queries = 'brand|vrand|b rand...' #insert here your branded queries

df_canibalized = df[df['position'] > SERP_results] 
df_canibalized = df_canibalized[~df_canibalized['query'].str.contains(branded_queries, regex=True)]
df_canibalized = df_canibalized[df_canibalized.duplicated(subset=['query'], keep=False)]
df_canibalized.set_index(['query'],inplace=True)
df_canibalized.sort_index(inplace=True)
df_canibalized.reset_index(inplace=True)
df_canibalized


## -----  Scraping URLs and Adding Titles and Meta Descriptions to the DataFrame

def get_meta(url):
    page = requests.get(url)
    soup = BeautifulSoup(page.content,'html.parser')
    title = soup.find('title').get_text()
    meta = soup.select('meta[name="description"]')[0].attrs["content"] 
    return title, meta

df_canibalized['title'],df_canibalized['meta'] = zip(*df_canibalized['page'].apply(get_meta))
df_canibalized


##-----  Creating a dynamic grid to analyse the data

grid = qgrid.show_grid(df_canibalized, show_toolbar=True)
grid