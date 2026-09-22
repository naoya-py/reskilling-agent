"""アプリの入り口。

FastAPI のふつうのウェブアプリ。第4回で Docker に入れて AWS Lambda に載せるが、
コードのどこにも Lambda は出てこない（Dockerfile を見ること）。

第3回時点：/api/chat は「受け取った文字をそのまま返す」だけ。
ただし返す形（reply・turns・tokens …）は完成形と同じにしてある。
第5回でこの関数の中身を LLM（Amazon Bedrock）の呼び出しに差し替えても、画面側は変えなくてよい。
"""

import logging
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.logging_conf import setup_logging
from app.secrets import demo_api_key

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name, version="0.1.0")

WEB_DIR = Path(__file__).parent / "web"


# ---------- リクエストとレスポンスの型 ----------
# 型を先に書いておくと、FastAPI が入力の検証と /docs の画面を自動で作ってくれる。

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000, description="利用者からの入力")
    # どの会話の続きかを示す。ブラウザが作って送ってくる（第6回で履歴に使う）
    session_id: str = Field(default="default", min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


class ChatResponse(BaseModel):
    reply: str
    # 画面に実測値を出す。第5回から本物の数字が入る。いまは 0
    turns: int = 0
    tools_used: list[str] = []
    input_tokens: int = 0
    output_tokens: int = 0
    elapsed_ms: int = 0
    model: str = "echo"
    history_messages: int = 0


# ---------- エンドポイント ----------

@app.get("/healthz")
def healthz() -> dict:
    """生きているかの確認用。第4回から AWS がここを叩く。200 を返さないと起動失敗になる。"""
    return {
        "status": "ok",
        "env": settings.app_env,
        "student_id": settings.student_id,
        "app_name": settings.app_name,
        "api_key_set": bool(demo_api_key()),
    }


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    """画面。app/web/index.html をそのまま返す。"""
    return (WEB_DIR / "index.html").read_text(encoding="utf-8")


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """第3回時点では、受け取った文字をそのまま返す。

    第5回で、この中身を Bedrock の呼び出しに差し替える。
    受け取る形・返す形・記録する、の3つを先に作っておくのがこの回の目的。
    """
    started = time.monotonic()
    logger.info("chat request received", extra={"extra_fields": {"chars": len(req.message), "session_id": req.session_id}})
    reply = f"受け取りました: {req.message}"
    return ChatResponse(reply=reply, elapsed_ms=int((time.monotonic() - started) * 1000))


@app.get("/api/suggestions")
def suggestions() -> list[str]:
    """画面の定型質問ボタン。ここを変えると、画面のボタンが変わる（3-2 で画面側をつなぐ）。"""
    return [
        "いま何時？",
        "今日は何曜日？",
        "生成AIのRAGとは何か、3行で説明して",
        "議事録のテンプレートを作って",
    ]
