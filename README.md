# Hemogram API

![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.85%2B-green.svg)
![PyMuPDF](https://img.shields.io/badge/PyMuPDF-1.22%2B-red.svg)
![Supabase](https://img.shields.io/badge/Supabase-Integration-darkgreen.svg)

## 📖 Visão Geral

A **Hemogram API** é uma solução de backend projetada para processar laudos de exames de sangue em formato PDF. Ela expõe um endpoint simples que recebe um arquivo e um ID de cliente, acionando um pipeline de extração de dados que:

1.  Lê o conteúdo do PDF, palavra por palavra, com suas coordenadas.
2.  Agrupa palavras em linhas de forma eficiente, mesmo em layouts mais complexos.
3.  Identifica métricas de saúde conhecidas (ex: "Hemoglobina", "Colesterol LDL") usando um mapa de normalização.
4.  Busca e extrai os valores numéricos associados a cada métrica, lidando com diferentes formatos.
5.  Estrutura os dados extraídos em um DataFrame do Pandas, adicionando unidades de medida.
6.  Envia os resultados processados para um banco de dados Supabase.
7.  Retorna um JSON estruturado para o cliente.

## 🚀 Funcionalidades Principais

-   **Extração Inteligente de PDF**: Utiliza a biblioteca `PyMuPDF` para uma análise do layout do documento, permitindo a extração precisa de dados mesmo em PDFs com formatação variada.
-   **Normalização de Métricas**: Converte diferentes nomenclaturas de exames (ex: "hdl", "colesterol hdl") para um formato padronizado, garantindo a consistência dos dados.
-   **Parser de Valores Numéricos**: Capaz de interpretar e converter múltiplos formatos numéricos (ex: `1.234,56`, `3,5`, `10 x 10^3`) para o tipo `float`.
-   **Integração com Supabase**: Salva os resultados extraídos de forma estruturada no banco de dados, associando-os a um usuário e a uma data de exame.
-   **API com FastAPI**: Oferece uma interface moderna, rápida e com documentação automática (Swagger UI) para interagir com o serviço.
-   **Validação de Entrada**: Garante que os arquivos enviados sejam válidos e parâmetros.

## 🛠️ Tecnologias Utilizadas

-   **Backend**: [FastAPI](https://fastapi.tiangolo.com/)
-   **Processamento de PDF**: [PyMuPDF (fitz)](https://github.com/pymupdf/PyMuPDF)
-   **Manipulação de Dados**: [Pandas](https://pandas.pydata.org/)
-   **Banco de Dados**: [Supabase](https://supabase.io/) (via `supabase-py`)
-   **Variáveis de Ambiente**: [python-dotenv](https://github.com/theskumar/python-dotenv)
-   **Servidor ASGI**: [Uvicorn](https://www.uvicorn.org/)

---

## 🌐 API Pública (Live Demo)

Esta API está hospedada na plataforma Render e pode ser acessada publicamente, sem a necessidade de configuração local.

**URL Base:** `https://tcc-t47r.onrender.com`

Você pode interagir diretamente com os endpoints utilizando esta URL.

### Exemplo de Uso com `curl` (Live)

Para testar o processamento de um hemograma na API pública, utilize o comando abaixo, substituindo `cliente-exemplo-live` pelo ID desejado e `/caminho/para/seu/exame.pdf` pelo caminho real do seu arquivo:

```bash
curl -X POST "https://tcc-t47r.onrender.com/hemogramToDataBase/id-cliente-exemplo-live" \
     -F "file=@/caminho/para/seu/exame.pdf"
```

---

## ⚙️ Configuração do Ambiente Local

1.  **Clone o repositório:**
    ```bash
    git clone https://github.com/AldoJDev/Hemogram-reader_API.git
    cd hemogram-api
    ```

2.  **Crie e ative um ambiente virtual:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # No Windows: venv\Scripts\activate
    ```

3.  **Crie um arquivo `requirements.txt`** com as seguintes dependências:
    ```txt
    fastapi
    uvicorn[standard]
    python-multipart
    pandas
    PyMuPDF
    supabase
    python-dotenv
    ```

4.  **Instale as dependências:**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Configure as variáveis de ambiente:**
    Crie um arquivo chamado `.env` na raiz do projeto e adicione suas credenciais do Supabase:
    ```env
    supabase_url="SUA_URL_DO_SUPABASE"
    supabase_key="SUA_CHAVE_API_DO_SUPABASE"
    ```

## ▶️ Como Executar

Com o ambiente configurado, inicie a aplicação com Uvicorn:

```bash
uvicorn main:app --reload
```

A API provavelmente estará disponível em `http://127.0.0.1:8000`. Você pode acessar a documentação interativa em `http://127.0.0.1:8000/docs`.

## 📡 Uso da API

### Endpoint Principal: Processar Hemograma

Envia um arquivo PDF de hemograma para ser processado, extraído e salvo no banco de dados.

-   **URL**: `/hemogramToDataBase/{client_id}`
-   **Método**: `POST`
-   **Parâmetros de URL**:
    -   `client_id` (string, **obrigatório**): O identificador único do cliente/usuário.
-   **Corpo da Requisição**:
    -   `file` (arquivo, **obrigatório**): O arquivo PDF do hemograma.

**Exemplo de uso com `curl`:**

```bash
curl -X POST "http://127.0.0.1:8000/hemogramToDataBase/cliente-teste-001" \
     -F "file=@/caminho/para/seu/exame.pdf"
```

#### Resposta de Sucesso (200 OK)

```json
{
  "message": "Hemograma processado com sucesso!",
  "data": {
    "client_id": "cliente-teste-001",
    "exam_date": "2024-08-21",
    "filename": "exame.pdf",
    "total_metrics": 18,
    "metrics": [
      {
        "Paciente": "cliente-teste-001",
        "Data_Exame": "2024-08-21",
        "Métrica": "Hemácias",
        "Valor": 4.7,
        "Unidade": "milhões/mm³"
      },
      {
        "Paciente": "cliente-teste-001",
        "Data_Exame": "2024-08-21",
        "Métrica": "Hemoglobinas",
        "Valor": 14.5,
        "Unidade": "g/dL"
      }
      // ... outras métricas
    ]
  }
}
```

#### Resposta de Erro (422 Unprocessable Entity)

Ocorre quando o PDF é válido, mas o parser não consegue extrair nenhuma métrica conhecida.

```json
{
    "error": "Nenhum dado válido pôde ser extraído do PDF. Verifique o arquivo.",
    "client_id": "cliente-teste-001"
}
```

## 🏗️ Estrutura do Projeto (Sugerida)

```
.
├── .env                 # Arquivo para variáveis de ambiente (NÃO versionar)
├── .gitignore           # Arquivos e pastas a serem ignorados pelo Git
├── hemogram_api/
│   ├── __init__.py
│   └── services/
│       ├── __init__.py
│       └── hemogram_processor.py  # Módulo principal de processamento de PDF
├── main.py              # Arquivo principal da API com os endpoints FastAPI
└── requirements.txt     # Lista de dependências Python
```

## 🤝 Contribuição

Contribuições são bem-vindas! Se você tiver sugestões para melhorar o projeto, sinta-se à vontade para criar um *fork* do repositório e abrir um *Pull Request*.

## 📄 Licença

Este projeto está licenciado sob a Licença MIT. Veja o arquivo `LICENSE` para mais detalhes.
```
