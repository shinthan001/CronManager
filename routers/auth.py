import os
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
from jose import jwt, JWTError
from starlette import status
from fastapi.templating import Jinja2Templates

router = APIRouter(
    prefix='/auth',
    tags=['auth']
)

oauth2_bearer = OAuth2PasswordBearer(tokenUrl='auth/token')

templates = Jinja2Templates(directory='./templates')

### Pages ###
@router.get("/login-page")
def render_login_page(request: Request):
    
    return templates.TemplateResponse("login.html", {"request": request})

### Endpints ###
class Token(BaseModel):
    access_token: str
    token_type: str

def _authenticate_user(uname,passwd):
    if(uname==os.getenv('CRONMGR_USER') and passwd==os.getenv("CRONMGR_PASS")):
        return uname
    return False

def _create_token():
    encode = {'sub': os.getenv('CRONMGR_USER')}
    encode['exp'] = datetime.now(timezone.utc) + timedelta(int(os.getenv('EXPIRE_MIN')))
    return jwt.encode(encode, os.getenv('SECRET_KEY'), algorithm=os.getenv('ALGORITHM'))

async def get_user(token: str=Depends(oauth2_bearer)):
    # try:
    payload = jwt.decode(token, os.getenv('SECRET_KEY'), algorithms=[os.getenv('ALGORITHM')])
    username = payload['sub']
    if(username != os.getenv('CRONMGR_USER')):
        raise(HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail='Could not validate user.'))
    return {'username': username}        
    # except JWTError:
    #     raise(HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
    #                         detail='Could not validate user.'))

@router.post("/token/", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = _authenticate_user(form_data.username, form_data.password)
    if(not user):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail='Could not validate user.')

    token = _create_token()
    return {'access_token': token, 'token_type': 'bearer'}