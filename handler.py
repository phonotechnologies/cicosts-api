"""
AWS Lambda handler for CICosts API.

Uses Mangum to adapt FastAPI ASGI app for Lambda.
"""
print("[HANDLER] Loading CICosts API Lambda handler")

from mangum import Mangum
from app.main import app

print("[HANDLER] Creating Mangum adapter")

# Lambda handler
handler = Mangum(app, lifespan="off")

print("[HANDLER] Handler ready")
