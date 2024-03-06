from flask import Blueprint, render_template, request, session
import requests, os, logging, sys, re
from urllib.parse import quote  # For URL encoding the query
from dotenv import load_dotenv
from flask import request, render_template
from datetime import datetime, timedelta
import time

load_dotenv()
logging.basicConfig(stream=sys.stderr, level=logging.INFO)
main = Blueprint('main', __name__)

def authenticate_spotify():
    auth_url = "https://accounts.spotify.com/api/token"
    response = requests.post(auth_url, {
        'grant_type': 'client_credentials',
        'client_id': os.getenv('SPOTIFY_CLIENT_ID'),
        'client_secret': os.getenv('SPOTIFY_CLIENT_SECRET'),
    })
    auth_data = response.json()
    access_token = auth_data.get('access_token')
    expires_in = auth_data.get('expires_in')  # Time in seconds until the token expires

    # Calculate the expiry time as a datetime object
    expiry_time = datetime.now() + timedelta(seconds=expires_in)

    # Store the access token and its expiry time in the session
    session['access_token'] = access_token
    session['token_expiry'] = expiry_time.timestamp()  # Convert datetime to a timestamp

    return access_token

def get_spotify_token():
    # Check if token is expired
    current_time = datetime.now().timestamp()
    if 'token_expiry' not in session or current_time >= session['token_expiry']:
        return authenticate_spotify()  # Re-authenticate if token is expired or not set
    else:
        return session['access_token']

def search_spotify(query):
    access_token = get_spotify_token()  # Get a valid access token
    
    headers = {
        'Authorization': f"Bearer {access_token}",
    }
    search_url = "https://api.spotify.com/v1/search"
    offset = 0
    limit = 50
    while offset < 1000:
        params = {'q': query, 'type': 'track', 'limit': limit, 'offset': offset}
        response = requests.get(search_url, headers=headers, params=params)
        search_results = response.json()
        if response.status_code == 401:
            # If the token is expired, re-authenticate and retry the request
            access_token = authenticate_spotify()
            headers['Authorization'] = f"Bearer {access_token}"
            response = requests.get(search_url, headers=headers, params=params)
            search_results = response.json()
            
        tracks = search_results.get('tracks', {}).get('items', [])
        for track in tracks:
            # Compare query with track name for an exact match
            if track['name'].lower() == query.lower():
                return {
                    'name': track['name'],
                    'artist': ", ".join(artist['name'] for artist in track['artists']),
                    'album_art': track['album']['images'][0]['url'] if track['album']['images'] else None
                }
        offset += limit
    return None 
    # Return an empty list if no match is found

def threaded_search_spotify(query):
    # Wraps the search_spotify function for use with threading
    # Return both the query and the result for identifying matches
    result = search_spotify(query)
    return query, result

@main.route('/')
def index():
    return render_template('index.html')

@main.route('/search', methods=['POST'])

def search():
    text = request.form['text']
    # Clean the input text by removing punctuation
    cleaned_text = re.sub(r'[^\w\s]', '', text)
    words = cleaned_text.split()  # Split the cleaned input text into individual words
    results = []
    i = 0
    while i < len(words):
        longest_match = None
        current_query = ""
        for j in range(i, len(words)):
            # Build up query from left to right
            current_query += ("" if current_query == "" else " ") + words[j]  
            result = search_spotify(current_query)
            if result:
                # Update longest match
                longest_match = result  
                last_successful_j = j
            logging.info(f"Trying with query: {current_query}")
        if longest_match:
            results.append(longest_match)
            i = last_successful_j + 1  # Move index past the last successful match
        else:
            # If no match was found for any sequence starting with word[i], add a not found entry and move to the next word
            results.append({'name': 'song <br>' + words[i] + '<br> not found', 'artist': 'sorry :<', 'album_art': '/static/images/me_sorry.jpg'})
            i += 1
    return render_template('results.html', songs=results, query=text)
