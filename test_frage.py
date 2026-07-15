
import sys
sys.path.insert(0, '.')
from rag.query import ask_susi
result = ask_susi('Welches Embedding-Modell verwendet SUSI aktuell?', mode='auto')
print('Antwort:', result['answer'][:300])
print('Router:', result['router_profil'])
print('LLM:', result['llm_model'])
print('Chunks:', result['chunks_nach_reranking'])
print('Quellen:', result['quelldateien'])


