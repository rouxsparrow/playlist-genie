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

# @main.route('/me', methods=['POST'])
# def me():
#     auth_url = "https://accounts.spotify.com/authorize"
#     response_type = "code"
#     scope = os.getenv('SPOTIFY_SCOPE')
#     logging.info(f"Scope: {scope}")
#     # Build the authorization URL
#     auth_query = urllib.parse.urlencode({
#         "response_type": response_type,
#         "client_id": os.getenv('SPOTIFY_CLIENT_ID'),
#         "scope": scope,
#         "redirect_uri": os.getenv('REDIRECT_URI')
#     })

#     return redirect(f"{auth_url}?{auth_query}")

# @main.route('/callback', methods=['GET'])
# def callback():
#     code = request.args.get('code')
#     error = request.args.get('error')

#     if error:
#         return f"Error: {error}", 400

#     # Exchange the code for an access token
#     token_url = "https://accounts.spotify.com/api/token"
#     # headers = {
#     #     "Authorization": f"Basic {os.getenv('SPOTIFY_CLIENT_ID')}:{os.getenv('SPOTIFY_CLIENT_SECRET')}",
#     #     "content-type": "application/x-www-form-urlencoded"
#     # }
#     payload = {
#         "grant_type": "authorization_code",
#         "code": code,
#         "redirect_uri": os.getenv('REDIRECT_URI'),
#         'client_id': os.getenv('SPOTIFY_CLIENT_ID'),
#         'client_secret': os.getenv('SPOTIFY_CLIENT_SECRET'),
#     }
#     response = requests.post(token_url, data=payload)
#     token_info = response.json()

#     if 'access_token' in token_info:
#         # Store the access token in a session or a secure place
#         # Write the access token, refresh token, and its expiry time to a file
#         access_token = token_info.get('access_token')
#         refresh_token = token_info.get('refresh_token')
#         expires_in = token_info.get('expires_in', 3600)  # Use default 1 hour if not provided
#         expiry_time = datetime.now() + timedelta(seconds=expires_in)
#         with open(os.getenv('TOKEN_FILE_PATH'), 'w') as token_file:
#             token_file.write(access_token + '\n')
#             token_file.write(refresh_token + '\n')  # Store the refresh token
#             token_file.write(str(expiry_time.timestamp()))
#         return redirect('/index') 
#     else:
#         return "Failed to get access token", 400