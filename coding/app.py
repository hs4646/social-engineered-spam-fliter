import threading
import webbrowser

import uvicorn

from app.main import create_app


app = create_app()


if __name__ == "__main__":
    threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:8000")).start()
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)
