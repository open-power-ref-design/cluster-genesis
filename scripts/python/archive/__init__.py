import os
from os import path
import sys

# Allow imports
TOP_DIR = path.join(os.getcwd(), path.dirname(__file__), '../')
SCRIPT_DIR = 'scripts/python'
sys.path.append(path.join(TOP_DIR, SCRIPT_DIR))
