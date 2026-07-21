from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        import os, threading
        if os.environ.get('RUN_MAIN') == 'true':
            threading.Thread(target=self._warmup, daemon=True).start()

    @staticmethod
    def _warmup():
        import requests
        import yaml
        import os

        config_path = os.path.join(os.path.dirname(__file__), '..', 'rag', 'susi_config.yaml')
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f)

        model = cfg['generation']['llm_model']
        keep_alive = cfg['generation']['keep_alive']

        try:
            print(f"  🔥 Warmup: {model}")
            requests.post("http://localhost:11434/api/generate", json={
                "model": model,
                "prompt": "Hi",
                "stream": False,
                "keep_alive": keep_alive,
                "options": {"num_ctx": 32, "num_predict": 1}
            }, timeout=60)
            print(f"  ✅ {model} loaded")
        except Exception as e:
            print(f"  ⚠ Warmup failed: {e}")

        try:
            reranker_model = cfg.get('reranker', {}).get('model', '')
            if reranker_model:
                print(f"  🔥 Warmup Reranker: {reranker_model}")
                from rag.query import get_reranker
                get_reranker()
                print(f"  ✅ Reranker loaded (CPU)")
        except Exception as e:
            print(f"  ⚠ Reranker warmup failed: {e}")

        print("  🚀 Warmup complete")