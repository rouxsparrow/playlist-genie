from flask import Blueprint, render_template, request, session
import requests, os
from urllib.parse import quote  # For URL encoding the query
from dotenv import load_dotenv
from flask import request, render_template

load_dotenv()

main = Blueprint('main', __name__)

def authenticate_spotify():
    auth_url = "https://accounts.spotify.com/api/token"
    response = requests.post(auth_url, {
        'grant_type': 'client_credentials',
        'client_id': os.getenv('SPOTIFY_CLIENT_ID'),
        'client_secret': os.getenv('SPOTIFY_CLIENT_SECRET'),
    })
    return response.json()

def search_spotify(query):
    if 'access_token' not in session:
        auth_response = authenticate_spotify()
        session['access_token'] = auth_response['access_token']
    
    headers = {
        'Authorization': f"Bearer {session['access_token']}",
    }
    search_url = "https://api.spotify.com/v1/search"
    offset = 0
    limit = 50
    while offset < 1000:
        params = {'q': query, 'type': 'track', 'limit': limit, 'offset': offset}
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
    return {'name': 'song <br>' + query + '<br> not found','artist':'sorry :<','album_art':'/static/images/me_sorry.jpg'} 
    # Return an empty list if no match is found

@main.route('/')
def index():
    return render_template('index.html')

@main.route('/search', methods=['POST'])
def search():
    text = request.form['text']
    words = text.split()  # Split the input text into individual words
    results = []
    for word in words:
        result = search_spotify(word)
        if result:
            print(f"Found result: {result}")  # Debug print
            results.append(result)
    print(f"Final results: {results}")
    # The result is either a list with one item or an empty list
    return render_template('results.html', songs=results, query=text)
