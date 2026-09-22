# tests/test_health.py の**末尾に足す**（第7回 02 の 4-2）。丸ごと差し替えではない。
# 4-2 で run_tool に try を足したあと、これを足して pytest が 9 件になることを確かめる。


def test_run_tool_does_not_raise_on_failure():
    """ tool が失敗しても例外を外に出さず、error を結果として返すこと。

    例外が外に出ると、tool が1つ壊れただけで会話全体が HTTP 500 で落ちる（4-1 で見たもの）。
    error を返せば、モデルはそれを読んで謝るか、別の言い方を試せる。
    """
    assert "error" in run_tool("get_current_time", {"timezone": 999})   # 引数が変
    assert "error" in run_tool("get_weather", {})                       # 無い tool
