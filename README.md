# 🚀 Project Login - Solução Web Segura (Python/Flask)

Este projeto demonstra uma solução completa e profissional para autenticação de usuários, segurança e processamento de pagamentos em um ambiente de desenvolvimento moderno.

## 🔗 Link do Projeto (Deploy Ativo)

O projeto está implantado na plataforma Render e pode ser acessado em tempo real:

**URL Pública:**[(https://project-login-flask.onrender.com/)]

---
## Funcionalidades Chave

Este sistema foi construído para atender a padrões profissionais de segurança e usabilidade (UX).

| Módulo | Funcionalidade | Detalhes Técnicos |
| :--- | :--- | :--- |
| **Autenticação** | Login e Cadastro completos. | Persistência de dados em JSON (simulação de BD). |
| **Segurança** | **Validação de Senha Forte** e **Hash SHA256** (para senhas). | Previne ataques comuns. |
| **Anti-Robô** | **Google reCAPTCHA v2 (Real)**. | Valida se o usuário é humano no momento do cadastro (requer chave secreta injetada via ambiente). |
| **Pagamento** | **Integração de Cobrança com Stripe.** | Captura segura de cartão (Stripe Elements) e processamento de transação de teste. |
| **Usabilidade** | **Toggle de Senha** (`👁️` | `🔒`) e UX de Recuperação de Senha. | Recurso moderno que melhora a acessibilidade. |
| **Design** | Tema Dark (Preto/Vermelho) em CSS modular. | Focado em alto contraste e estilo *cyberpunk-lite*. |

## Tecnologias Utilizadas

* **Backend:** Python 3 (Framework Flask)
* **Servidor:** Gunicorn (para produção)
* **Frontend:** HTML5, CSS3, JavaScript
* **Integrações:** Stripe SDK, Google reCAPTCHA API.

---
*Desenvolvido por leozorzii.*
