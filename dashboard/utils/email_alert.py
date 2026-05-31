# Bloco: envio de email emergêncial
#
# Opt-in via BLUA_EMAIL_ALERTS=enabled. Sem essa flag, retorna silenciosamente
# (decisão de Trabalho 1 — auditoria pós-merge). Justificativa: SMTP é feature
# secundária, e qualquer falha (TypeError em ", ".join([None]), timeout, auth)
# costumava bubblezar pra cima e crashar o callback /monitor (300/2654 janelas
# de 5 batimentos no blob real disparam a chamada).

import os
import smtplib
import time
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()


EMAIL_REMETENTE = os.getenv("EMAIL_REMETENTE")
EMAIL_SENHA = os.getenv("SENHA_REMETENTE")


# Filtra None: se EMAIL_DESTINATARIO_1 ausente, DESTINATARIOS=[] (não [None]),
# evitando TypeError em ", ".join([None]) antes do try/except.
DESTINATARIOS = [d for d in [os.getenv("EMAIL_DESTINATARIO_1")] if d]

ULTIMO_ENVIO = 0
COOLDOWN = 300 # segundos


def _alerts_habilitados() -> bool:
    """Opt-in via env var. Default desabilitado pra evitar surpresa em demo."""
    return os.getenv("BLUA_EMAIL_ALERTS", "disabled").lower() == "enabled"


def _smtp_configurado() -> bool:
    """Vars mínimas pra montar e enviar e-mail."""
    return bool(EMAIL_REMETENTE and EMAIL_SENHA and DESTINATARIOS)


def enviar_alerta(latest, irregulares):
    global ULTIMO_ENVIO

    # Opt-in: sem BLUA_EMAIL_ALERTS=enabled, no-op silencioso
    if not _alerts_habilitados():
        return

    # Defensive: se vars não foram preenchidas, log e retorna
    if not _smtp_configurado():
        print("[Email]: BLUA_EMAIL_ALERTS=enabled mas vars SMTP incompletas "
              "(EMAIL_REMETENTE/SENHA_REMETENTE/EMAIL_DESTINATARIO_1)")
        return

    agora = time.time()

    # evitar spam
    if agora - ULTIMO_ENVIO < COOLDOWN:
        return

    assunto = "ALERTA CARDÍACO - Arritmia detectada"
    html = f"""
    <html>
    <head>
    <style>
        body {{
            font-family: Arial, sans-serif;
            background-color: #f4f7fb;
            padding: 20px;
        }}
        .container {{
            background: white;
            border-radius: 12px;
            padding: 24px;
            max-width: 700px;
            margin: auto;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }}
        .header {{
            background: #0b3d91;
            color: white;
            padding: 18px;
            border-radius: 10px;
            text-align: center;
        }}
        .alert {{
            margin-top: 20px;
            background: #ffebee;
            color: #c62828;
            padding: 16px;
            border-radius: 8px;
            font-weight: bold;
            text-align: center;
            font-size: 18px;
        }}
        .metrics {{
            margin-top: 24px;
        }}
        .metric {{
            background: #f7f9fc;
            padding: 14px;
            border-radius: 8px;
            margin-bottom: 12px;
        }}
        .label {{
            font-size: 13px;
            color: #666;
        }}
        .value {{
            font-size: 22px;
            font-weight: bold;
            color: #0b3d91;
        }}
        .footer {{
            margin-top: 24px;
            font-size: 12px;
            color: #888;
            text-align: center;
        }}
    </style>
    </head>

    <body>

    <div class="container">
        <div class="header">
            <h1>ML CarePlus</h1>
            <p>Sistema Inteligente de Monitoramento Cardíaco</p>
    </div>

    <div class="alert">
        ⚠ ALERTA DE ARRITMIA PERSISTENTE DETECTADA
    </div>

    <div class="metrics">

        <div class="metric">
            <div class="label">Status</div>
            <div class="value">{latest['status']}</div>
        </div>

        <div class="metric">
            <div class="label">BPM Atual</div>
            <div class="value">{latest['bpm']:.0f} bpm</div>
        </div>

        <div class="metric">
            <div class="label">IBI Atual</div>
            <div class="value">{latest['ibi_ms']:.0f} ms</div>
        </div>

        <div class="metric">
            <div class="label">Desvio Médio</div>
            <div class="value">{latest['desvio_medio']:.0f} ms</div>
        </div>

        <div class="metric">
            <div class="label">Registros Irregulares</div>
            <div class="value">{irregulares}/5</div>
        </div>

    </div>

    <div class="footer">
        ML CarePlus • Monitoramento em Tempo Real
    </div>

</div>

</body>
</html>
"""
    
    # try/except cobre TUDO: construção MIME + SMTP + cleanup. Antes só cobria
    # smtplib.SMTP() e descendentes — o ", ".join(DESTINATARIOS) (L148 original)
    # ficava de fora, então TypeError com DESTINATARIOS=[None] bubblezava pra
    # cima e crashava o callback _render do /monitor.
    try:
        email = MIMEMultipart()
        email["From"] = EMAIL_REMETENTE
        email["To"] = ", ".join(DESTINATARIOS)
        email["Subject"] = assunto

        email.attach(MIMEText(html, "html"))

        servidor = smtplib.SMTP("smtp.gmail.com", 587)
        servidor.starttls()

        servidor.login(EMAIL_REMETENTE, EMAIL_SENHA)

        servidor.sendmail(
            EMAIL_REMETENTE,
            DESTINATARIOS,
            email.as_string()
        )

        servidor.quit()

        ULTIMO_ENVIO = agora
        print("[Email]: Alerta enviado com sucesso.")

    except Exception as e:
        print(f"[Email]: Erro ao enviar o alerta -> {type(e).__name__}: {e}")