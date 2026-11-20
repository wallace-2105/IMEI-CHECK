# IMEI CHECK

Sistema interno **100% gratuito, offline e sem anúncios** para validação de IMEIs e identificação de fabricantes e modelos por código TAC (*Type Allocation Code*), desenvolvido para empresas de telemetria, rastreadores, dispositivos IoT e chips M2M.

---

## 1. Funcionalidades

- **Consulta individual:** valida formato (15 dígitos), verifica dígito verificador pelo **algoritmo de Luhn** (3GPP TS 23.003), extrai o TAC (8 primeiros dígitos) e consulta o banco SQLite local.
- **Consulta em lote:** permite colar até **10 IMEIs simultaneamente**, exibindo tabela colorida por status e exportação imediata para Excel (`.xlsx`).
- **Status claros e confiáveis:** `Identificado`, `TAC não encontrado`, `IMEI inválido` e `Erro na consulta`.
- **Histórico local e privacidade:** armazena consultas somente no computador local (`database/imei_database.db`), com opção para **desativar gravação** e botão para **apagar histórico**.
- **Exportação Excel (.xlsx):** gera planilhas formatadas com cabeçalho estilizado, filtro automático, ajuste de largura de colunas e preservação de zeros à esquerda em IMEI/TAC.
- **Atualização segura sem perda de dados:** em caso de falha de rede ou arquivo inválido durante uma atualização, a última base local válida permanece intacta.
- **Importação local (CSV):** permite cadastrar listas internas de TACs de rastreadores/fornecedores diretamente na aba **Banco de dados**.

---

## 2. Tecnologias Utilizadas

- **Python 3.11+** (testado em Python 3.14)
- **Streamlit** (interface web local)
- **SQLite** (banco de dados local offline)
- **Pandas** (visualização tabular)
- **OpenPyXL** (exportação Excel `.xlsx`)
- **Requests** (download das bases públicas gratuitas)
- **Pillow** (ícone da aplicação)
- **Pytest** (testes automatizados)

---

## 3. Origem das Bases TAC Gratuitas

1. **Osmocom TAC Database (Fonte Principal)**
   - Site oficial: `http://tacdb.osmocom.org/`
   - Repositório cliente/documentação: `https://github.com/osmocom/osmo-tacdb` / `https://gitea.osmocom.org/osmocom/osmo-tacdb`
   - Endpoints oficiais utilizados: `/export/tacdb.sqlite3` (primário) e `/export/tacdb.csv` (fallback)
   - Licença: **Creative Commons Attribution-ShareAlike 3.0 Unported (CC-BY-SA v3.0)**
   - Campos: TAC (8 dígitos), fabricante (`brand`), modelo (`model`), nomes alternativos (`aka`), contribuidor, comentário, data do registro e URL de referência.

2. **Base Comunitária Expandida — Optus V36 / IoT (Fonte Complementar Opcional)**
   - Repositório: `https://github.com/MoazEb/tac-database`
   - Licença: **MIT License**
   - Amplia a cobertura gratuita para dispositivos recentes e módulos/rastreadores IoT/M2M (ex.: Quectel, Teltonika, Queclink, Suntech, Maxtrack, Concox, u-blox, Telit, Simcom), mantendo prioridade para registros locais e Osmocom.

> **Garantia de gratuidade:** nenhuma API paga, sistema de créditos, assinatura, chave de API ou scraping de sites com anúncios (como IMEI.info) é utilizado.

---

## 4. Estrutura do Projeto

```text
IMEI-CHECK/
├── .streamlit/
│   └── config.toml
├── app.py
├── requirements.txt
├── README.md
├── instalar.bat
├── iniciar.bat
├── assets/
│   └── logo.png
├── database/
│   └── imei_database.db
├── services/
│   ├── bootstrap.py
│   ├── database_service.py
│   ├── export_service.py
│   ├── imei_validator.py
│   └── tac_service.py
├── components/
│   ├── about.py
│   ├── batch_search.py
│   ├── dashboard.py
│   ├── database_manager.py
│   ├── history.py
│   ├── search.py
│   ├── sidebar.py
│   └── styles.py
└── tests/
    ├── test_database_service.py
    ├── test_export_service.py
    ├── test_imei_validator.py
    ├── test_tac_service.py
    └── test_ui_app.py
```

---

## 5. Como Instalar e Executar (Windows 10 e Windows 11)

### Instalação automática

1. Certifique-se de ter o **Python 3.11 ou superior** instalado no Windows.
2. Dê um duplo clique no arquivo **`instalar.bat`**.
3. O script criará o ambiente virtual `.venv`, instalará as dependências gratuitas e baixará a base TAC local para uso offline.

### Execução diária

1. Dê um duplo clique no arquivo **`iniciar.bat`**.
2. O navegador abrirá automaticamente em `http://localhost:8501` com o painel do **IMEI CHECK**.
3. Após a base baixada, todas as consultas funcionam **100% offline**.

### Execução manual via terminal (opcional)

```bat
.venv\Scripts\python.exe -m streamlit run app.py
```

### Executar testes automatizados

```bat
.venv\Scripts\python.exe -m pytest -v
```

---

## 6. Limitações Conhecidas

- **Cobertura de modelos:** bases públicas gratuitas não contêm 100% de todas as alocações comerciais da GSMA (cuja base completa é paga e restrita). Caso algum rastreador específico não conste na base pública, é possível importá-lo via CSV interno na aba **Banco de dados**.
- **Validade vs. Identificação:** um IMEI aprovado no algoritmo de Luhn pode retornar `TAC não encontrado` caso o lote TAC ainda não tenha sido catalogado na base.
- **Informações de rede:** a consulta TAC não verifica se o aparelho está ligado, conectado à rede celular, com chip M2M ativo ou bloqueado/roubado.
