
import os
from fastapi import FastAPI, Request, status
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from routers import auth, cron
from fastapi.responses import RedirectResponse

load_dotenv('./env/.env')

app = FastAPI()

# mounting static directory
absolute_path = os.path.dirname(__file__)
app.mount("/static", StaticFiles(directory=os.path.join(absolute_path, "static")), name="static")

@app.get("/")
def test(request: Request):
    return RedirectResponse(url="/cronmgr/jobs-page", status_code=status.HTTP_302_FOUND)

@app.get("/healthy")
def health_check():
    return {'status': 'Healthy'}

app.include_router(auth.router)
app.include_router(cron.router)