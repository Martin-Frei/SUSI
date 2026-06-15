from rag.query import get_frontend_config, build_prompt, SYSTEM_PROMPTS

REQUIRED = {
    "llm_options", "prompt_options", "top_k_min", "top_k_max", "top_k_default",
    "temperature_min", "temperature_max", "temperature_step",
    "temperature_default", "prompt_default", "llm_default",
}


def test_frontend_config_has_required_keys():
    assert REQUIRED.issubset(get_frontend_config().keys())


def test_frontend_config_defaults():
    cfg = get_frontend_config()
    assert cfg["top_k_default"] == 8
    assert cfg["temperature_default"] == 0.0
    assert cfg["prompt_default"] == "susi_standard"


def test_prompt_options_are_name_label_pairs():
    for opt in get_frontend_config()["prompt_options"]:
        assert "name" in opt and "label" in opt


def test_system_prompts_loaded_from_yaml():
    assert "susi_standard" in SYSTEM_PROMPTS
    assert "praezise_cot" in SYSTEM_PROMPTS


def test_build_prompt_with_cot_prompt():
    p = build_prompt("q", "ctx", "01.01.2026", system_prompt="praezise_cot")
    assert "Schritt für Schritt" in p
    assert "ctx" in p
