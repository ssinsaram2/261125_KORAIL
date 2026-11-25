"""[1.5] 블록 AI 추천(Ollama) — 가짜 Ollama 서버로 시험한다(진짜 모델 없이도 돈다)."""
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from prompt98 import ai
from prompt98.dialogs.suggest import merge
from prompt98.model import Block, Template, Variable


def tmpl() -> Template:
    t = Template(name="열차 지연 안내문", category="고객·민원")
    t.variables = [Variable("지연시간", "number"), Variable("안내채널", "select", "문자,코레일톡")]
    t.blocks = [Block("role", content="당신은 코레일 고객 안내 담당자입니다."),
                Block("constraint", content="- 300자 이내"), Block("format")]
    return t


# ---------------------------------------------------------------- 질문·답 정리
def test_messages_carry_template_context():
    t = tmpl()
    sys_msg, user = ai.build_messages(t, t.blocks[2])
    assert sys_msg["role"] == "system" and "JSON" in sys_msg["content"]
    u = user["content"]
    assert "열차 지연 안내문" in u and "{{지연시간}}(숫자)" in u and "{{안내채널}}(선택 목록)" in u
    assert "[역할] 당신은 코레일" in u                       # 다른 블록 내용이 들어감
    assert "출력 형식" in u and "비어 있음" in u


def test_messages_ask_for_additions_when_block_has_content():
    t = tmpl()
    u = ai.build_messages(t, t.blocks[1])[1]["content"]
    assert "이어 붙일" in u and "- 300자 이내" in u
    assert "[조건·제약]" not in u                            # 자기 자신은 '다른 블록'에 넣지 않음


def test_clean_strips_unknown_vars_and_numbering():
    names = {"지연시간"}
    assert ai.clean_suggestion("1. {{지연시간}}분 지연 시 {{보상금액}} 안내", names) == "{{지연시간}}분 지연 시 보상금액 안내"
    assert ai.clean_suggestion("- - 존댓말로 쓸 것\n- • 짧게", names) == "- 존댓말로 쓸 것\n- 짧게"
    assert len(ai.clean_suggestion("가" * 2000, names)) == ai.MAX_LEN


def test_parse_json_dedupes_and_limits():
    text = json.dumps({"suggestions": ["A", "A", " ", "B", "C", "D"]})
    assert ai.parse_suggestions(text, set()) == ["A", "B", "C"]
    assert ai.parse_suggestions(text, set(), current="A") == ["B", "C", "D"]   # 지금 내용과 같은 것은 뺌


def test_parse_falls_back_to_paragraphs_and_survives_garbage():
    assert ai.parse_suggestions("첫째 추천\n\n둘째 추천", set()) == ["첫째 추천", "둘째 추천"]
    assert ai.parse_suggestions('{"suggestions": [', set()) == []
    assert ai.parse_suggestions('{"other": 1}', set()) == []


def test_merge_modes():
    assert merge("- 300자 이내\n", "- 존댓말", "append") == "- 300자 이내\n- 존댓말"
    assert merge("기존", "새 글", "replace") == "새 글"
    assert merge("  ", "새 글", "append") == "새 글"


def test_config_from_settings():
    class S(dict):
        def get(self, k, d=None):
            return super().get(k, d)
    c = ai.AIConfig.from_settings(S(ai_url="http://10.0.0.5:11434/ ", ai_model=" llama3 "))
    assert (c.url, c.model) == ("http://10.0.0.5:11434", "llama3")
    c = ai.AIConfig.from_settings(S())
    assert (c.url, c.model) == (ai.DEFAULT_URL, ai.DEFAULT_MODEL)


# ---------------------------------------------------------------- 가짜 Ollama 서버
class Fake:
    models = ["gemma4:latest"]
    chunks: list = []
    status = 200
    last_body: dict | None = None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        body = json.dumps({"models": [{"name": n} for n in Fake.models]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        Fake.last_body = json.loads(self.rfile.read(n))
        if Fake.status != 200:
            body = json.dumps({"error": f"model '{Fake.last_body['model']}' not found"}).encode()
            self.send_response(Fake.status)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.end_headers()
        for i, c in enumerate(Fake.chunks):
            msg = {"message": {"role": "assistant", "content": c}, "done": i == len(Fake.chunks) - 1}
            self.wfile.write((json.dumps(msg, ensure_ascii=False) + "\n").encode())
            self.wfile.flush()


class QuietServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address):   # 취소 시험에서 끊긴 연결은 조용히
        pass


@pytest.fixture
def server():
    Fake.models, Fake.status, Fake.last_body = ["gemma4:latest"], 200, None
    answer = json.dumps({"suggestions": ["- {{지연시간}}분 이상이면 사과문을 먼저", "- {{없는변수}} 안내"]},
                        ensure_ascii=False)
    Fake.chunks = [answer[i:i + 7] for i in range(0, len(answer), 7)]   # 조각조각 스트리밍
    srv = QuietServer(("127.0.0.1", 0), Handler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    yield ai.AIConfig(url=f"http://127.0.0.1:{srv.server_address[1]}", timeout=10)
    srv.shutdown()
    srv.server_close()


def test_check_ok_and_missing_model(server):
    assert "gemma4:latest" in ai.check(server)
    Fake.models = ["llama3:latest"]
    with pytest.raises(ai.AIError, match="ollama pull gemma4"):
        ai.check(server)


def test_suggest_streams_and_cleans(server):
    t = tmpl()
    seen = []
    out = ai.suggest(server, t, t.blocks[1], progress=seen.append)
    assert out == ["- {{지연시간}}분 이상이면 사과문을 먼저", "- 없는변수 안내"]
    assert seen and seen[-1] == sum(map(len, Fake.chunks))
    body = Fake.last_body
    assert body["model"] == "gemma4" and body["think"] is False and body["stream"] is True
    assert body["format"]["required"] == ["suggestions"]


def test_suggest_cancel_returns_nothing(server):
    t = tmpl()
    ev = threading.Event()
    ev.set()
    assert ai.suggest(server, t, t.blocks[1], ev) == []


def test_suggest_model_not_found(server):
    Fake.status = 404
    t = tmpl()
    with pytest.raises(ai.AIError, match="모델을 찾지 못했어요"):
        ai.suggest(server, t, t.blocks[1])


def test_suggest_empty_answer_is_error(server):
    Fake.chunks = ['{"suggestions": []}']
    t = tmpl()
    with pytest.raises(ai.AIError, match="다시 추천"):
        ai.suggest(server, t, t.blocks[1])


def test_unreachable_server_message():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()                                               # 아무도 듣지 않는 포트
    cfg = ai.AIConfig(url=f"http://127.0.0.1:{port}", timeout=3)
    with pytest.raises(ai.AIError, match="Ollama 에 연결하지 못했어요"):
        ai.check(cfg, timeout=3)
    t = tmpl()
    with pytest.raises(ai.AIError, match="켜져 있는지"):
        ai.suggest(cfg, t, t.blocks[0])
