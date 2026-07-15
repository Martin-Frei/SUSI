
import sys
sys.path.insert(0, '.')
from rag.query import ask_susi_eval
result = ask_susi_eval('Welches Embedding-Modell verwendet SUSI aktuell?')
print('Antwort:', repr(result['answer'][:300]))
print('Router:', result['router_profil'])
print('LLM:', result['llm_model'])
print('Chunks nach Reranking:', result['chunks_nach_reranking'])
print('Kontext nach Reranking:', repr(result['kontext_nach_reranking'][:200]))


