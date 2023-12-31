#!/bin/bash

# Start the Flask application
export FLASK_APP=coachess.py
flask run &

# Save the PID of the Flask process
FLASK_PID=$!

# Wait for the server to start up, then open it in a web browser
sleep 5
xdg-open http://127.0.0.1:5000

# Wait for the Flask process to finish, then exit
wait $FLASK_PID