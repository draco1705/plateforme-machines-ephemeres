# api/app/exceptions.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

class AppError(Exception):
     def __init__(self, code: str, message: str, status: int = 400):
          self.code, self.message, self.status = code, message, status
     
def register_exception_handlers(app: FastAPI):
     @app.exception_handler(AppError)
     async def app_error_handler(request: Request, exc: AppError):
          return JSONResponse(
               status_code = exc.status,
               content = {
                    "code": exc.code, "message": exc.message,
               }
          )

     @app.exception_handler(IntegrityError)
     async def integrity_error_handler(request: Request, exc: IntegrityError):
          return JSONResponse(
               status_code=409,
               content={
                    "code": "DATABASE_INTEGRITY_ERROR",
                    "message": "Erreur d'intégrité de la base de données (donnée dupliquée ou contrainte violée)."
               }
          )