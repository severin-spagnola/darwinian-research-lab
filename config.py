# config.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# API Keys
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Directories
BASE_DIR = Path(__file__).parent
RESULTS_DIR = BASE_DIR / "results"
CACHE_DIR = RESULTS_DIR / "cache"  # On persistent disk (Render: 10GB mounted at /results)
GRAPHS_DIR = BASE_DIR / "graphs"
PATCHES_DIR = BASE_DIR / "patches"
STATIC_DIR = BASE_DIR / "static"

# Create directories (RESULTS_DIR first, then subdirectories)
for d in [RESULTS_DIR, CACHE_DIR, GRAPHS_DIR, PATCHES_DIR, STATIC_DIR]:
    d.mkdir(exist_ok=True, parents=True)

# Settings
DEFAULT_TIMEFRAME = "5m"
MAX_NODES_PER_GRAPH = 40
CACHE_EXPIRY_DAYS = 7

# Validation
HOLDOUT_SPLIT = 0.75  # 75% train, 25% holdout
JITTER_RUNS = 10
JITTER_PCT = 0.1
SUBWINDOW_CHUNKS = 6

# Evolution
DARWIN_DEPTH = 3
SURVIVORS_PER_GEN = 3
CHILDREN_PER_SURVIVOR = 3