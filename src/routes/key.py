from flask import Blueprint, request, jsonify
from src.models.key import Key, db
from datetime import datetime
import hashlib

key_bp = Blueprint('key', __name__)

# Webhook URL para logs (será configurado pelo bot)
webhook_url = None

def log_to_webhook(message):
    """Envia log para o webhook configurado"""
    if webhook_url:
        import requests
        try:
            requests.post(webhook_url, json={"content": message})
        except:
            pass

@key_bp.route('/status', methods=['GET'])
def get_status():
    """Retorna o status do servidor"""
    total_keys = Key.query.count()
    active_keys = Key.query.filter_by(is_active=True).count()
    used_keys = Key.query.filter(Key.hwid.isnot(None)).count()
    expired_keys = len([k for k in Key.query.all() if k.is_expired()])
    
    return jsonify({
        'status': 'online',
        'server_time': datetime.utcnow().isoformat(),
        'statistics': {
            'total_keys': total_keys,
            'active_keys': active_keys,
            'used_keys': used_keys,
            'expired_keys': expired_keys,
            'unused_keys': total_keys - used_keys
        }
    })

@key_bp.route('/auth', methods=['POST'])
def authenticate():
    """Autentica uma chave com HWID"""
    data = request.get_json()
    
    if not data or 'key' not in data or 'hwid' not in data:
        return jsonify({'success': False, 'message': 'Chave e HWID são obrigatórios'}), 400
    
    key_value = data['key'].upper()
    hwid = data['hwid']
    
    # Busca a chave
    key_obj = Key.query.filter_by(key_value=key_value).first()
    
    if not key_obj:
        log_to_webhook(f"❌ Tentativa de login com chave inválida: {key_value}")
        return jsonify({'success': False, 'message': 'Chave inválida'}), 404
    
    if not key_obj.is_active:
        log_to_webhook(f"❌ Tentativa de login com chave inativa: {key_value}")
        return jsonify({'success': False, 'message': 'Chave inativa'}), 403
    
    if key_obj.is_paused:
        log_to_webhook(f"❌ Tentativa de login com chave pausada: {key_value}")
        return jsonify({'success': False, 'message': 'Chave pausada'}), 403
    
    if key_obj.is_expired():
        log_to_webhook(f"❌ Tentativa de login com chave expirada: {key_value}")
        return jsonify({'success': False, 'message': 'Chave expirada'}), 403
    
    # Verifica HWID
    if key_obj.hwid and key_obj.hwid != hwid:
        log_to_webhook(f"❌ Tentativa de login com HWID diferente: {key_value} (HWID: {hwid})")
        return jsonify({'success': False, 'message': 'Esta chave já está vinculada a outro dispositivo'}), 403
    
    # Primeiro uso da chave
    first_use = False
    if not key_obj.hwid:
        key_obj.hwid = hwid
        key_obj.first_use_at = datetime.utcnow()
        first_use = True
        db.session.commit()
        log_to_webhook(f"✅ Primeira utilização da chave: {key_value} (HWID: {hwid})")
    else:
        log_to_webhook(f"✅ Login bem-sucedido: {key_value} (HWID: {hwid})")
    
    return jsonify({
        'success': True,
        'message': 'Autenticação bem-sucedida',
        'first_use': first_use,
        'remaining_time': key_obj.get_remaining_time(),
        'key_info': {
            'key': key_obj.key_value,
            'created_at': key_obj.created_at.isoformat(),
            'first_use_at': key_obj.first_use_at.isoformat() if key_obj.first_use_at else None,
            'remaining_time': key_obj.get_remaining_time()
        }
    })

@key_bp.route('/keys', methods=['GET'])
def get_all_keys():
    """Retorna todas as chaves (para o bot)"""
    keys = Key.query.all()
    return jsonify({
        'keys': [key.to_dict() for key in keys],
        'total': len(keys)
    })

@key_bp.route('/keys/<key_value>', methods=['GET'])
def get_key_status(key_value):
    """Retorna o status de uma chave específica"""
    key_obj = Key.query.filter_by(key_value=key_value.upper()).first()
    
    if not key_obj:
        return jsonify({'success': False, 'message': 'Chave não encontrada'}), 404
    
    return jsonify({
        'success': True,
        'key': key_obj.to_dict()
    })

@key_bp.route('/keys', methods=['POST'])
def create_keys():
    """Cria novas chaves"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': 'Dados inválidos'}), 400
    
    quantity = data.get('quantity', 1)
    expires_in_days = data.get('expires_in_days')
    expires_in_hours = data.get('expires_in_hours')
    
    if quantity <= 0 or quantity > 100:
        return jsonify({'success': False, 'message': 'Quantidade deve ser entre 1 e 100'}), 400
    
    created_keys = []
    
    for _ in range(quantity):
        key_value = Key.generate_key()
        new_key = Key(
            key_value=key_value,
            expires_in_days=expires_in_days,
            expires_in_hours=expires_in_hours
        )
        db.session.add(new_key)
        created_keys.append(key_value)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'{quantity} chave(s) criada(s) com sucesso',
        'keys': created_keys
    })

@key_bp.route('/keys/<key_value>', methods=['PUT'])
def update_key(key_value):
    """Atualiza uma chave"""
    data = request.get_json()
    key_obj = Key.query.filter_by(key_value=key_value.upper()).first()
    
    if not key_obj:
        return jsonify({'success': False, 'message': 'Chave não encontrada'}), 404
    
    if 'expires_in_days' in data:
        key_obj.expires_in_days = data['expires_in_days']
        key_obj.expires_in_hours = None
    
    if 'expires_in_hours' in data:
        key_obj.expires_in_hours = data['expires_in_hours']
        key_obj.expires_in_days = None
    
    if 'is_paused' in data and key_obj.can_pause():
        key_obj.is_paused = data['is_paused']
        if data['is_paused']:
            key_obj.pause_count += 1
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Chave atualizada com sucesso',
        'key': key_obj.to_dict()
    })

@key_bp.route('/keys/<key_value>/reset-hwid', methods=['POST'])
def reset_hwid(key_value):
    """Reseta o HWID de uma chave"""
    key_obj = Key.query.filter_by(key_value=key_value.upper()).first()
    
    if not key_obj:
        return jsonify({'success': False, 'message': 'Chave não encontrada'}), 404
    
    if not key_obj.can_reset_hwid():
        return jsonify({'success': False, 'message': 'Limite de reset de HWID atingido'}), 403
    
    key_obj.hwid = None
    key_obj.first_use_at = None
    key_obj.hwid_reset_count += 1
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'HWID resetado com sucesso',
        'key': key_obj.to_dict()
    })

@key_bp.route('/keys/<key_value>', methods=['DELETE'])
def delete_key(key_value):
    """Deleta uma chave específica"""
    key_obj = Key.query.filter_by(key_value=key_value.upper()).first()
    
    if not key_obj:
        return jsonify({'success': False, 'message': 'Chave não encontrada'}), 404
    
    db.session.delete(key_obj)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Chave deletada com sucesso'
    })

@key_bp.route('/keys', methods=['DELETE'])
def delete_all_keys():
    """Deleta todas as chaves"""
    deleted_count = Key.query.delete()
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'{deleted_count} chave(s) deletada(s) com sucesso'
    })

@key_bp.route('/webhook', methods=['POST'])
def set_webhook():
    """Configura o webhook para logs"""
    global webhook_url
    data = request.get_json()
    
    if not data or 'url' not in data:
        return jsonify({'success': False, 'message': 'URL do webhook é obrigatória'}), 400
    
    webhook_url = data['url']
    
    return jsonify({
        'success': True,
        'message': 'Webhook configurado com sucesso'
    })

