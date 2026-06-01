"""
Responsabilidades:
- Conexão com DashScope International (qwen-plus)
- Suporte a function calling (tools)
- Suporte a hybrid thinking mode (thinking=ON/OFF por agente)
- Tratamento de erros e retries
- Interface única para todos os agentes

Uso:
    from src.llm.qwen_client import chat

    resposta = chat(
        messages=[{"role": "user", "content": "Olá"}],
        tools=None,
        enable_thinking=False,
        temperature=0.3
    )
"""

from __future__ import annotations

import os
import time
from typing import Any, Literal
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# CONSTANTES

# Modelo fixo — alterado apenas via variável de ambiente
def _modelo_padrao(backend: str) -> str:
    """Lê o modelo no momento da chamada (não no import).

    Necessário porque `colab_setup.preparar_ambiente()` pode rodar
    depois do primeiro `import` deste módulo — se lêssemos no import,
    a variável atualizada seria ignorada.
    """
    if backend == "dashscope":
        # Default qwen-turbo (~30% mais rápido que qwen-plus pra qualidade
        # aceitável em demo). Override via QWEN_DASHSCOPE_MODEL=qwen-plus
        # se quiser qualidade superior em troca de latência.
        return os.getenv("QWEN_DASHSCOPE_MODEL", "qwen-turbo")
    return os.getenv("QWEN_OLLAMA_MODEL", "qwen:9b")

# Base URLs por backend — dashscope cloud OU ollama on-prem
_DASHSCOPE_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
_OLLAMA_BASE_URL_DEFAULT = "http://localhost:11434/v1"


def _obter_base_url(backend: str) -> str:
    """Retorna a base_url do backend ativo.

    DashScope: URL fixa do endpoint internacional.
    Ollama: lê OLLAMA_BASE_URL (default: localhost:11434) — útil pra rodar
    em outro host ou container.
    """
    if backend == "ollama":
        return os.getenv("OLLAMA_BASE_URL", _OLLAMA_BASE_URL_DEFAULT)
    return _DASHSCOPE_BASE_URL


# Mantido por compat retroativa (Sprint 1 importava esse símbolo)
_BASE_URL = _DASHSCOPE_BASE_URL

# Temperatura padrão por tipo de agente
# Roteador e checkup: baixa — respostas determinísticas
# Triagem e suporte: média — raciocínio mais elaborado
TEMPERATURA_PADRAO = 0.3
TEMPERATURA_RACIOCINIO = 0.5

# Máximo de tokens por resposta
# Reduzido de 1024 para 600 no padrao: respostas medicas tipicas usam
# 150-400 tokens; 600 da folga e corta ~1-2s de geração em casos longos.
MAX_TOKENS_PADRAO = 600
MAX_TOKENS_RACIOCINIO = 1200  # thinking = ON gasta mais tokens (era 2048)

# Cliente OpenAI-compatible — DashScope cloud OU Ollama on-prem
def _obter_cliente(backend: str = "dashscope") -> OpenAI:
    """
    Instancia o cliente OpenAI roteando por backend.

    - dashscope: exige DASHSCOPE_API_KEY (chave do Bailian International)
    - ollama: aceita qualquer string como api_key (Ollama ignora) e usa
      OLLAMA_BASE_URL como endpoint (default localhost:11434)

    Args:
        backend: "dashscope" (default) ou "ollama"

    Raises:
        RuntimeError: backend=dashscope sem DASHSCOPE_API_KEY configurada
    """
    if backend == "ollama":
        # Ollama não autentica via key, mas o SDK OpenAI exige uma string
        # não-vazia. Usamos "ollama" como sentinel — ignorado pelo servidor.
        return OpenAI(api_key="ollama", base_url=_obter_base_url("ollama"))

    # dashscope (default)
    chave = os.getenv("DASHSCOPE_API_KEY")
    if not chave:
        raise RuntimeError(
            "DASHSCOPE_API_KEY não encontrada. "
            "Defina via .env, Colab Secrets ou variável de ambiente. "
            "Alternativa: use backend='ollama' rodando localmente."
        )
    return OpenAI(api_key=chave, base_url=_obter_base_url("dashscope"))

# Função principal de chat
@retry(
    retry = retry_if_exception_type(Exception),
    stop = stop_after_attempt(3),
    wait = wait_exponential(multiplier = 1, min = 2, max = 10),
    reraise = True,
)

def chat(
    messages: list[dict[str, Any]],
    tools: list[dict] | None = None,
    enable_thinking: bool = False,
    temperature: float = TEMPERATURA_PADRAO,
    max_tokens: int | None = None,
    modelo: str | None = None,
    backend: Literal["dashscope", "ollama"] = "dashscope",
) -> dict[str, Any]:
    """
    Envia mensagens ao Qwen via DashScope e retorna a resposta

    Args:
        messages: Histórico de mensagens no formato OpenAI
                  [{"role": "system"|"user"|"assistant", "content": "..."}]
        tools: Lista de tools no formato JSON Schema OpenAI-compatible.
               None desativa function calling.
        enable_thinking: Liga o hybrid thinking mode do Qwen.
                         Use True em agentes de triagem e suporte clínico.
                         Use False no roteador para latência mínima.
        temperature: Temperatura de geração. 0.0 a 1.0.
        max_tokens: Limite de tokens na resposta.
                    Se None, usa MAX_TOKENS_THINKING se thinking=True,
                    senão MAX_TOKENS_PADRAO.
        modelo: Sobrescreve o modelo padrão. Usar com cautela.

    Returns:
        Dicionário com:
        - content (str): texto da resposta
        - tool_calls (list | None): chamadas de tools se houver
        - thinking (str | None): conteúdo do bloco de raciocínio
        - usage (dict): tokens consumidos
        - finish_reason (str): motivo de parada

    Raises:
        RuntimeError: chave não configurada
        Exception: erro de API após 3 tentativas
    """

    cliente = _obter_cliente(backend)

    # Ajustar o max_tokens de acordo com o thinking mode
    if max_tokens is None:
        max_tokens = MAX_TOKENS_RACIOCINIO if enable_thinking else MAX_TOKENS_PADRAO

    # Parâmetros da chamada
    params: dict[str, Any] = {
        "model": modelo or _modelo_padrao(backend),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    # Adiciona tools se forem fornecidas
    if tools:
        params["tools"] = tools
        params["tool_choice"] = "auto"

    # Hybrid thinking mode - parâmetro do Qwen
    # Quando True, o modelo raciocina antes de responder.
    # Gerando um bloco <think>...<think> interno
    if enable_thinking:
        params["extra_body"] = {"enable_thinking": True}

    # Chamada à API
    resposta = cliente.chat.completions.create(**params)
    mensagem = resposta.choices[0].message

    # Extrair o conteúdo de thinking, se houver
    # O Qwen retorna o bloco de raciocínio em reasoning_content

    thinking = None
    if hasattr(mensagem, "reasoning_content"):
        thinking = mensagem.reasoning_content

    # Extrair tool calls, se houver
    tool_calls = None
    if hasattr(mensagem, "tool_calls") and mensagem.tool_calls:
        tool_calls = [
            {
                "id": tc.id,
                "name": tc.function.name,
                "arguments": tc.function.arguments
            }
            for tc in mensagem.tool_calls
        ]
    return {
        "content": mensagem.content or "",
        "tool_calls": tool_calls,
        "thinking": thinking,
        "usage":{
            "prompt_tokens": resposta.usage.prompt_tokens,
            "completion_tokens": resposta.usage.completion_tokens,
            "total_tokens": resposta.usage.total_tokens

        },
        "finish_reason": resposta.choices[0].finish_reason
    }

# Utilitários

def smoke_test() -> bool:
    """
    Ping ao modelo para validar credenciais e conectividade.
    Retorna True se bem-sucedido, False no contrário
    """

    try:
        resposta = chat(
            messages=[
                {
                    "role": "system",
                    "content": "Responda em ma frase curta, em português brasileiro."
                },
                {
                    "role": "user",
                    "content": "Você está funcionando?"
                }
            ],
            enable_thinking= False,
            temperature= 0.1
        )
        print(f"[smoke_test] OK -> resposta: {resposta['content']!r}")
        print(f"[smoke_test] Tokens: {resposta['usage']}")
        return True

    except Exception as e:
        print(f"[smoke_test] FALHOU: {type(e).__name__}: {e}")
        return False

def formatar_mensagens(
        system_prompt: str,
        historico: list[dict],
        mensagem_usuario: str
) -> list[dict]:
    """
    Monta a lista de mensagens no formato esperado pela API.

    Args:
        system_prompt: Conteúdo do system prompt do agente.
        historico: Lista de turnos anteriores
                   [{"role": "user"|"assistant", "content": "..."}]
        mensagem_usuario: Mensagem atual do usuário.

    Returns:
        Lista formatada pronta para passar ao chat().
    """
    mensagens = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]
    mensagens.extend(historico)
    mensagens.append({
        "role": "user",
        "content": mensagem_usuario
    })
    return mensagens


class QwenClient:
    """Versão OO da função `chat`, útil para fixar o backend uma vez.

    Equivalente funcional a chamar `chat(..., backend=self.backend)` em
    todo lugar — existe só para deixar explícito (e auditável via grep)
    qual backend cada consumidor usa.
    """

    def __init__(self, backend: Literal["dashscope", "ollama"] = "dashscope") -> None:
        self.backend = backend

    def chat(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.setdefault("backend", self.backend)
        return chat(**kwargs)