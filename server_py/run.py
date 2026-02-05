import uvicorn
import os

if __name__ == "__main__":
    # Ensure current directory is correct for imports
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
