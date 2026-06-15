def test_get_frontend_config_uses_real_yaml_not_fallback():
    from core.views import _get_frontend_config
    cfg = _get_frontend_config()
    names = [o["name"] for o in cfg["prompt_options"]]
    # The real YAML has praezise_cot; the hard-coded fallback stub does not.
    # So seeing it proves the importlib hack is gone and the real fn is used.
    assert "praezise_cot" in names


def test_ask_susi_helper_fails_gracefully():
    from core.views import _ask_susi
    # No Ollama/langchain in the gate env -> must return an error STRING, not raise.
    result = _ask_susi("ping")
    assert isinstance(result, str)
    assert result.startswith("[SUSI Fehler]")