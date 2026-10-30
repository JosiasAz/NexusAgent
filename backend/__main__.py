"""Sobe o servidor: python -m backend"""
import logging
import os

import uvicorn

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
uvicorn.run('backend.api.app:app', host=os.environ.get('HOST', '127.0.0.1'),
            port=int(os.environ.get('BACKEND_PORT', 8001)))
