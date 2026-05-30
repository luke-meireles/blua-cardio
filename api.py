# Receberá os dados da ESP, chamará o modelo e retornará a predição

# Framework para criação da API
from fastapi import FastAPI, HTTPException

# Validação e tipagem dos dados recebidos
from pydantic import BaseModel

import pandas as pd
from predicao import prever_salvar
import os

app = FastAPI(
    title='Care Plus API',
    description= 'API de predição de ritmo cardíaco - regular/irregular',
    version='1.0.0'
)


# Modelo de Entrada
"""
    Define os campos de entrada que a ESP32 deve enviar ao corpo de requisição
    Cada campo tem um tipo de variável esperado - FastAPI valida automaticamente
"""
class DadosCardiacos(BaseModel):
    timestamp: float            # Timestamp (s)
    ibi: float                  # IBI (ms) - intervalo entre os pulsos
    bpm: float                  # BPM - batimentos por minuto
    media_ibi: float            # Media IBI
    desvio_medio: float         # Desvio Médio
    bat_anormais: int           # Bat. Anormais (janelas)


# EndPoint de verificação
# Rota simples para verificar se a API esta online
# Útil para o monitoramento na Azure
@app.get("/")
def status():
    return {"Status": "Care Plus API Online"}

# Endpoint de predição
# Rota principal — recebe os dados do ESP32 e retorna a predição
@app.post("/prever")
def prever(dados: DadosCardiacos):
    try:
        # Converção dos dados para o formato esperado pelo modelo
        # os nomes devem ser idênticos aos presentes no treinamento
        df = pd.DataFrame([{
            'Timestamp (s)':          dados.timestamp,
            'IBI (ms)':               dados.ibi,
            'BPM':                    dados.bpm,
            'Média IBI':              dados.media_ibi,
            'Desvio Médio':           dados.desvio_medio,
            'Bat. Anormais (janela)': dados.bat_anormais
        }])

        resultado = prever_salvar(df)

        # Extrai o status predito da última linha adicionada
        status_predito = resultado.iloc[-1]['Status']

        return {
            'status': status_predito,
            'mensagem': 'Registro salvo com sucesso'
        }
    
    # Captura qualquer erro inesperado e retorna uma mensagem clara a respeito da falha
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
