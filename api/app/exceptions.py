# api/app/exceptions.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

class AppError(Exception):
     def __init__(self, code: str, message: str, status: int = 400):
          self.code, self.message, self.status = code, message, status
     
def register_exception_handlers(app: FastAPI):
     @app.exception_handler(AppError)
     async def app_error_handler(request: Request, exc: AppError):
          return JSONResponse(
               status_code = exc.status,
               content = {
                    "code": exc_code, "message": exc.message,
               }
          )