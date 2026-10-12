#!/bin/bash
google-chrome-stable --user-data-dir=/tmp/jarvis_test_prof --headless=new --use-fake-ui-for-media-stream --remote-debugging-port=9222 http://192.168.1.92:8080 &
sleep 5
curl -s http://localhost:9222/json
