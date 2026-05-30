"""
Gerador de IBI simulado - Care Plus
Simula um sensor PPG gerando valores de IBI realistas
e os envia ao simulador_esp32 via stdin.
"""

import subprocess
import time
import random
import os
import sys
import threading

# --- Configurações ---

IBI_NORMAL_MIN = 600    # ms
IBI_NORMAL_MAX = 1000   # ms
IBI_ARRITMIA_MIN = 300  # ms
IBI_ARRITMIA_MAX = 1800 # ms

BATIMENTOS_NORMAIS_MIN = 15     # mínimo de batimentos normais antes de uma arritmia
BATIMENTOS_NORMAIS_MAX = 25     # máximo
BATIMENTOS_ARRITMIAS_MIN = 3    # mínimo de batimentos no bloco irregular
BATIMENTOS_ARRITMIAS_MAX = 6    # máximo

FATOR_VELOCIDADE = 10       # divide o delay real — 1 = tempo real, 10 = 10x mais rápido

# --- Caminho do executável C++ ---

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SIMULADOR_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", "simulador_esp32"))
NOME_EXE = "simulador_esp32.exe" if sys.platform == "win32" else "simulador_esp32"
EXECUTAVEL = os.path.join(SIMULADOR_DIR, NOME_EXE)

# --- Geradores por tipo de arritmia ---

def gerar_ibi_normal(ibi_anterior: float) -> float:
    # Variação suave em torno do IBI anterior - ritmo saudável.
    variacao = random.uniform(-30, 30)
    novo = ibi_anterior + variacao
    return max(IBI_NORMAL_MIN, min(IBI_NORMAL_MAX, novo))

def gerar_bloco_taquicardia(tamanho: int) -> list:
    """
    IBIs curtos e regulares.
    Simula frequência acima de 100 BPM (IBI < 600ms)
    """
    base = random.uniform(350, 500)
    return [round(base + random.uniform(-20, 20), 2) for _ in range(tamanho)]

def gerar_bloco_bradicardia(tamanho: int) -> list:
    """
    IBIs longos e regulares.
    Simula frequência cardíaca abaixo de 60 BPM (IBI > 1000ms)
    """
    base = random.uniform(1100, 1600)
    return [round(base + random.uniform(-30, 30), 2) for _ in range(tamanho)]

def gerar_bloco_fibrilacao_atrial(tamanho: int) -> list:
    """
    IBIs completamente caóticos e sem padrão.
    Alta variância - assinatura característica FA.
    """
    return[round(random.uniform(400, 1200), 2) for _ in range(tamanho)]

def gerar_bloco_extrassistole(ibi_anterior: float) -> list:
    """
    Um IBI muito curto (batimento precoce) seguido de uma pausa compensatória longa. Geralmente 2 batimentos
    """
    ibi_curto = round(random.uniform(300, 450), 2)
    pausa = round(ibi_anterior * 1.8 + random.uniform(-50, 50), 2)
    pausa = min(pausa, 1800)
    return[ibi_curto, pausa]

TIPOS_ARRITMIA = ["taquicardia", "bradicardia", "fibrilacao_atrial", "extrassistole"]

def gerar_bloco_arritmia(tipo: str, tamanho: int, ibi_anterior: float) -> list:
    if tipo == "taquicardia":
        return gerar_bloco_taquicardia(tamanho)
    
    elif tipo == "bradicardia":
        return gerar_bloco_bradicardia(tamanho)
    
    elif tipo == "fibrilacao_atrial":
        return gerar_bloco_fibrilacao_atrial(tamanho)
    
    elif tipo == "extrassistole":
        return gerar_bloco_extrassistole(ibi_anterior)
    
    return[]

# --- Principal ---
def ler_stdout(processo):
    """Lê o stdout do C++ em uma thread separada."""
    for linha in processo.stdout:
        print(f"[esp32 ] {linha.strip()}", flush=True)


def main():
    print(f"[gerador] Iniciando processo C++: {EXECUTAVEL}", flush=True)

    try:
        processo = subprocess.Popen(
            [EXECUTAVEL],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,
            text=True,
            bufsize=0
        )
    except FileNotFoundError:
        print(f"[ERRO] Executável não encontrado: {EXECUTAVEL}", flush=True)
        print(f"[ERRO] Compile o simulador_esp32 antes de rodar este script.", flush=True)
        sys.exit(1)

    print("[gerador] Processo Iniciado. Enviando IBIs...\n", flush=True)

    # Thread separada para ler stdout do C++
    thread_stdout = threading.Thread(target=ler_stdout, args=(processo,), daemon=True)
    thread_stdout.start()

    ibi_atual = 800.0
    contador_normais = 0
    proxima_arritmia = random.randint(BATIMENTOS_NORMAIS_MIN, BATIMENTOS_NORMAIS_MAX)
    fila_arritmia = []

    try:
        while True:
            # --- Gerar próximo IBI ---
            if fila_arritmia:
                ibi_atual = fila_arritmia.pop(0)

            elif contador_normais >= proxima_arritmia:
                tipo = random.choice(TIPOS_ARRITMIA)
                tamanho = random.randint(BATIMENTOS_ARRITMIAS_MIN, BATIMENTOS_ARRITMIAS_MAX)
                fila_arritmia = gerar_bloco_arritmia(tipo, tamanho, ibi_atual)
                ibi_atual = fila_arritmia.pop(0)
                contador_normais = 0
                proxima_arritmia = random.randint(BATIMENTOS_NORMAIS_MIN, BATIMENTOS_NORMAIS_MAX)
                print(f"[gerador] >>> Arritmia: {tipo.upper()} "
                      f"({len(fila_arritmia) + 1} batimentos)", flush=True)

            else:
                ibi_atual = gerar_ibi_normal(ibi_atual)
                contador_normais += 1

            # --- Envia IBI para o C++ ---
            try:
                processo.stdin.write(f"{ibi_atual:.2f}\n")
                processo.stdin.flush()
            except OSError:
                break

            # --- Verificar se o processo C++ ainda está ativo ---
            if processo.poll() is not None:
                print(f"[ERRO] Processo C++ encerrou inesperadamente. Código: {processo.poll()}", flush=True)
                break

            # --- Delay simulando tempo real ---
            time.sleep(ibi_atual / 1000.0 / FATOR_VELOCIDADE)

    except KeyboardInterrupt:
        print("\n[gerador] Interrompido pelo usuário. Encerrando...", flush=True)
    finally:
        processo.stdin.close()
        processo.wait(timeout=3)
        print("[gerador] Processo C++ encerrado.", flush=True)


if __name__ == "__main__":
    main()