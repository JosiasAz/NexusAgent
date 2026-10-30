"""Configuração central: variáveis de ambiente, limites e escolha do modelo."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
os.environ['LANGSMITH_TRACING'] = 'false'
os.environ['LANGCHAIN_TRACING_V2'] = 'false'
os.environ['OTEL_SDK_DISABLED'] = 'true'

MAX_TOKENS = int(os.environ.get('MAX_TOKENS', 4096))  # o projeto inteiro volta a cada etapa
MAX_TOKENS_ARQUITETO = int(os.environ.get('MAX_TOKENS_ARQUITETO', 3000))
TIMEOUT_SEGUNDOS = int(os.environ.get('TIMEOUT_SEGUNDOS', 60))
MAX_RODADAS = 2          # rodadas de revisão antes de desistir
MAX_MENSAGEM = 2000      # caracteres aceitos por mensagem do usuário
MAX_TITULO = 80
MAX_DESCRICAO = 1500
MAX_EQUIPES_EM_MEMORIA = 50  # equipes montadas mantidas em cache
VERSAO_INICIAL = '0.1.0'
DB_PATH = Path(os.environ.get('DB_PATH', Path(__file__).resolve().parent.parent / 'data' / 'equipe.db'))

GEMINI_MODELO = os.environ.get('GEMINI_MODEL', 'gemini-3.5-flash-lite')
OLLAMA_CLOUD_MODELO = os.environ.get('OLLAMA_CLOUD_MODEL', 'gemma4:31b')
OLLAMA_LOCAL_MODELO = os.environ.get('OLLAMA_MODEL', 'qwen2.5:7b')


def descrever_modelo():
    """Nome do provedor e do modelo que será usado, sem expor chaves."""
    if os.environ.get('GOOGLE_API_KEY'):
        return f'Gemini · {GEMINI_MODELO}'
    if os.environ.get('OLLAMA_API_KEY'):
        return f'Ollama Cloud · {OLLAMA_CLOUD_MODELO}'
    return f'Ollama local · {OLLAMA_LOCAL_MODELO}'


def criar_modelo(max_tokens=MAX_TOKENS):
    """Escolhe o modelo pelo .env: GOOGLE_API_KEY > OLLAMA_API_KEY > Ollama local."""
    if os.environ.get('GOOGLE_API_KEY'):
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=GEMINI_MODELO, max_output_tokens=max_tokens,
                                      timeout=TIMEOUT_SEGUNDOS, max_retries=5)
    from langchain_ollama import ChatOllama
    chave = os.environ.get('OLLAMA_API_KEY')
    if chave:
        return ChatOllama(model=OLLAMA_CLOUD_MODELO, base_url='https://ollama.com', num_predict=max_tokens,
                          validate_model_on_init=False,
                          client_kwargs={'headers': {'Authorization': 'Bearer ' + chave},
                                         'timeout': TIMEOUT_SEGUNDOS})
    return ChatOllama(model=OLLAMA_LOCAL_MODELO, num_predict=max_tokens,
                      client_kwargs={'timeout': TIMEOUT_SEGUNDOS})
