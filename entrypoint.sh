#!/bin/bash
# Run watch_dog_mrf.py in the background
python3 watch_dog_loads.py &

# Run app.py in the foreground
python3 run.py
