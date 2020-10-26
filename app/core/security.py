import jwt
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from datetime import datetime, timedelta

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/token")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = "d7Wn3VRWMWPqpM5rqsdRAvW$2Y7&MTwqnEFZrxA!tNDd&p9F#quNp*SsKzd&AWSLap!NkvW7DPsHktcJPA&cw@bZ$hxpprDdGKk*h53tL47dDH2epM6JaqD6mfju4&bz"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 7


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(*, data: dict, expires_delta: timedelta = timedelta(days=7)):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
