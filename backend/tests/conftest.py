import sys
from pathlib import Path

# Add the backend directory to sys.path so `import main` works
sys.path.insert(0, str(Path(__file__).parent.parent))
