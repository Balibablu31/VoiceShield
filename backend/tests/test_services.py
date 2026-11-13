from app import services


class StubPipeline:
    def __init__(self, result):
        self.result = result

    def __call__(self, *args, **kwargs):
        return self.result


def test_text_pipeline_accepts_flat_transformers_outputs(monkeypatch):
    monkeypatch.setattr(services, "_pipeline", lambda model_id: StubPipeline([
        {"label": "Fake", "score": 0.8}, {"label": "Real", "score": 0.2},
    ]))
    result = services.classify_text("A long enough test claim.", "en")
    assert result["model_status"] == "ready"
    assert result["verdict"] == "fake"
    assert result["risk_score"] == 80.0


def test_text_pipeline_accepts_nested_transformers_outputs(monkeypatch):
    monkeypatch.setattr(services, "_pipeline", lambda model_id: StubPipeline([[
        {"label": "Real", "score": 0.9}, {"label": "Fake", "score": 0.1},
    ]]))
    result = services.classify_text("A long enough test claim.", "en")
    assert result["model_status"] == "ready"
    assert result["verdict"] == "real"
    assert result["risk_score"] == 10.0
