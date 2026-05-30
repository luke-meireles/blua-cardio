"""
Monitor CSV em tempo real — Care Plus
Lê o dataset_ppg.csv do Azure Blob Storage e exibe novas linhas conforme chegam.
"""
import os
import time
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

# --- Configuração ---
load_dotenv()

CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME    = "dataset"
BLOB_NAME         = "dataset_ppg.csv"
INTERVALO_SEGUNDOS = 1  # frequência de verificação

COLUNAS = [
    "Timestamp (s)", "IBI (ms)", "BPM",
    "Média IBI", "Desvio Médio", "Bat. Anormais (janela)", "Status"
]

LARGURA = [14, 10, 8, 12, 14, 22, 10]

def formatar_cabecalho():
    return " | ".join(c.ljust(LARGURA[i]) for i, c in enumerate(COLUNAS))


def formatar_linha(linha: str):
    valores = linha.strip().split(",")
    if len(valores) != len(COLUNAS):
        return None
    return " | ".join(v.ljust(LARGURA[i]) for i, v in enumerate(valores))


def ler_blob() -> list:
    client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    blob = client.get_blob_client(container=CONTAINER_NAME, blob=BLOB_NAME)
    conteudo = blob.download_blob().readall().decode("utf-8")
    linhas = conteudo.strip().splitlines()
    # Remove cabeçalho
    if linhas and "Timestamp" in linhas[0]:
        linhas = linhas[1:]
    return linhas


def main():
    if not CONNECTION_STRING:
        print("[ERRO] AZURE_STORAGE_CONNECTION_STRING não encontrada no .env")
        return

    print("=" * 100)
    print(" CARE PLUS — Monitor de Dados Cardíacos em Tempo Real")
    print("=" * 100)
    print(formatar_cabecalho())
    print("-" * 100)

    linhas_vistas = set()

    # Carrega estado inicial sem exibir
    try:
        iniciais = ler_blob()
        for linha in iniciais:
            linhas_vistas.add(linha.strip())
        print(f"[monitor] {len(linhas_vistas)} registros existentes carregados. Aguardando novos...\n")
    except Exception as e:
        print(f"[ERRO] Não foi possível conectar ao Blob: {e}")
        return

    try:
        while True:
            time.sleep(INTERVALO_SEGUNDOS)
            try:
                atuais = ler_blob()
                for linha in atuais:
                    linha_limpa = linha.strip()
                    if linha_limpa and linha_limpa not in linhas_vistas:
                        linhas_vistas.add(linha_limpa)
                        formatada = formatar_linha(linha_limpa)
                        if formatada:
                            # Colorir status
                            if "irregular" in linha_limpa:
                                print(f"\033[91m{formatada}\033[0m", flush=True)
                            else:
                                print(f"\033[92m{formatada}\033[0m", flush=True)
            except Exception as e:
                print(f"[ERRO] Falha ao ler blob: {e}", flush=True)

    except KeyboardInterrupt:
        print("\n[monitor] Encerrado pelo usuário.")


if __name__ == "__main__":
    main()