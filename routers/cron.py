
import subprocess, os, re, croniter, datetime
from subprocess import PIPE
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Path, Request
from fastapi.logger import logger
from pydantic import BaseModel, Field
from starlette import status
from starlette.responses import RedirectResponse 
from .auth import get_user
from fastapi.templating import Jinja2Templates

router = APIRouter(
    prefix='/cronmgr',
    tags=['cronmgr']
)

crons = None

templates = Jinja2Templates(directory='./templates')

class Job:
    id : int
    cron_job : str
    is_active : bool

    def __init__(self, id, names, cron_job, is_active, next_run):
        self.id = id
        self.name = names[-1].strip() if len(names)>=1 else None
        self.cron_job = cron_job
        self.is_active = is_active
        self.next_run = next_run

class JobRequest(BaseModel):
    id : Optional[int]
    name: str = Field(min_length=1)
    cron_job : str = Field(min_length=1)
    is_active : bool

    class Config:
        schema_extra = {
            "example": {
                "name": "cronjob name",
                "cron_job" : "command or script to run with cron expression",
                "is_active" : "status of cron job"
            }
        }

def redirect_to_login():
    redirect_response = RedirectResponse(url="/auth/login-page", status_code=status.HTTP_302_FOUND)
    redirect_response.delete_cookie(key="access_token")
    return redirect_response

### Pages ###
@router.get("/jobs-page")
async def render_jobs_page(request: Request):
    global crons
    try:
        user = await get_user(request.cookies.get('access_token'))

        if user is None:
            return redirect_to_login()
        
        crons = _get_cron()
        return templates.TemplateResponse("jobs.html", {"request": request,
                                                        "jobs": crons, "user": user})

    except:
        return redirect_to_login()


### Endpoints ###
def _parse_cron_expression(cron_expr):
    cron_expr = cron_expr.strip()
    if(cron_expr[0]=='#'): cron_expr = cron_expr[1:].strip()
    
    cron_pattern = r'(\S+)\s(\S+)\s(\S+)\s(\S+)\s(\S+)\s'
    match = re.match(cron_pattern, cron_expr)
    if(not match): return None
    # print(cron_expr, match.groups())
    match = ' '.join(match.groups())
    now = datetime.datetime.now()
    cron = croniter.croniter(match, now)
    t = cron.get_next(datetime.datetime)
    return t.strftime('%m/%d/%Y %H:%M:%S')

def _get_cron():
    result = subprocess.run(['crontab','-l'], stdout=PIPE, stderr=PIPE)
    if(result.stderr):
        logger.error(f"Error {result.stderr}")
        raise result.stderr
    result = result.stdout.decode().strip()
    lines = [line for line in result.split('\n') if line]
    cron_jobs = [Job(idx,re.findall(r'#([^\n#]+)',line),line, not line.strip().startswith('#'),
                     _parse_cron_expression(line)) for idx,line in enumerate(lines)]
    if(len(cron_jobs) == 0): raise HTTPException(status_code=404, detail='Item not found')
    return cron_jobs

def _run_cron(cronfile:str):
    result = subprocess.run(['crontab',f'{cronfile}'], stdout=PIPE, stderr=PIPE)
    if(result.stderr):
        logger.error(f"Error {result.stderr}")
        raise result.stderr
    return result

@router.get("/get_jobs", status_code=status.HTTP_200_OK)
# async def get_jobs(user:dict=Depends(get_user)):
async def get_jobs():
    global crons
    user = Depends(get_user)
    if(user is None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED
                            , detail='Authentication Failed')
    crons = _get_cron()
    if(len(crons)==0):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Jobs not found.")
    return crons

def _validate_cron(cur_cron:Job, new_cron:Job):
    if(cur_cron.name != new_cron.name): return None

    if(cur_cron.cron_job != new_cron.cron_job):
        if(not cur_cron.is_active and 
           cur_cron.cron_job[1:] != new_cron.cron_job): return None
        if(not new_cron.is_active and 
           new_cron.cron_job[1:] != cur_cron.cron_job): return None

    return new_cron

def _update_cron(new_cron:Job):
    if(new_cron.is_active and new_cron.cron_job[0]=='#'):
        new_cron.cron_job = new_cron.cron_job[1:].strip()
    if(not new_cron.is_active and new_cron.cron_job[0]!='#'):
        new_cron.cron_job = '#' + new_cron.cron_job.strip()
    return new_cron

@router.put("/update_job/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_job( job_request: JobRequest, id:int=Path(gt=0)):
    global crons
    if(crons is None):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail='No job found.')

    user = Depends(get_user)
    if user is None:
        raise HTTPException(status_code=401, detail='Authentication Failed')
                                
    try:
        new_cron = _validate_cron(crons[id], job_request)
        if(new_cron is None):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT
                                , detail='Unmatched data.')
        new_cron = _update_cron(new_cron)
        crons[id] = new_cron
    except:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, 
                            detail='Unable to overwrite exisiting cron.')

@router.post("/save_jobs", status_code=status.HTTP_201_CREATED)
async def save_jobs():
    global crons
    user = Depends(get_user)
    
    if user is None:
        raise HTTPException(status_code=401, detail='Authentication Failed')
    
    try:
        if(crons is None): crons = _get_cron()
        cron_dir = os.getenv('CRON_FILE')
   
        with open(cron_dir, 'w', encoding='utf-8') as f:
            for idx,j in enumerate(crons):
                if(idx<len(crons)-1): 
                    f.write(j.cron_job+'\n\n'); continue
                f.write(j.cron_job+'\n')

        try:
            _run_cron(cron_dir)
            logger.info(f"Successfully saved {cron_dir}")
        except:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, 
                                detail='Failed to save cron.')

    except:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, 
                            detail='Failed to save cron.')
    return crons