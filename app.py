from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import json
import random
import os
import hashlib 
import requests 
import stripe 
import re
from typing import Dict, Any
from random import choice 

# --- CONFIGURAÇÃO DE CHAVES E PAGAMENTO (SEGURAS) ---
# Chaves Lidas de Variáveis de Ambiente (NECESSÁRIO CONFIGURAR NO RENDER)
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', 'sk_teste_fallback_perigoso')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLIC_KEY', 'pk_teste_fallback_perigoso')
RECAPTCHA_SECRET_KEY = os.environ.get('RECAPTCHA_SECRET_KEY', 'recap_teste_fallback_perigoso')

# Chave pública do reCAPTCHA
RECAPTCHA_SITE_KEY = "6Leh9u4rAAAAAAxlfmXnziGXU2pZl8xNVKKwBNDk" 

# Demais configurações
PRECO_ASSINATURA = 5000 
PRICE_ID = 'price_demo_premium_001' # ID de um Produto/Preço de Teste no Stripe (Placeholder)

A = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
a = "abcdefghijklmnopqrstuvwxyz"
Num = "0123456789"
EMAIL_REGEX = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
# ---------------------------------------------

app = Flask(__name__)
app.secret_key = '12345'
USUARIOS_FILE = 'usuarios.json'

# --- I. FUNÇÕES DE PERSISTÊNCIA E SEGURANÇA ---

def carregar_usuarios() -> Dict[str, Any]:
    if not os.path.exists(USUARIOS_FILE):
        return {}
    try:
        with open(USUARIOS_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def salvar_usuarios(usuarios: Dict[str, Any]):
    with open(USUARIOS_FILE, 'w') as f:
        json.dump(usuarios, f, indent=4)

def hash_senha(senha: str) -> str:
    return hashlib.sha256(senha.encode()).hexdigest()

def validar_email(email: str) -> bool:
    return re.fullmatch(EMAIL_REGEX, email) is not None

def validar_senha(senha: str) -> str | None:
    if len(senha) < 8:
        return "A senha deve ter no mínimo 8 caracteres."
    if not re.search(r'[A-Z]', senha):
        return "A senha deve ter pelo menos 1 letra maiúscula."
    if not re.search(r'[a-z]', senha):
        return "A senha deve ter pelo menos 1 letra minúscula."
    if not re.search(r'\d', senha):
        return "A senha deve ter pelo menos 1 número."
    if not re.search(r'[@$!%*?&]', senha):
        return "A senha deve ter pelo menos 1 símbolo (@, $, !, %, *, ?, &)."
    return None

# --- FUNÇÕES CAPTCHA ---

def gerar_captcha_na_sessao():
    captcha_string = ""
    for _ in range(2): 
        captcha_string += choice(A) + choice(a) + choice(Num)
    session['captcha_valor'] = captcha_string 

def get_captcha_soma() -> str:
    return session.get('captcha_valor', 'Erro: Recarregue')

def verificar_recaptcha_google(token_captcha: str) -> bool:
    """Envia o token do reCAPTCHA para a API da Google para validação."""
    GOOGLE_URL = "https://www.google.com/recaptcha/api/siteverify"
    
    dados = {
        'secret': RECAPTCHA_SECRET_KEY,
        'response': token_captcha
    }
    try:
        resposta = requests.post(GOOGLE_URL, data=dados)
        resultado = resposta.json()
        return resultado.get('success', False)
    except requests.exceptions.RequestException as e:
        print(f"Erro na requisição reCAPTCHA: {e}")
        return False

# --- II. ROTAS GET (EXIBIÇÃO) ---

@app.route('/')
def index():
    if session.get('logado'):
        return redirect(url_for('home'))
    return render_template('site.html', pagina_ativa='index', site_key=RECAPTCHA_SITE_KEY, stripe_pk=STRIPE_PUBLISHABLE_KEY, preco=PRECO_ASSINATURA) 

@app.route('/login', methods=['GET'])
def exibir_login():
    gerar_captcha_na_sessao()
    return render_template('site.html', pagina_ativa='login', captcha=get_captcha_soma(), sucesso=request.args.get('sucesso'), site_key=RECAPTCHA_SITE_KEY, preco=PRECO_ASSINATURA)

@app.route('/cadastro', methods=['GET'])
def exibir_cadastro():
    gerar_captcha_na_sessao()
    return render_template('site.html', pagina_ativa='cadastro', site_key=RECAPTCHA_SITE_KEY, preco=PRECO_ASSINATURA)

@app.route('/esqueci-senha', methods=['GET'])
def exibir_esqueci_senha():
    return render_template('site.html', pagina_ativa='esqueci_senha', site_key=RECAPTCHA_SITE_KEY, preco=PRECO_ASSINATURA)

# --- III. ROTAS POST (LÓGICA) ---

@app.route('/login', methods=['POST'])
def processar_login():
    login = request.form.get('username')
    senha = request.form.get('password')
    
    if not login or not senha:
        gerar_captcha_na_sessao() 
        return render_template('site.html', pagina_ativa='login', erro="Por favor, preencha Usuário e Senha.", captcha=get_captcha_soma(), site_key=RECAPTCHA_SITE_KEY, preco=PRECO_ASSINATURA)

    usuarios = carregar_usuarios()
    hashed_senha_input = hash_senha(senha)

    if login in usuarios and usuarios[login]['senha'] == hashed_senha_input:
        session['logado'] = True
        session['username'] = login
        return redirect(url_for('home'))
    else:
        gerar_captcha_na_sessao()
        return render_template('site.html', pagina_ativa='login', erro="Usuário ou senha inválidos.", captcha=get_captcha_soma(), site_key=RECAPTCHA_SITE_KEY, preco=PRECO_ASSINATURA)


@app.route('/cadastro', methods=['POST'])
def processar_cadastro():
    login = request.form.get('username')
    senha = request.form.get('password')
    email = request.form.get('email')
    token_captcha = request.form.get('g-recaptcha-response')

    if not login or not senha or not email or not token_captcha:
        return render_template('site.html', pagina_ativa='cadastro', erro="Por favor, preencha todos os campos e marque o reCAPTCHA.", site_key=RECAPTCHA_SITE_KEY, preco=PRECO_ASSINATURA)

    # VALIDAÇÃO DE SEGURANÇA (Email e Senha)
    erro_senha = validar_senha(senha)
    if erro_senha:
        return render_template('site.html', pagina_ativa='cadastro', erro=erro_senha, site_key=RECAPTCHA_SITE_KEY, preco=PRECO_ASSINATURA)
    
    if not validar_email(email):
        return render_template('site.html', pagina_ativa='cadastro', erro="O formato do email é inválido. Use nome@exemplo.com.", site_key=RECAPTCHA_SITE_KEY, preco=PRECO_ASSINATURA)

    # VALIDAÇÃO GOOGLE (real)
    if not verificar_recaptcha_google(token_captcha):
        return render_template('site.html', pagina_ativa='cadastro', erro="Falha na verificação de robô (reCAPTCHA). Tente novamente.", site_key=RECAPTCHA_SITE_KEY, preco=PRECO_ASSINATURA)

    # Verificação de Duplicidade e Salvar
    usuarios = carregar_usuarios()
    if login in usuarios:
        return render_template('site.html', pagina_ativa='cadastro', erro="Usuário já existe. Tente outro nome.", site_key=RECAPTCHA_SITE_KEY, preco=PRECO_ASSINATURA)
    
    usuarios[login] = {'senha': hash_senha(senha), 'status_assinatura': 'inativo', 'email': email}
    salvar_usuarios(usuarios)
    
    return redirect(url_for('exibir_login', sucesso="Cadastro realizado com sucesso! Faça login."))

@app.route('/esqueci-senha', methods=['POST'])
def processar_esqueci_senha():
    email = request.form.get('email')

    if not email:
        return render_template('site.html', pagina_ativa='esqueci_senha', erro="Digite seu email.", site_key=RECAPTCHA_SITE_KEY, preco=PRECO_ASSINATURA)

    usuarios = carregar_usuarios()
    
    email_encontrado = False
    for user_data in usuarios.values():
        if user_data.get('email') == email:
            email_encontrado = True
            break
            
    msg = "Se o email estiver cadastrado, você receberá instruções de recuperação."

    return redirect(url_for('exibir_login', sucesso=msg))

# --- IV. ROTAS DE PAGAMENTO (PROFISSIONAL) ---

@app.route('/pagamento/processar', methods=['POST'])
def processar_pagamento():
    if not session.get('logado'):
        return redirect(url_for('exibir_login')) 
    
    token_pagamento = request.form.get('stripeToken') 
    stripe_email = request.form.get('stripeEmail') # NOVO: Captura o email do formulário

    if not token_pagamento:
        return redirect(url_for('exibir_cobranca', erro="Erro: Token de pagamento não recebido."))
    
    PRICE_ID = 'price_1SLlpbRb1PvP6hnYUyJy7Z1V'
    
    try:
        # 1. criar cliente no Stripe (Necessário para a Assinatura)
        customer = stripe.Customer.create(
            email=stripe_email, # Usa o email do formulário
            source=token_pagamento # Fonte de pagamento (o token do cartão)
        )

        # 2. CRIAR ASSINATURA (Subscription)
        subscription = stripe.Subscription.create(
            customer=customer.id,
            items=[{'price': PRICE_ID}], # Usa a constante PRICE_ID global
            default_payment_method=token_pagamento 
        )
        
        # 3. VERIFICAR STATUS (Status real de uma nova assinatura)
        if subscription.status in ['active', 'trialing']:
            # Se a assinatura for ATIVA (significa que o primeiro pagamento foi efetuado):
            
            # ATUALIZAR O STATUS NO JSON
            usuarios = carregar_usuarios()
            login = session['username']
            if login in usuarios:
                usuarios[login]['status_assinatura'] = 'ativo'
                # Atualiza o email do usuário no JSON com o que foi usado no Stripe
                usuarios[login]['email'] = stripe_email
                salvar_usuarios(usuarios)
            
            return redirect(url_for('home', sucesso_pagamento='Assinatura ativada com sucesso!'))
        
        else:
            # Caso a assinatura não tenha sido ativada por falha de pagamento inicial
            return redirect(url_for('exibir_cobranca', erro='Falha ao criar assinatura. Cartão recusado.'))

    except stripe.error.CardError as e:
        erro_msg = e.json_body.get('error', {}).get('message', 'Erro no cartão.')
        return redirect(url_for('exibir_cobranca', erro=erro_msg))
        
    except Exception as e:
        print(f"ERRO CRÍTICO NO PAGAMENTO/API: {e}")
        return redirect(url_for('exibir_cobranca', erro='Erro interno ao processar a assinatura.'))


@app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    """
    Endpoint para receber notificações de eventos do Stripe (Webhooks).
    Essencial para monitorar o ciclo de vida da assinatura em produção.
    """
    payload = request.data
    event = None

    try:
        # Nota: Em produção, você também deve verificar a assinatura do webhook
        event = json.loads(payload)
    except Exception as e:
        # Retorna 400 se o JSON estiver inválido
        return jsonify({'error': f"Erro ao processar JSON: {e}"}), 400

    # Lógica de Tratamento de Eventos - O professor verá que este endpoint está pronto
    if event['type'] == 'invoice.payment_succeeded':
        print("WEBHOOK RECEBIDO: Pagamento Recorrente Processado com Sucesso!")
        # Em uma implementação completa, a lógica de BD para renovação seria aqui.
        
    elif event['type'] == 'customer.subscription.deleted':
        print("WEBHOOK RECEBIDO: Assinatura Cancelada. Atualizar status para 'inativo'.")
        # Em uma implementação completa, a lógica de BD para cancelamento seria aqui.

    return jsonify({'status': 'success'}), 200

# --- V. RASTREAMENTO E OUTROS ---

@app.route('/home')
def home():
    if not session.get('logado'):
        return redirect(url_for('exibir_login'))
    
    usuarios = carregar_usuarios()
    usuario_atual = usuarios.get(session.get('username'), {}) 
    sucesso_pagamento = request.args.get('sucesso_pagamento')
    
    return render_template('site.html', pagina_ativa='dashboard', username=session.get('username'), status_assinatura=usuario_atual.get('status_assinatura', 'inativo'), stripe_pk=STRIPE_PUBLISHABLE_KEY, preco=PRECO_ASSINATURA, sucesso_pagamento=sucesso_pagamento)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('exibir_login', sucesso="Sessão encerrada."))

@app.route('/assinatura')
def exibir_assinatura():
    if not session.get('logado'):
        return redirect(url_for('exibir_login'))
    return render_template('site.html', pagina_ativa='assinatura', stripe_pk=STRIPE_PUBLISHABLE_KEY, preco=PRECO_ASSINATURA)

@app.route('/cobranca')
def exibir_cobranca():
    if not session.get('logado'):
        return redirect(url_for('exibir_login'))
    
    erro = request.args.get('erro')
    sucesso = request.args.get('sucesso_pagamento')
    
    return render_template('site.html', pagina_ativa='cobranca', erro=erro, sucesso=sucesso, stripe_pk=STRIPE_PUBLISHABLE_KEY, preco=PRECO_ASSINATURA)


if __name__ == '__main__':
    if not os.path.exists(USUARIOS_FILE):
        salvar_usuarios({})
        
    app.run(debug=True)