"""
AWS Lambda handler for CICosts API.

Uses Mangum to adapt FastAPI ASGI app for Lambda.
"""
from mangum import Mangum
from app.main import app

# Lambda handler
handler = Mangum(app, lifespan="off")
