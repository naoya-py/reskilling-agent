"""アプリの入り口。

FastAPI のふつうのウェブアプリ。第4回で Docker に入れて AWS Lambda に載せるが、
コードのどこにも Lambda は出てこない（Dockerfile を見ること）。

第3回時点：/api/chat は「受け取った文字をそのまま返す」だけ。
ただし返す形（reply・turns・tokens …）は完成形と同じにしてある。
第5回でこの関数の中身を LLM（Amazon Bedrock）の呼び出しに差し替えても、画面側は変えなくてよい。
"""

import logging
from pathlib import Path

from botocore.exceptions import ClientError
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.llm import ask
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
    """受け取った文章を LLM に送り、答えを返す。第5回は1問1答。"""
    logger.info("chat request received", extra={"extra_fields": {"chars": len(req.message), "session_id": req.session_id}})

    try:
        result = ask(req.message)
    except ClientError as e:
        # AWS が返してきたエラー。権限不足・モデル未有効化・混雑など。
        # 中身をそのまま画面に出すと情報が漏れるので、ログには全部、画面には種別だけ
        code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.exception("bedrock call failed", extra={"extra_fields": {"error_code": code}})
        if code == "ThrottlingException":
            raise HTTPException(status_code=429, detail="混み合っています。少し待って再送してください") from e
        raise HTTPException(status_code=502, detail=f"モデルの呼び出しに失敗しました（{code}）") from e

    logger.info("chat request completed", extra={"extra_fields": {
        "input_tokens": result["input_tokens"],
        "output_tokens": result["output_tokens"],
        "stop_reason": result["stop_reason"],
        "elapsed_ms": result["elapsed_ms"],
    }})

    return ChatResponse(
        reply=result["reply"],
        turns=1,
        input_tokens=result["input_tokens"],
        output_tokens=result["output_tokens"],
        elapsed_ms=result["elapsed_ms"],
        model=settings.bedrock_model_id,
    )


@app.get("/api/suggestions")
def suggestions() -> list[str]:
    """画面の定型質問ボタン。ここを変えると、画面のボタンが変わる（3-2 で画面側をつなぐ）。"""
    return [
        "いま何時？",
        "今日は何曜日？",
        "生成AIのRAGとは何か、3行で説明して",
        "議事録のテンプレートを作って",
    ]
