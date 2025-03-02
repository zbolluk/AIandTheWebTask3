## newChannel.py - a simple message channel test
##

from flask import Flask, request, render_template, jsonify
import json
import requests
from datetime import datetime, timedelta
from better_profanity import profanity

# Class-based application configuration
class ConfigClass(object):
    """ Flask application config """

    # Flask settings
    SECRET_KEY = 'This is an INSECURE secret!! DO NOT use this in production!!'

# Create Flask app
app = Flask(__name__)
app.config.from_object(__name__ + '.ConfigClass')  # configuration
app.app_context().push()  # create an app context before initializing db

HUB_URL = 'http://localhost:5555'
HUB_AUTHKEY = '1234567890'
CHANNEL_AUTHKEY = '0987654321'
CHANNEL_NAME = "Events of Osnabrück Channel"
CHANNEL_ENDPOINT = "http://localhost:5002" # don't forget to adjust in the bottom of the file
CHANNEL_FILE = 'newmessages.json'
CHANNEL_TYPE_OF_SERVICE = 'aiweb24:chat'


MAX_MESSAGE_AGE_MINUTES = 120

@app.cli.command('register')
def register_command():
    global CHANNEL_AUTHKEY, CHANNEL_NAME, CHANNEL_ENDPOINT

    # send a POST request to server /channels
    response = requests.post(HUB_URL + '/channels', headers={'Authorization': 'authkey ' + HUB_AUTHKEY},
                             data=json.dumps({
                                "name": CHANNEL_NAME,
                                "endpoint": CHANNEL_ENDPOINT,
                                "authkey": CHANNEL_AUTHKEY,
                                "type_of_service": CHANNEL_TYPE_OF_SERVICE,
                             }))

    if response.status_code != 200:
        print("Error creating channel: "+str(response.status_code))
        print(response.text)
        return

def check_authorization(request):
    global CHANNEL_AUTHKEY
    # check if Authorization header is present
    if 'Authorization' not in request.headers:
        return False
    # check if authorization header is valid
    if request.headers['Authorization'] != 'authkey ' + CHANNEL_AUTHKEY:
        return False
    return True

@app.route('/health', methods=['GET'])
def health_check():
    global CHANNEL_NAME
    if not check_authorization(request):
        return "Invalid authorization", 400
    return jsonify({'name':CHANNEL_NAME}),  200

# GET: Return list of messages
@app.route('/', methods=['GET'])
def home_page():
    if not check_authorization(request):
        return "Invalid authorization", 400
    # fetch channels from server
    messages = read_messages()
    messages = remove_old_messages(messages)  # Clean up old messages
    save_messages(messages)  # Save the cleaned-up list
    return jsonify(messages)

# POST: Send a message
@app.route('/', methods=['POST'])
def send_message():
    # fetch channels from server
    # check authorization header
    if not check_authorization(request):
        return "Invalid authorization", 400
    # check if message is present
    message = request.json
    if not message:
        return "No message", 400
    if not 'content' in message:
        return "No content", 400
    if not 'sender' in message:
        return "No sender", 400
    if not 'extra' in message:
        extra = None
    else:
        extra = message['extra']

    profanity.load_censor_words()

    content = message['content']

    #check if the content contains profanity
    if profanity.contains_profanity(content):
        return "Message contains banned/off-topic language.", 400
    
  
    # timestamp in ISO 8601 format
    timestamp = datetime.utcnow().isoformat()

    # add message to messages
    messages = read_messages()
    messages.append({'content': content,
                     'sender': message['sender'],
                     'timestamp': timestamp,
                     'extra': extra,
                     'pinned': False,
                     })
    messages = remove_old_messages(messages)
    save_messages(messages)
    return "OK", 200

       
def read_messages():
    global CHANNEL_FILE
    try:
        f = open(CHANNEL_FILE, 'r')
    except FileNotFoundError:
        return []
    try:
        messages = json.load(f)
    except json.decoder.JSONDecodeError:
        messages = []
    f.close()
    return messages

def save_messages(messages):
    global CHANNEL_FILE
    with open(CHANNEL_FILE, 'w') as f:
        json.dump(messages, f)

def initialize_welcome_message():
    """Ensure the 'Founders' message is pinned at startup."""
    messages = read_messages()

    # Check if "Founders" message exists
    for message in messages:
        if message.get("sender") == "Founders":
            message["pinned"] = True  # Mark as pinned
            save_messages(messages)
            return

initialize_welcome_message()

def remove_old_messages(messages):
    """ Remove messages older than MAX_MESSAGE_AGE_MINUTES. """
    now = datetime.utcnow()
    cutoff_time = now - timedelta(minutes=MAX_MESSAGE_AGE_MINUTES)

    filtered_messages = []
    for msg in messages:
        try:
            msg_time = datetime.fromisoformat(msg['timestamp'])
            if msg.get('pinned', False) or msg_time >= cutoff_time:
                filtered_messages.append(msg)
        except ValueError:
            print(f"Skipping message with invalid timestamp: {msg['timestamp']}")

    return filtered_messages


# Start development web server
# run flask --app channel.py register
# to register channel with hub

if __name__ == '__main__':
    app.run(port=5002, debug=True)

