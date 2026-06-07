import jwt
from config import settings
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# auto_error=False sorgt dafür, dass FastAPI nicht automatisch abstürzt, 
# wenn kein "Authorization"-Header mitgesendet wird.
security = HTTPBearer(auto_error=False) 

async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)):
    # ---- 1. DER DEVELOPMENT / TEST-MODUS ----
    print(settings.ENVIRONMENT, flush=True)
    print("hallo", flush=True)
    
    if settings.ENVIRONMENT == "dev":
        return {
            "email": "max.mustermann@uni-muenster.de",
            "name": "Max Mustermann",
            "institution": "fh-swf",
            "role": "faculty"
        }
        
    # ---- 2. DER PRODUKTIONS-MODUS ----
    # In Prod müssen wir jetzt händisch prüfen, ob credentials überhaupt existieren,
    # da auto_error=False den automatischen Absturz verhindert hat.
    if not credentials:
        raise HTTPException(
            status_code=401, 
            detail="Authentifizierung erforderlich. 'Authorization'-Header fehlt."
        )
        
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Das Login-Token ist abgelaufen.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Ungültiges Authentifizierungs-Token.")