from flask import Flask, request, jsonify, send_file
import requests
from bs4 import BeautifulSoup
import json
import os
from functools import lru_cache
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

def send_get_request(url: str) -> dict:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, verify=False, allow_redirects=True)
        cookies = [f"{k}={v}" for k, v in response.cookies.items()]
        csrf_token = extract_csrf_token(response.text)
        
        return {
            'body': response.text,
            'cookies': '; '.join(cookies),
            'csrf_token': csrf_token
        }
    except Exception as e:
        return None

def extract_csrf_token(html: str) -> str:
    soup = BeautifulSoup(html, 'html.parser')
    
    # Try to find CSRF token in meta tags
    meta = soup.find('meta', {'name': 'csrf-token'})
    if meta and 'content' in meta.attrs:
        return meta['content']
    
    # Try to find it in input fields
    for input_tag in soup.find_all('input'):
        name = input_tag.get('name', '').lower()
        if 'csrf' in name or 'token' in name:
            return input_tag.get('value')
    
    return None

def get_input_by_id(html: str, id: str) -> str:
    soup = BeautifulSoup(html, 'html.parser')
    input_element = soup.find(id=id)
    
    if input_element:
        return input_element.get('name')
    return None

def get_input_by_type(html: str, type: str, index: int = 0) -> dict:
    soup = BeautifulSoup(html, 'html.parser')
    input_elements = soup.find_all('input', {'type': type})
    
    if len(input_elements) > index:
        element = input_elements[index]
        return {
            'name': element.get('name'),
            'value': element.get('value')
        }
    return None

def send_post_request(url: str, data: dict, cookie: str, csrf_token: str = None) -> dict:
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36',
        'Cookie': cookie
    }
    
    if csrf_token:
        headers['X-CSRF-Token'] = csrf_token
    
    try:
        response = requests.post(url, data=data, headers=headers, verify=False, allow_redirects=True)
        cookies = [f"{k}={v}" for k, v in response.cookies.items()]
        new_csrf_token = extract_csrf_token(response.text)
        
        return {
            'status_code': response.status_code,
            'body': response.text,
            'cookies': cookies,
            'csrf_token': new_csrf_token
        }
    except Exception as e:
        return {
            'status_code': 0,
            'body': f'Request failed: {str(e)}',
            'cookies': []
        }

def save_auth_data(cookies: list, csrf_token: str = None, rgid: str = None) -> None:
    # Default cookies
    default_cookies = [
        'redeem_banner=yes',
        'region=IN',
        'CookieConsent={stamp:\'BdwMOWyJhyeycito6a5d/RwoCYRc53JWLvyV+4GNKCHN0VPZ4HjuVw==\',necessary:true,preferences:false,statistics:false,marketing:false,method:\'explicit\',ver:1,utc:1741942679561,region:\'in\'}'
    ]
    
    cookie_array = default_cookies.copy()
    
    # Process received cookies
    for cookie in cookies:
        cookie = cookie.strip()
        if not cookie:
            continue
        
        cookie_name = cookie.split('=')[0]
        exists = False
        
        for i, existing_cookie in enumerate(cookie_array):
            if existing_cookie.startswith(f"{cookie_name}="):
                cookie_array[i] = cookie
                exists = True
                break
        
        if not exists:
            cookie_array.append(cookie)
    
    # Save cookies to file
    cookie_string = ';'.join(cookie_array)
    
    # Save auth data to JSON
    auth_data = {
        'cookies': cookie_array,
        'csrf_token': csrf_token
    }
    
    if rgid:
        auth_data['rgid'] = rgid
    
    with open(os.path.join(os.path.dirname(__file__), 'py_data.json'), 'w') as f:
        json.dump(auth_data, f, indent=2)
    
    # Save session cookie separately if present
    for cookie in cookie_array:
        if cookie.startswith('unipin_session='):
            session_value = cookie.split('=', 1)[1]
            with open(os.path.join(os.path.dirname(__file__), 'session.txt'), 'w') as f:
                f.write(session_value)
            break

from dotenv import load_dotenv
import os

def refresh_cookies():
    load_dotenv()
    url = 'https://www.unipin.com/login'
    get_response = send_get_request(url)
    
    if get_response:
        response = get_response['body']
        cookies = get_response['cookies']
        csrf_token = get_response['csrf_token']
        
        # Try to login with session first
        session_file = os.path.join(os.path.dirname(__file__), 'session.txt')
        if os.path.exists(session_file):
            try:
                with open(session_file, 'r') as f:
                    session_value = f.read().strip()
                if session_value:
                    # Add session cookie to existing cookies
                    cookies = f"{cookies}; unipin_session={session_value}"
                    # Try to access a protected page to verify session
                    verify_response = send_get_request('https://www.unipin.com/in/bgmi')
                    if verify_response and 'Sign Out' in verify_response['body']:
                        save_auth_data([cookies], csrf_token)
                        return True
                        print(f"Session login Success with unipin session: {session_value}")
            except Exception as e:
                print(f"Session login failed: {str(e)}")
        
        # Fall back to email/password login
        email_input_name = get_input_by_id(response, 'sign-in-email')
        password_input_name = get_input_by_id(response, 'signInPassword')
        
        # Get hidden inputs
        hidden_inputs = {}
        for i in range(5):
            hidden_input = get_input_by_type(response, 'hidden', i)
            if hidden_input:
                hidden_inputs[hidden_input['name']] = hidden_input['value']
        
        # Prepare login data using environment variables
        post_data = {
            email_input_name: os.getenv('UNIPIN_EMAIL'),
            password_input_name: os.getenv('UNIPIN_PASSWORD')
        }
        post_data.update(hidden_inputs)
        
        # Send login request
        post_response = send_post_request(url, post_data, cookies, csrf_token)
        
        if post_response['status_code'] == 200:
            bgmi_url = 'https://www.unipin.com/in/bgmi'
            bgmi_response = send_get_request(bgmi_url)
            
            if bgmi_response:
                html = bgmi_response['body']
                import re
                rgid_match = re.search(r"'rgid':\s*'([^']+)'", html)
                
                if rgid_match:
                    rgid = rgid_match.group(1)
                    save_auth_data(post_response['cookies'], post_response['csrf_token'], rgid)
                    return True
                else:
                    save_auth_data(post_response['cookies'], post_response['csrf_token'])
                    return True
            else:
                save_auth_data(post_response['cookies'], post_response['csrf_token'])
                return True
        else:
            save_auth_data(post_response['cookies'], post_response['csrf_token'])
            return False
    return False

@lru_cache(maxsize=128)
def get_checkout_details(dyn):
    # Read data from py_data.json
    with open(os.path.join(os.path.dirname(__file__), 'py_data.json'), 'r') as file:
        data = json.load(file)
    
    headersList = {
        "Host": "www.unipin.com",
        "accept": "application/json, text/javascript, */*; q=0.01",
        "accept-language": "en-GB,en-US;q=0.9,en;q=0.8,hi;q=0.7,zh-CN;q=0.6,zh;q=0.5",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "cookie": '; '.join(data['cookies']),
        "origin": "https://www.unipin.com",
        "priority": "u=1, i",
        "referer": "https://www.unipin.com/in/bgmi",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        "x-csrf-token": data['csrf_token'],
        "x-requested-with": "XMLHttpRequest"
    }
    
    url = f"https://www.unipin.com/in/bgmi/checkout/{dyn}"
    response = requests.get(url, headers=headersList)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        rows = soup.find_all("div", class_="details-row")
        for row in rows:
            label = row.find("div", class_="details-label text-white-50")
            value = row.find("div", class_="details-value")
            if label and value and "Username" in label.get_text(strip=True):
                return value.get_text(strip=True)
    return None

def load_uid_cache():
    cache_path = os.path.join(os.path.dirname(__file__), 'uid_cache.json')
    try:
        with open(cache_path, 'r') as cache_file:
            return json.load(cache_file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_uid_cache(cache):
    cache_path = os.path.join(os.path.dirname(__file__), 'uid_cache.json')
    with open(cache_path, 'w') as cache_file:
        json.dump(cache, cache_file, indent=2)

@app.route("/get_user", methods=["POST", "GET"])
def get_user():
    if request.method == "GET" and not request.args.get("uid"):
        return send_file('bgmi.html', mimetype='text/html')
    
    uid = request.args.get("uid") if request.method == "GET" else request.json.get("uid")
    if not uid:
        return jsonify({"error": "No UID provided"}), 400
        
    # Check if the UID exists in cache
    uid_cache = load_uid_cache()
    if uid in uid_cache:
        return uid_cache[uid], 200

    def make_request():
        # Reload data from py_data.json
        try:
            data_path = os.path.join(os.path.dirname(__file__), 'py_data.json')
            with open(data_path, 'r') as file:
                data = json.load(file)
        except Exception as e:
            # Try to refresh cookies immediately when authentication data loading fails
            try:
                if refresh_cookies():
                    print("Successfully refreshed cookies after auth data load failure")
                    # Try loading the data again after refresh
                    with open(data_path, 'r') as file:
                        data = json.load(file)
                else:
                    print("Failed to refresh cookies after auth data load failure")
                    return jsonify({"error": "Failed to refresh authentication data"}), 500
            except Exception as refresh_error:
                print(f"Failed to refresh cookies: {str(refresh_error)}")
                return jsonify({"error": "Failed to load and refresh authentication data"}), 500

        headersList = {
            "Host": "www.unipin.com",
            "accept": "application/json, text/javascript, */*; q=0.01",
            "accept-language": "en-GB,en-US;q=0.9,en;q=0.8,hi;q=0.7,zh-CN;q=0.6,zh;q=0.5",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "cookie": '; '.join(data['cookies']),
            "origin": "https://www.unipin.com",
            "priority": "u=1, i",
            "referer": "https://www.unipin.com/in/bgmi",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            "x-csrf-token": data['csrf_token'],
            "x-requested-with": "XMLHttpRequest"
        }

        reqUrl = "https://www.unipin.com/in/bgmi/inquiry"
        payload = f"rgid={data.get('rgid', '')}&userid={uid}&did=5218&pid=764&influencer=&cust_email=sahilraz9265@gmail.com"
        return requests.post(reqUrl, data=payload, headers=headersList)

    def process_response(response):
        if isinstance(response, tuple):
            return response
        if response.status_code == 200:
            try:
                json_response = response.json()
                if json_response.get("status") == "1":
                    dyn = json_response.get("message")
                    username = get_checkout_details(dyn)
                    return username if username else "Username not found", 200
                else:
                    return "Incorrect Uid or Player Id", 400
            except requests.exceptions.JSONDecodeError:
                return None
        return None

    # First attempt
    response = make_request()
    result = process_response(response)
    if result is not None:
        if isinstance(result, tuple) and result[1] == 200:
            uid_cache = load_uid_cache()
            uid_cache[uid] = result[0]
            save_uid_cache(uid_cache)
        return result

    # If first attempt failed, refresh cookies and try again
    try:
        if refresh_cookies():
            print("Successfully refreshed cookies")
        else:
            print("Failed to refresh cookies")
    except Exception as e:
        print(f"Failed to refresh cookies: {str(e)}")
        if response.status_code != 200:
            return jsonify({"error": f"Request failed with status code {response.status_code}"}), 500
        return jsonify({"error": "Failed to decode JSON response"}), 500

    # Second attempt after refreshing cookies
    response = make_request()
    result = process_response(response)
    if result is not None:
        if isinstance(result, tuple) and result[1] == 200:
            # Save successful result to cache
            uid_cache = load_uid_cache()
            uid_cache[uid] = result[0]
            save_uid_cache(uid_cache)
        return result

    # If both attempts failed, return appropriate error
    if response.status_code != 200:
        return jsonify({"error": f"Request failed with status code {response.status_code}"}), 500
    return jsonify({"error": "Failed to decode JSON response"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)