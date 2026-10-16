from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.apis.v1 import v1_routers
from app.core import config
from app.core.config import Env
from app.core.db.databases import initialize_tortoise
from app.core.errors import register_error_handlers

app = FastAPI(
    default_response_class=ORJSONResponse, docs_url="/api/docs", redoc_url="/api/redoc", openapi_url="/api/openapi.json"
)
# 내 컴퓨터에서 웹(Expo web)으로 화면을 확인할 때만 다른 주소에서의 요청을 허용 (앱에는 필요 없음, dev · prod에서는 끔)
if config.ENV == Env.LOCAL:
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_methods=["*"],
        allow_headers=["*"],
    )
initialize_tortoise(app)
register_error_handlers(app)

app.include_router(v1_routers)
