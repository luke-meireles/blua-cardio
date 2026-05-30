/**
 * Simulador ESP32 — Care Plus
 * Recebe IBI via stdin, calcula os atributos cardíacos
 * e envia JSON via HTTPS POST para a API na Azure.
 */

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winsock2.h>
#include <ws2tcpip.h>
#pragma comment(lib, "ws2_32.lib")

#include <openssl/ssl.h>
#include <openssl/err.h>

#include <iostream>
#include <sstream>
#include <string>
#include <array>
#include <cmath>
#include <algorithm>
#include <iomanip>

// ── Configurações da API ───────────────────────────────────────
const std::string API_HOST = "api-predicaocardiaca-cpc0bufrhmd7ade4.brazilsouth-01.azurewebsites.net";
const std::string API_PATH = "/prever";
const int         API_PORT = 443;

// ── Janela deslizante ──────────────────────────────────────────
const int   JANELA_SIZE    = 5;
const float LIMIAR_ANORMAL = 100.0f;

float janela[JANELA_SIZE] = {0};
int   contador_global     = 0;
float timestamp_s         = 0.0f;


// ── Funções de cálculo ─────────────────────────────────────────

int tamanho_valido() {
    return std::min(contador_global, JANELA_SIZE);
}

float calcular_media() {
    int n = tamanho_valido();
    if (n == 0) return 0.0f;
    float soma = 0.0f;
    for (int i = 0; i < n; i++) {
        soma += janela[i];
    }
    return soma / n;
}

float calcular_desvio_medio(float media) {
    int n = tamanho_valido();
    if (n == 0) return 0.0f;
    float soma = 0.0f;
    for (int i = 0; i < n; i++) {
        soma += std::fabs(janela[i] - media);
    }
    return soma / n;
}

int calcular_batimentos_anormais(float media) {
    int n = tamanho_valido();
    int count = 0;
    for (int i = 0; i < n; i++) {
        if (std::fabs(janela[i] - media) > LIMIAR_ANORMAL) {
            count++;
        }
    }
    return count;
}


// ── Montagem do JSON ───────────────────────────────────────────

std::string montar_json(float ts, float ibi, float bpm,
                        float media, float desvio, int anormais) {
    std::ostringstream oss;
    oss << std::fixed << std::setprecision(2);
    oss << "{"
        << "\"timestamp\":"    << ts      << ","
        << "\"ibi\":"          << ibi     << ","
        << "\"bpm\":"          << bpm     << ","
        << "\"media_ibi\":"    << media   << ","
        << "\"desvio_medio\":" << desvio  << ","
        << "\"bat_anormais\":" << anormais
        << "}";
    return oss.str();
}


// ── HTTPS POST via OpenSSL ─────────────────────────────────────

bool enviar_post(const std::string& body) {
    // Inicializar OpenSSL
    SSL_CTX* ctx = SSL_CTX_new(TLS_client_method());
    if (!ctx) {
        std::cerr << "[esp32] Erro: falha ao criar contexto SSL." << std::endl;
        return false;
    }

    // Resolver host
    struct addrinfo hints{}, *res = nullptr;
    hints.ai_family   = AF_INET;
    hints.ai_socktype = SOCK_STREAM;

    if (getaddrinfo(API_HOST.c_str(), std::to_string(API_PORT).c_str(), &hints, &res) != 0) {
        std::cerr << "[esp32] Erro: nao foi possivel resolver o host." << std::endl;
        SSL_CTX_free(ctx);
        return false;
    }

    // Criar socket
    SOCKET sock = socket(res->ai_family, res->ai_socktype, res->ai_protocol);
    if (sock == INVALID_SOCKET) {
        std::cerr << "[esp32] Erro: nao foi possivel criar socket." << std::endl;
        freeaddrinfo(res);
        SSL_CTX_free(ctx);
        return false;
    }

    // Conectar
    if (connect(sock, res->ai_addr, (int)res->ai_addrlen) != 0) {
        std::cerr << "[esp32] Erro: nao foi possivel conectar." << std::endl;
        closesocket(sock);
        freeaddrinfo(res);
        SSL_CTX_free(ctx);
        return false;
    }

    freeaddrinfo(res);

    // Criar SSL sobre o socket
    SSL* ssl = SSL_new(ctx);
    SSL_set_fd(ssl, (int)sock);
    SSL_set_tlsext_host_name(ssl, API_HOST.c_str());

    if (SSL_connect(ssl) != 1) {
        std::cerr << "[esp32] Erro: handshake SSL falhou." << std::endl;
        SSL_free(ssl);
        closesocket(sock);
        SSL_CTX_free(ctx);
        return false;
    }


    // Montar requisição HTTP
    std::ostringstream req;
    req << "POST " << API_PATH << " HTTP/1.1\r\n"
        << "Host: " << API_HOST << "\r\n"
        << "Content-Type: application/json\r\n"
        << "Content-Length: " << body.size() << "\r\n"
        << "Connection: close\r\n"
        << "\r\n"
        << body;

    std::string request = req.str();
    SSL_write(ssl, request.c_str(), (int)request.size());

    // Ler resposta
    char buffer[4096] = {0};
    std::string resposta;
    int bytes;
    while ((bytes = SSL_read(ssl, buffer, sizeof(buffer) - 1)) > 0) {
        buffer[bytes] = '\0';
        resposta += buffer;
    }

    // Encerrar SSL
    SSL_shutdown(ssl);
    SSL_free(ssl);
    closesocket(sock);
    SSL_CTX_free(ctx);

    // Extrair body da resposta HTTP
    auto pos = resposta.find("\r\n\r\n");
    if (pos != std::string::npos) {
        std::string resp_body = resposta.substr(pos + 4);
        // Remover eventuais espaços ou quebras extras
        while (!resp_body.empty() && (resp_body.back() == '\n' || 
                                       resp_body.back() == '\r' || 
                                       resp_body.back() == ' ')) {
            resp_body.pop_back();
        }
        std::cout << resp_body << "\n" << std::flush;
        return true;
    }

    return false;
}

// ── Main ───────────────────────────────────────────────────────

int main() {
    std::cerr << "[esp32] Processo iniciado." << std::endl;
    std::cerr.flush();
    // Inicializar Winsock
    WSADATA wsa;
    WSAStartup(MAKEWORD(2, 2), &wsa);

    std::string linha;

    while (std::getline(std::cin, linha)) {
        if (linha.empty()) continue;

        // Converter para float
        float ibi;
        try {
            ibi = std::stof(linha);
        } catch (...) {
            continue;
        }

        // Validar IBI fisiológico
        if (ibi < 300.0f || ibi > 2000.0f) continue;

        // Atualizar timestamp
        timestamp_s += ibi / 1000.0f;

        // Inserir na janela deslizante
        janela[contador_global % JANELA_SIZE] = ibi;
        contador_global++;

        // Calcular atributos
        float bpm    = 60000.0f / ibi;
        float media  = calcular_media();
        float desvio = calcular_desvio_medio(media);
        int anormais = calcular_batimentos_anormais(media);

        // Montar JSON
        std::string json = montar_json(timestamp_s, ibi, bpm, media, desvio, anormais);

        // Enviar para API
        enviar_post(json);
    }

    WSACleanup();
    return 0;
}