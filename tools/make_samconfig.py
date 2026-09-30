#!/usr/bin/env python3
r"""samconfig.toml を作る（第4回 03-デプロイ手順書 2-3）。

    py ..\answers\tools\make_samconfig.py yamada-2610       # Windows
    python3 ../answers/tools/make_samconfig.py yamada-2610   # Mac

やること
  1. 受講者 ID の形を確かめる（小文字の 名前-2610。例 yamada-2610）
  2. aws sts get-caller-identity で自分のアカウント ID を拾う
  3. リポジトリ直下に samconfig.toml を書く

手で書くと「3か所の置き換え」を1つ間違えるだけで別の人の ECR に push しようとする。
なので書かせない。**このスクリプトを読むと、samconfig.toml に何が入るかが分かる。**
"""

import json
import re
import subprocess
import sys
from pathlib import Path

REGION = "ap-northeast-1"


def main() -> int:
    if len(sys.argv) != 2 or not re.fullmatch(r"[a-z][a-z0-9]*-2610", sys.argv[1]):
        print("使い方: make_samconfig.py 名前-2610   （例: yamada-2610）")
        return 1
    student = sys.argv[1]

    # aws configure が済んでいれば、自分のアカウント ID が返る
    try:
        out = subprocess.run(
            ["aws", "sts", "get-caller-identity", "--output", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
    except FileNotFoundError:
        print("aws コマンドが見つかりません。04 の 2-1 を先に済ませ、ターミナルを開き直してください（T-11）")
        return 1
    except subprocess.CalledProcessError as e:
        print("aws sts get-caller-identity が失敗しました。04 の 2-2〜2-3 を確認してください（T-12）")
        print(e.stderr.strip())
        return 1

    account = json.loads(out)["Account"]
    ecr = f"{account}.dkr.ecr.{REGION}.amazonaws.com/{student}-agent"
    bucket = f"{student}-sam-{account}"

    body = f"""# sam build / sam deploy の既定値。make_samconfig.py が作った。
# 毎回長いオプションを打たなくて済むように、ここに持たせる。
version = 0.1

[default.global.parameters]
stack_name = "{student}-agent"
region = "{REGION}"

[default.build.parameters]
cached = true

[default.deploy.parameters]
capabilities = "CAPABILITY_IAM"
confirm_changeset = false
s3_bucket = "{bucket}"
s3_prefix = "{student}-agent"
image_repositories = ["AgentFunction={ecr}"]
parameter_overrides = "StudentId={student} PermissionsBoundaryArn=arn:aws:iam::{account}:policy/reskilling-student-boundary"
# **StudentId のタグは消さないこと。** CloudFront と Cognito は名前で絞れないので、
# 「自分のものか」をこのタグで確かめている。無いと作成が拒否される
tags = "Project=reskilling Owner={student} StudentId={student}"
"""
    path = Path("samconfig.toml")
    path.write_text(body, encoding="utf-8")
    print(f"書きました: {path.resolve()}")
    print(f"  スタック名  : {student}-agent")
    print(f"  権限境界    : reskilling-student-boundary")
    print(f"  イメージ先  : {ecr}")
    print(f"  作業用 S3   : {bucket}")
    print("次は 03 の 2-4（sam build）へ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
