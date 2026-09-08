from passlib.context import CryptContext
from app.core.config import settings
from datetime import datetime,timedelta
import jwt
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def hash_password(password:str):
    return pwd_context.hash(password)

def verify_password(password:str,hashed_password:str):
    return pwd_context.verify(password,hashed_password)

def create_access_token(claims:dict)->str:
    to_encode = claims.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode["exp"] = expire
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)

    return encoded_jwt

def decode_access_token(token:str):
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def create_refresh_token(claims:dict)->str:
    to_encode = claims.copy()
    expire = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    to_encode["exp"] = expire
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt
    
    
def decode_refresh_token(token:str):
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
