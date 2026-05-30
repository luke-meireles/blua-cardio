import pandas as pd
import pickle
import os
from io import StringIO
from azure.storage.blob import BlobServiceClient
from config import caminho_modelo

# Configuração do Blob Storage
CONNECTION_STRING = os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
CONTAINER_NAME = 'dataset'
BLOB_NAME = 'dataset_ppg.csv'

def ler_dataset() -> pd.DataFrame:
    # Conecta ao Blob Storage e lê o CSV
    blob_service = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    blob_client = blob_service.get_blob_client(container= CONTAINER_NAME, blob = BLOB_NAME)

    # Baixa o conteúdo e converte para Dataframe
    conteudo = blob_client.download_blob().readall().decode('utf-8')
    return pd.read_csv(StringIO(conteudo))

def salvar_dataset(df: pd.DataFrame):
    # Converte o Dataframe para CSV em memória
    blob_service = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    blob_client = blob_service.get_blob_client(container= CONTAINER_NAME, blob= BLOB_NAME)

    # Sobe o CSV atualizado para o Blob Storage
    conteudo = df.to_csv(index= False)
    blob_client.upload_blob(conteudo, overwrite=True)

def prever_salvar(dados: pd.DataFrame) -> pd.DataFrame:
    """
    Recebe um DataFrame com as colunas de atributos (sem Status),
    faz a predição, adiciona a coluna 'Status' e anexa as novas
    linhas ao dataset original (dataset_ppg.csv).
 
    Parâmetros
    ----------
    dados : pd.DataFrame
        Deve conter as colunas:
        Timestamp (s), IBI (ms), BPM, Média IBI,
        Desvio Médio, Bat. Anormais (janela)
 
    Retorno
    -------
    pd.DataFrame — dataset original atualizado com as novas linhas
    """
    # Carrega o modelo e os atributos salvos no disco
    with open(caminho_modelo, 'rb') as f:
        artefato = pickle.load(f)

    # Extrai o modelo treinado e a lista de atributos esperados
    m = artefato['modelo']
    atributos = artefato['atributos']

    # Aplica o modelo apenas nas colunas corretas, na ordem certa
    preds = m.predict(dados[atributos])

    # Cria cópia para não modificar o DataFrame original
    novas_linhas = dados.copy()

    # Converte as predições numéricas (0/1) de volta para texto legível
    novas_linhas['Status'] = ['irregular' if p == 1 else 'regular' for p in preds]

    # Carrega o dataset do Blob Storage
    df_original = ler_dataset()

    # Anexa as novas linhas ao final do dataset
    df_atualizado = pd.concat([df_original, novas_linhas], ignore_index=True)

    # Salva o dataset atualizado no Blob Storage
    salvar_dataset(df_atualizado)

    print(f'{len(dados)} nova(s) linha(s) adicionada(s) ao Dataset.')
    return df_atualizado