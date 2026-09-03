# Parkinho — Estacionamento com jeito de playground

Sistema simples de controle de estacionamento feito com **Python + Flask + SQLite + HTML/CSS**.

## Funcionalidades

- **Dashboard** com visão geral de vagas e veículos no pátio
- **Entrada e Saída** de veículos (com cálculo automático de valor)
- **Vagas**: normais, preferenciais, PCD e elétricas
- **Controle de placas** (cadastro e busca)
- **Cadastro de clientes**
- **Cadastro de veículos** (placa, marca, modelo, cor, tipo, tamanho, ano)
- **Tabela de preços** (hora, diária, mensal, anual)
- **Relatórios** de receita e histórico de saídas

## Como rodar

```bash
# 1. Entre na pasta do projeto
cd parking_system

# 2. Instale o Flask (se ainda não tiver)
pip install flask
# ou: pip install --user flask

# 3. Execute
python app.py
```

Acesse: **http://127.0.0.1:5000**

O banco SQLite (`estacionamento.db`) é criado automaticamente na primeira execução, com:

- 20 vagas normais (N01–N20)
- 5 vagas preferenciais (P01–P05)
- 3 vagas PCD (D01–D03)
- 3 vagas elétricas (E01–E03)

**Preços não vêm prontos** — o administrador cadastra, edita e exclui no painel de Preços.

## Estrutura

```
parking_system/
├── app.py                 # Backend (Flask + SQLite)
├── estacionamento.db      # Banco (gerado automaticamente)
├── templates/             # Páginas HTML
│   ├── base.html
│   ├── index.html
│   ├── entrada.html
│   ├── saida.html
│   ├── clientes.html
│   ├── form_cliente.html
│   ├── veiculos.html
│   ├── form_veiculo.html
│   ├── vagas.html
│   ├── form_vaga.html
│   ├── precos.html
│   ├── form_preco.html
│   └── relatorios.html
└── static/css/style.css   # Estilos
```

## Fluxo típico de uso

1. Cadastre clientes (opcional)
2. Cadastre veículos (ou use entrada rápida só com a placa)
3. Vá em **Entrada** → selecione veículo/placa + vaga livre
4. No Dashboard, clique em **Registrar Saída** quando o veículo for embora
5. O sistema calcula o valor automaticamente (hora ou diária)
6. Acompanhe tudo em **Relatórios**

## Tecnologias

| Camada     | Tecnologia      |
|------------|-----------------|
| Backend    | Python + Flask  |
| Banco      | SQLite          |
| Frontend   | HTML + CSS      |
| Templates  | Jinja2          |

Simples, sem frameworks pesados, fácil de entender e expandir.
