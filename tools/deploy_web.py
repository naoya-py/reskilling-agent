#!/usr/bin/env python3
"""画面を S3 に置いて、CloudFront から配る（第4回 03-デプロイ手順書 3-x）。

    py ..\\answers\\tools\\deploy_web.py        # Windows
    python3 ../answers/tools/deploy_web.py     # Mac

**`sam deploy` は S3 バケットと CloudFront を作るが、中身は入れない。**
デプロイ直後のバケットは空で、公開 URL を開いても何も出ない。
このスクリプトが、そこに2つのファイルを置く。

  index.html    画面そのもの
  config.json   画面が知りようのない値。**デプロイして初めて決まり、人ごとに違う**

config.json に入るのは5つ。

  apiBase        API の宛先（関数 URL）。ランダムな32文字
  cognitoDomain  ログイン画面の場所
  clientId       Cognito のアプリクライアント ID
  userPoolId     Cognito のユーザープール ID
  redirectUri    ログインしたあとの戻り先（＝自分の公開 URL）

**コードに書かない。**書くと、人ごとに値が違うたびにコードを書き換える羽目になる。
だからデプロイのたびにここで作り直して、外から渡す。

**手で書き写さない。**5つとも長く、1文字違うとログインが通らない。
どこが悪いのかも画面からは分からない。
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REGION = "ap-northeast-1"


def aws(*args: str) -> str:
    """aws コマンドを1つ動かして、標準出力を返す。"""
    try:
        r = subprocess.run(["aws", *args], capture_output=True, text=True, check=True)
    except FileNotFoundError:
        print("aws コマンドが見つかりません。04 の 2-1 を先に済ませ、ターミナルを開き直してください（T-11）")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print("aws コマンドが失敗しました:", " ".join(args[:3]))
        print(e.stderr.strip())
        sys.exit(1)
    return r.stdout.strip()


def main() -> int:
    # スタック名は samconfig.toml に書いてある。ここでも手で打たせない
    cfg = Path("samconfig.toml")
    if not cfg.exists():
        print("samconfig.toml がありません。リポジトリ直下で実行してください（03 の 2-3）")
        return 1
    stack = ""
    for line in cfg.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("stack_name"):
            stack = line.split("=", 1)[1].strip().strip('"')
            break
    if not stack:
        print("samconfig.toml に stack_name がありません。make_samconfig.py をやり直してください")
        return 1

    page = Path("app/web/index.html")
    if not page.exists():
        print("app/web/index.html がありません。リポジトリ直下で実行してください")
        return 1

    # スタックの出力をまとめて1回で取る。7回に分けて叩くと遅い
    raw = aws("cloudformation", "describe-stacks", "--region", REGION,
              "--stack-name", stack, "--query", "Stacks[0].Outputs", "--output", "json")
    out = {o["OutputKey"]: o["OutputValue"] for o in json.loads(raw or "[]")}

    need = ["WebBucketName", "DistributionId", "WebUrl",
            "FunctionUrl", "UserPoolId", "UserPoolClientId", "CognitoDomain"]
    missing = [k for k in need if not out.get(k)]
    if missing:
        print("スタックの出力が足りません:", " ".join(missing))
        print("先に sam deploy を終わらせてください（03 の 2-5）")
        return 1

    bucket = out["WebBucketName"]
    web_url = out["WebUrl"].rstrip("/")
    # 関数 URL は末尾に / が付いてくる。そのまま繋ぐと //api/chat になる
    api = out["FunctionUrl"].rstrip("/")

    config = {
        "apiBase": api,
        "cognitoDomain": out["CognitoDomain"].rstrip("/"),
        "clientId": out["UserPoolClientId"],
        "userPoolId": out["UserPoolId"],
        "redirectUri": web_url + "/",
    }

    print(f"スタック   : {stack}")
    print(f"置き場     : s3://{bucket}")
    print(f"API の宛先 : {api}")
    print()

    with tempfile.TemporaryDirectory() as tmp:
        conf = Path(tmp) / "config.json"
        conf.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

        aws("s3", "cp", str(page), f"s3://{bucket}/index.html",
            "--content-type", "text/html; charset=utf-8",
            "--cache-control", "max-age=60", "--only-show-errors")
        # config.json はキャッシュさせない。
        # 設定を変えたのに古いものが配られると、何が悪いのか画面から分からなくなる
        aws("s3", "cp", str(conf), f"s3://{bucket}/config.json",
            "--content-type", "application/json",
            "--cache-control", "no-cache, no-store, must-revalidate", "--only-show-errors")
    print("2つのファイルを置きました")

    inv = aws("cloudfront", "create-invalidation", "--distribution-id", out["DistributionId"],
              "--paths", "/*", "--query", "Invalidation.Id", "--output", "text")
    print(f"CloudFront のキャッシュを消しています: {inv}（反映まで1〜2分）")

    print()
    print("=" * 60)
    print(f" 公開 URL: {web_url}")
    print("=" * 60)
    print("開くと「利用するにはログインが必要です」と出ます。次は 03 の 3-x（ログイン）へ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
