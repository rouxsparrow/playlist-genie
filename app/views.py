from flask import Blueprint, render_template, request, session
import requests, os, logging, sys, re
from urllib.parse import quote  # For URL encoding the query
from dotenv import load_dotenv
from flask import request, render_template
from datetime import datetime, timedelta
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

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

    # Write the access token and its expiry time to a file
    with open(os.getenv('TOKEN_FILE_PATH'), 'w') as token_file:
        token_file.write(access_token + '\n')
        token_file.write(str(expiry_time.timestamp()))

    return access_token

def get_spotify_token():
    try:
        # Attempt to read the access token and expiry time from the file
        with open(os.getenv('TOKEN_FILE_PATH'), 'r') as token_file:
            access_token = token_file.readline().strip()
            expiry_time = float(token_file.readline().strip())

        current_time = datetime.now().timestamp()
        if current_time >= expiry_time:
            # If the token is expired, re-authenticate and get a new token
            return authenticate_spotify()
        else:
            return access_token
    except FileNotFoundError:
        # If the token file does not exist, authenticate to create it
        return authenticate_spotify()

def search_spotify(query,access_token):
    # access_token = get_spotify_token()
    headers = {'Authorization': f'Bearer {access_token}'}
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

def search_with_offset(query, access_token, offset):
    headers = {'Authorization': f'Bearer {access_token}'}
    search_url = "https://api.spotify.com/v1/search"
    params = {'q': query, 'type': 'track', 'limit': 50, 'offset': offset}
    response = requests.get(search_url, headers=headers, params=params)
    search_results = response.json()

    if response.status_code == 401:  # Token expired
        return None, True  # Indicate that re-authentication is needed

    tracks = search_results.get('tracks', {}).get('items', [])
    for track in tracks:
        if track['name'].lower() == query.lower():
            return {
                    'name': track['name'],
                    'artist': ", ".join(artist['name'] for artist in track['artists']),
                    'album_art': track['album']['images'][0]['url'] if track['album']['images'] else None
                }, False  # Found a match, no re-auth needed
    return None, False  # No match found, no re-auth needed

def search_thread(query, access_token):
    for _ in range(3):  # Try up to 3 times
        with ThreadPoolExecutor(max_workers=5) as executor:
            offsets = [i * 50 for i in range(5)]  # Initial offsets: 0, 50, 100, 150, 200
            future_to_offset = {executor.submit(search_with_offset, query, access_token, offset): offset for offset in offsets}

            for future in as_completed(future_to_offset):
                track, need_auth = future.result()
                if need_auth:
                    access_token = authenticate_spotify()  # Re-authenticate if needed
                    return search_thread(query, access_token)  # Retry search with new token

                if track:
                    return track  # Return the first match found

            offsets = [offset + 250 for offset in offsets]  # Increase each offset by 250 for the next iteration
            logging.info(f"Retrying with new offsets: {offsets}")
    return None  # No match found after all attempts


def deduplicate_and_sort_results(results, words):
    # Sort results by the length of the match in descending order to prioritize longer matches
    results.sort(key=lambda x: len(x[0]), reverse=True)

    # Initialize a dictionary to keep track of the longest match for each starting word
    longest_matches = {}
    for query, result in results:
        start_word = query.split()[0]
        if start_word not in longest_matches:
            longest_matches[start_word] = (query, result)

    # Prepare the final list of results, ensuring every word from the input is accounted for
    final_results = []
    used_words = set()
    for word in words:
        if word in used_words:
            continue  # Skip words already included in a longer match
        if word in longest_matches:
            final_results.append(longest_matches[word][1])
            used_words.update(longest_matches[word][0].split())  # Mark all words in this match as used
        else:
            # If the word was not part of any successful match, add a 'not found' entry
            final_results.append({'name': f'song <br>{word}<br> not found', 'artist': 'sorry :<', 'album_art': '/static/images/me_sorry.jpg'})
            used_words.add(word)  # Mark this word as used

    return final_results

@main.route('/')
def index():
    return render_template('index.html')

@main.route('/single_word_search', methods=['POST'])
def single_word_search():
    global_start_time = time.time()
    # Search for a single word query
    access_token = get_spotify_token()
    text = request.form['text']
    # Clean the input text by removing punctuation
    cleaned_text = re.sub(r'[^\w\s]', '', text)
    words = cleaned_text.split()  # Split the cleaned input text into individual words
    results = []
    for word in words:
        result = search_spotify(word,access_token)
        if not result:
            result = {'name': 'song <br>' + word + '<br> not found', 'artist': 'sorry :<', 'album_art': '/static/images/me_sorry.jpg'}
        logging.info(f"Found result: {result}")
        results.append(result)
    logging.info(f"Final results: {results}")
    global_end_time = time.time()
    logging.info(f"Total time taken: {global_end_time - global_start_time:.2f} seconds")
    # The result is either a list with one item or an empty list
    return render_template('results.html', songs=results, query=text)

@main.route('/search', methods=['POST'])
def search():
    global_start_time = time.time()
    access_token = get_spotify_token()
    text = request.form['text']
    # Clean the input text by removing punctuation
    cleaned_text = re.sub(r'[^\w\s]', '', text)
    words = cleaned_text.split()  # Split the cleaned input text into individual words
    results = []
    future_to_query = {}  # Use a dictionary to map futures to queries
    queries = [" ".join(words[i:j]) for i in range(len(words)) for j in range(i + 1, len(words) + 1)]
    logging.info(f"Queries: {queries}")
    with ThreadPoolExecutor(max_workers=5) as executor:
        for query in queries:
            future = executor.submit(search_thread, query, access_token)
            future_to_query[future] = query  # Map the future to its query

        for future in as_completed(future_to_query):
            query = future_to_query[future]  # Retrieve the query for this future
            try:
                result = future.result()  # Assuming future.result() returns the result directly
                if result:  # If a result is found, add it to the results list
                    logging.info(f"Found result: {result}")
                    logging.info(f"Query: {query}")
                    results.append((query, result))
            except Exception as exc:
                logging.error(f'Query "{query}" generated an exception: {exc}')

    # Deduplicate results based on the longest match for each starting word
    final_results = deduplicate_and_sort_results(results, words)
    global_end_time = time.time()
    logging.info(f"Total time taken: {global_end_time - global_start_time:.2f} seconds")
    return render_template('results.html', songs=final_results, query=text)

@main.route('/thread', methods=['POST'])
def thread():
    # Search for a single word query
    global_start_time = time.time()
    access_token = get_spotify_token()
    text = request.form['text']
    # Clean the input text by removing punctuation
    cleaned_text = re.sub(r'[^\w\s]', '', text)
    words = cleaned_text.split()  # Split the cleaned input text into individual words
    results = []
    for word in words:
        result = search_thread(word,access_token)
        if not result:
            result = {'name': 'song <br>' + word + '<br> not found', 'artist': 'sorry :<', 'album_art': '/static/images/me_sorry.jpg'}
        logging.info(f"Found result: {result}")
        results.append(result)
    logging.info(f"Final results: {results}")
    global_end_time = time.time()
    logging.info(f"Total time taken: {global_end_time - global_start_time:.2f} seconds")
    # The result is either a list with one item or an empty list
    return render_template('results.html', songs=results, query=text)
